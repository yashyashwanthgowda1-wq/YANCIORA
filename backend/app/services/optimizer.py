"""Smart prompt optimizer (Feature 3, opt_rules_v2).

Pipeline for every proposed edit (all offsets refer to the NFC original):
  1. protection  — an edit touching a critical detail (Feature 5 extraction) is rejected
                   (phrase-list edits may rewrite condition/constraint wording; the meaning gate
                   then checks the canonical condition/constraint is still there)
  2. overlap     — an edit overlapping an earlier-priority edit is rejected
  3. tokens      — must reduce tokens under >= 1 requested tokenizer and increase under none
  4. meaning     — Feature 5 check of original vs candidate:
                     preserved → applied automatically
                     at_risk   → returned as a suggestion (not applied)
                     changed   → rejected

Modes and risk levels (opt_rules_v2):
  safe        lossless formatting only: whitespace, invisible characters, repeated punctuation,
              decorative separator runs. Repeated sentences are suggestions.
  balanced    safe + removal of exact repeats of an earlier sentence/line that contain no
              critical detail + phrase lists the team has reviewed.
  aggressive  balanced + suggestions that may change meaning and always need approval:
              phrases from lists not yet reviewed, script/transliteration variants.

If nothing is eligible, the original text is returned exactly as given. Deterministic: fixed
rule order, left to right, no randomness. Token counts are counts of the exact text under each
tokenizer (the same encoding before and after); they are not provider billing.
"""
from __future__ import annotations

from app.core import details as D
from app.core import text as T
from app.optimizer import rules as R
from app.schemas import (
    AcceptedEdit, MeaningCheckRequest, OptimizeRequest, OptimizeResponse, OptimizeSuggestion,
    OptimizeTokenCount, PhraseListRef, RejectedEdit,
)
from app.services.counting import tokenizer_ref
from app.services.meaning import CODE_MIXED_RISK, LEXICON_RISK_PREFIX, MARKER_RISK_PREFIX, ROMANIZED_GUESS_RISK
from app.services.meaning import LIMITATIONS as MEANING_LIMITATIONS
from app.services.meaning import check as meaning_check
from app.services.meaning import check_with_details
from app.tokenizers import TokenizerAdapter, get_tokenizer

MAX_EVALUATED_EDITS = 200   # team decision 2026-11-20 (was 500)
PHRASE_REWRITABLE = {"condition", "constraint"}   # phrase edits may reword these; gate checks them
WS_FLEXIBLE = {"condition", "constraint", "entity", "negation"}   # whitespace-only edits may touch these
INVISIBLE_FLEXIBLE = WS_FLEXIBLE | {"number", "datetime", "question"}
SAFE_RULE_NAMES = {"invisible_chars", "ws_lines", "ws_inline", "punct_repeat", "separator_runs"}
IGNORABLE_FOR_REPEATS = (LEXICON_RISK_PREFIX, MARKER_RISK_PREFIX, CODE_MIXED_RISK,
                         ROMANIZED_GUESS_RISK.split("(")[0])

MODE_POLICY = {
    "safe": ("Safe (lossless formatting): applies only whitespace, invisible-character, repeated-"
             "punctuation and separator fixes that save tokens and pass the meaning check. "
             "Repeated sentences are offered as suggestions."),
    "balanced": ("Balanced (removes redundancy): safe fixes plus removal of exact repeats of an "
                 "earlier sentence or line (also when the repeat holds numbers, negations or other "
                 "details, as long as every value is still in the first copy), plus wording rules "
                 "the team has approved. Each edit must save tokens and pass the meaning check."),
    "aggressive": ("Aggressive (may change meaning): everything in balanced, plus suggestions that "
                   "always need your approval: wording from phrase lists not yet reviewed and "
                   "script/transliteration variants. Nothing extra is applied automatically."),
}
BILLING_WARNING = ("Savings are token counts under the listed tokenizers, not provider billing. "
                   "Hosted models may tokenize differently; experimental tokenizers never change "
                   "hosted-model billing.")
OPTIMIZER_LIMITATIONS = [
    "Rule-based optimizer (opt_rules_v2): it removes redundant whitespace, invisible characters, "
    "repeated punctuation, long separator lines and exact repeated sentences; reviewed phrase "
    "lists are used when the team has approved them. It does not paraphrase or summarise.",
    "Savings on Indic text are usually small: most of the token gap comes from how tokenizers "
    "split the script, which rewriting rules cannot change.",
    "No Indic phrase list exists yet: wording-level shortening in Kannada, Hindi, Tamil and "
    "Telugu needs native-speaker-reviewed lists.",
    "Edits are applied only when the rule-based meaning check reports 'preserved'; that check "
    "has its own limitations (below).",
]


def _apply(src: str, edits: list[R.Edit]) -> str:
    """Apply non-overlapping edits (original offsets). An edit fully inside a larger one is
    superseded by it."""
    chosen: list[R.Edit] = []
    for e in sorted(edits, key=lambda x: (x.start, -(x.end - x.start))):
        if chosen and e.start < chosen[-1].end:
            continue
        chosen.append(e)
    out, pos = [], 0
    for e in chosen:
        out.append(src[pos:e.start])
        out.append(e.after)
        pos = e.end
    out.append(src[pos:])
    return "".join(out)


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def _inside(inner: R.Edit, outer: R.Edit) -> bool:
    return outer.start <= inner.start and inner.end <= outer.end


class _Counter:
    def __init__(self, adapters: list[TokenizerAdapter]):
        self.adapters = adapters

    def __call__(self, text: str) -> dict[str, int]:
        return {a.info.name: a.count(text) for a in self.adapters}


def _token_verdict(delta: dict[str, int]) -> str | None:
    """None if acceptable, else the rejection reason."""
    worse = [f"{n} (+{d})" for n, d in delta.items() if d > 0]
    if worse:
        return "increases tokens under " + ", ".join(worse)
    if all(d == 0 for d in delta.values()):
        return "no token saving"
    return None


def _meaning_summary(mc) -> str:
    bits = [f"{f.state} {f.category} '{f.example}'" for f in mc.findings if f.state != "kept"]
    return "meaning check: changed (" + "; ".join(bits[:3]) + ")"


def _phrase_languages(req: OptimizeRequest, src: str) -> set[str]:
    """Only the prompt's own language (D59): an English rule is never applied to Kannada, Hindi,
    Tamil or Telugu text, and an Indic list only to text in that language. With language 'auto',
    the Indic scripts present decide; Latin-only text counts as English."""
    if req.language != "auto":
        return {req.language}
    return D.languages_in(src) or {"en"}


def _phrase_lists(req: OptimizeRequest, src: str, lists: tuple[R.PhraseList, ...]
                  ) -> tuple[list[R.PhraseList], list[R.PhraseList], list[PhraseListRef]]:
    """(applied lists, suggestion lists, refs). Reviewed lists apply in balanced and aggressive
    mode; reviewed-but-suggestion-only lists (e.g. register changes) are suggestions in those
    modes; lists not yet reviewed are suggestions in aggressive mode only."""
    langs = _phrase_languages(req, src)
    considered = [pl for pl in lists if pl.language in langs]
    active = req.mode != "safe"
    applied = [pl for pl in considered if active and pl.reviewed and not pl.suggest_only]
    suggest = [pl for pl in considered if pl.entries and (
        (active and pl.reviewed and pl.suggest_only) or (req.mode == "aggressive" and not pl.reviewed))]
    refs = [PhraseListRef(id=pl.id, language=pl.language, review_status=pl.review_status,
                          entries=len(pl.entries), applied=pl in applied)
            for pl in considered]
    return applied, suggest, refs


def _script_variant_edits(req: OptimizeRequest, src: str, text: str,
                          adapters: list[TokenizerAdapter]) -> tuple[list[R.Edit], list[str]]:
    """Whole-text script-variant edits (one per distinct variant text) for aggressive mode."""
    from app.schemas import ScriptVariantsRequest
    from app.services import transliteration as TL

    lang = req.language if req.language != "auto" else T.guess_language(
        T.detect_script(T.normalize(text)))
    if lang not in TL.LANG_SCRIPT:
        return [], ["Script-change suggestions need Kannada, Hindi, Tamil or Telugu text "
                    "(or language set to kn, hi, ta or te)."]
    try:
        resp = TL.script_variants(ScriptVariantsRequest(
            text=text, language=lang, target_schemes=[TL.DEFAULT_SCHEME, *TL.ASCII_SCHEMES],
            tokenizers=[a.info.name for a in adapters], protected_terms=req.protected_terms),
            adapters)
    except TL.TransliterationUnavailable:
        return [], ["Script-change suggestions unavailable: indic-transliteration is not installed."]
    edits, seen = [], set()
    for v in resp.variants:
        if v.text in seen or v.text == text or v.converted_spans == 0:
            continue
        seen.add(v.text)
        edits.append(R.Edit(f"script_variant:{v.scheme}", 0, len(src), v.text))
    notes = [w for v in resp.variants for w in v.warnings]
    return edits, list(dict.fromkeys(notes))


def _only_lexicon_risk(mc) -> bool:
    """at_risk solely because an unreviewed negation list was used. For removing an exact
    repeat that holds no detected detail this is not a real risk: every word, including any
    undetected negation, is still present in the first copy."""
    return mc.status == "at_risk" and bool(mc.risks) and all(r.startswith(IGNORABLE_FOR_REPEATS)
                                                              for r in mc.risks)


REGISTER_DROP_RISK = ("Removes a politeness or request phrase (e.g. 'please', 'I would like you to'): "
                      "the tone becomes more direct. Approve only if that is acceptable.")


def _register_drop(before: str, after: str, markers) -> bool:
    """True when any politeness/request marker occurs fewer times after the edit (count-based)."""
    rb, ra = D.register_markers(before, markers=markers), D.register_markers(after, markers=markers)
    return any(ra[k] < n for k, n in rb.items())


def _repeat_only_loss(mc) -> bool:
    """Every difference is a lower count of a value that is still present (nothing added,
    nothing gone entirely) — what removing one copy of a repeated sentence does."""
    diffs = [f for f in mc.findings if f.state != "kept"]
    return bool(diffs) and all(f.state == "missing" and f.candidate_count >= 1 for f in diffs)


def optimize(req: OptimizeRequest, adapters: list[TokenizerAdapter] | None = None,
             phrase_lists: tuple[R.PhraseList, ...] | None = None) -> OptimizeResponse:
    adapters = adapters or [get_tokenizer(n) for n in req.tokenizers]
    count = _Counter(adapters)
    src = D.nfc(req.text)
    explicit = None if req.language == "auto" else req.language
    lexes = D.active_lexicons(explicit, src)
    markers = D.active_markers(explicit, src)
    protected = D.extract_details(src, protected_terms=req.protected_terms, lexicons=lexes,
                                  markers=markers)
    resolved_lang = explicit or T.guess_language(T.detect_script(T.normalize(src)))

    lists = phrase_lists if phrase_lists is not None else R.load_phrase_lists() + R.review_phrase_lists()
    active_lists, suggest_lists, list_refs = _phrase_lists(req, src, lists)
    phrase_auto = R.phrase_edits(src, active_lists)
    list_of = {pl.id: pl for pl in active_lists + suggest_lists}
    phrase_suggest = R.phrase_edits(src, suggest_lists)
    auto_keys = {(e.start, e.end, e.after) for e in phrase_auto}
    phrase_suggest = [e for e in phrase_suggest if (e.start, e.end, e.after) not in auto_keys]
    auto_candidates = R.safe_edits(src) + phrase_auto
    phrase_ids = {id(e) for e in phrase_auto + phrase_suggest}

    def edit_language(e: R.Edit) -> str | None:
        pl = list_of.get(e.rule.removeprefix("phrase:")) if e.rule.startswith("phrase:") else None
        return pl.language if pl else resolved_lang

    def edit_risk(e: R.Edit, kind: str | None = None) -> str:
        if kind in ("script_variant", "unreviewed_phrase"):
            return "meaning_change"
        if e.rule in SAFE_RULE_NAMES:
            return "lossless"
        if e.rule == "duplicate_sentence":
            return "redundancy"
        if e.rule.startswith("script_variant"):
            return "meaning_change"
        return "wording"

    def extras(e: R.Edit, before: dict[str, int] | None, after: dict[str, int] | None,
               validation: str, approval: bool, kind: str | None = None) -> dict:
        return {"language": edit_language(e), "source": e.source or None, "risk": edit_risk(e, kind),
                "approval_required": approval, "validation": validation,
                "tokens_before": before, "tokens_after": after}

    # Candidates differ from the original only by edit replacements. If no replacement adds a
    # new script, the lexicons and the original's details are the same for every candidate,
    # so they are computed once (identical result to meaning.check, much faster).
    src_langs = D.languages_in(src)
    reuse = explicit is not None or all(D.languages_in(e.after) <= src_langs
                                        for e in auto_candidates + phrase_suggest)

    def gate(candidate: str):
        mreq = MeaningCheckRequest(original=src, candidate=candidate, language=req.language,
                                   protected_terms=req.protected_terms)
        if reuse:
            return check_with_details(mreq, original_details=protected, lexicons=lexes, markers=markers)
        return meaning_check(mreq)

    def protected_hit(e: R.Edit):
        exempt = PHRASE_REWRITABLE if id(e) in phrase_ids else set()
        if e.rule in ("ws_inline", "ws_lines") and not src[e.start:e.end].strip() and not e.after.strip():
            # Spacing inside multi-word markers and title+name spans cannot change them (they are
            # matched whitespace-flexibly); the meaning gate still checks the result.
            exempt = exempt | WS_FLEXIBLE
        elif e.rule == "invisible_chars":
            # An invisible character inside a detected word does not change the word (matching
            # ignores it); quoted text, code, URLs, money and protected terms stay protected.
            exempt = exempt | INVISIBLE_FLEXIBLE
        return next((d for d in protected if d.category not in exempt
                     and _overlaps(e.start, e.end, d.start, d.end)), None)

    rejected: list[RejectedEdit] = []
    suggestions: list[OptimizeSuggestion] = []
    accepted_edits: list[R.Edit] = []
    accepted: list[AcceptedEdit] = []

    def reject(e: R.Edit, stage: str, reason: str, delta: dict[str, int] | None = None,
               before: dict[str, int] | None = None, after: dict[str, int] | None = None,
               kind: str | None = None) -> None:
        rejected.append(RejectedEdit(rule=e.rule, start=e.start, end=e.end, before=src[e.start:e.end],
                                     after=e.after, token_delta=delta, reason=reason, stage=stage,
                                     **extras(e, before, after, f"rejected: {stage}", False, kind)))

    # 1–2. protection and overlap, in fixed priority order
    viable: list[R.Edit] = []
    for e in auto_candidates:
        hit = protected_hit(e)
        if hit:
            reject(e, "protected", f"touches protected detail ({hit.category}: {hit.text})")
            continue
        prior = next((v for v in viable if _overlaps(e.start, e.end, v.start, v.end)), None)
        if prior:
            reject(e, "overlap", f"overlaps an earlier edit by {prior.rule}")
            continue
        viable.append(e)

    # Repeated sentences: removable automatically in balanced/aggressive mode only when the
    # repeat holds no critical detail (removing one copy of a detail lowers its count, which the
    # meaning gate reports as 'changed'); otherwise, and always in safe mode, a suggestion.
    duplicates = R.duplicate_sentences(src)
    # opt_rules_v4 (D64): in balanced/aggressive every exact repeat is tried automatically; one
    # holding details is accepted only if each detail value is still present in the first copy.
    auto_dups = [e for e in duplicates if req.mode != "safe"]
    review_only: list[tuple[str, R.Edit]] = [("duplicate_sentence", e) for e in duplicates
                                             if e not in auto_dups]
    for e in phrase_suggest:
        hit = protected_hit(e)
        pl = list_of.get(e.rule.removeprefix("phrase:"))
        kind = "approved_phrase" if pl is not None and pl.reviewed else "unreviewed_phrase"
        if hit:
            reject(e, "protected", f"touches protected detail ({hit.category}: {hit.text})", kind=kind)
        else:
            review_only.append((kind, e))

    # 3–4. tokens, then the meaning gate; one edit at a time
    current = count(src)
    evaluated = 0

    def accept(e: R.Edit, delta: dict[str, int], reason: str, before: dict[str, int],
               after: dict[str, int], validation: str) -> None:
        nonlocal accepted_edits, accepted
        if e.rule == "duplicate_sentence":   # edits inside a removed repeat are superseded
            accepted_edits = [a for a in accepted_edits if not _inside(a, e)]
            accepted = [a for a in accepted if not (e.start <= a.start and a.end <= e.end)]
        accepted_edits.append(e)
        accepted.append(AcceptedEdit(rule=e.rule, start=e.start, end=e.end, before=src[e.start:e.end],
                                     after=e.after, token_delta=delta, reason=reason,
                                     **extras(e, before, after, validation, False)))

    for e in viable + auto_dups:
        if evaluated >= MAX_EVALUATED_EDITS:
            reject(e, "limit", f"not evaluated: limit of {MAX_EVALUATED_EDITS} edits per request")
            continue
        evaluated += 1
        candidate = _apply(src, accepted_edits + [e])
        counts = count(candidate)
        delta = {n: counts[n] - current[n] for n in counts}
        why = _token_verdict(delta)
        if why:
            reject(e, "tokens", why, delta, current, counts)
            continue
        mc = gate(candidate)
        is_dup = e.rule == "duplicate_sentence"
        if not is_dup and mc.status != "changed" and _register_drop(_apply(src, accepted_edits), candidate, markers):
            # opt_rules_v4: a wording edit that removes a politeness/request marker is a suggestion
            # even when another copy of the marker remains elsewhere (set-based check would pass).
            review_only.append(("at_risk_edit", e))
            continue
        if mc.status == "changed" and is_dup and _repeat_only_loss(mc):
            lost = ", ".join(f"{f.category} '{f.example}'" for f in mc.findings if f.state == "missing")
            accept(e, delta, "exact repeat of an earlier sentence; fewer tokens; every critical detail "
                   f"is still in the first copy ({lost})", current, counts,
                   "at_risk (repeat removed; every detail value still present)")
            current = counts
        elif mc.status == "changed":
            reject(e, "meaning", _meaning_summary(mc), delta, current, counts)
        elif mc.status == "preserved" or (is_dup and _only_lexicon_risk(mc)):
            accept(e, delta, "exact repeat of an earlier sentence; fewer tokens; meaning check "
                   + ("preserved" if mc.status == "preserved" else "found no detail change")
                   if is_dup else "fewer tokens; meaning check preserved", current, counts,
                   mc.status if mc.status == "preserved" else "at_risk (only pending word-list risk; exact repeat)")
            current = counts
        else:
            review_only.append(("duplicate_sentence" if is_dup else "at_risk_edit", e))

    final_text = _apply(src, accepted_edits) if accepted_edits else req.text
    final_counts = count(final_text)

    # Aggressive mode: script variants (Feature 6) of the optimized text, as whole-text
    # suggestions. Never applied; measured and gated like every other suggestion.
    script_notes: list[str] = []
    if req.mode == "aggressive":
        script_edits, script_notes = _script_variant_edits(req, src, D.nfc(final_text), adapters)
        review_only.extend(("script_variant", e) for e in script_edits)

    # Suggestions: each measured on its own against the final optimized text.
    removed_repeats = [a for a in accepted_edits if a.rule == "duplicate_sentence"]
    for kind, e in review_only:
        if kind != "script_variant" and any(r.start <= e.start and e.end <= r.end for r in removed_repeats):
            continue                     # inside a repeat that was removed: superseded, nothing to suggest
        if evaluated >= MAX_EVALUATED_EDITS:
            reject(e, "limit", f"not evaluated: limit of {MAX_EVALUATED_EDITS} edits per request")
            continue
        evaluated += 1
        if kind == "script_variant":
            candidate = e.after
        else:
            base = [a for a in accepted_edits if not _overlaps(a.start, a.end, e.start, e.end)]
            candidate = _apply(src, base + [e])
        counts = count(candidate)
        delta = {n: counts[n] - final_counts[n] for n in counts}
        why = _token_verdict(delta)
        if why:
            reject(e, "tokens", why, delta, final_counts, counts, kind)
            continue
        if kind == "script_variant":
            # Review-data markers are words in one script; a script variant keeps every word but
            # writes it differently, so those markers are not compared (script-neutral checks are).
            mc = check_with_details(MeaningCheckRequest(original=src, candidate=candidate, language=req.language,
                                                        protected_terms=req.protected_terms), markers=())
        elif removed_repeats and kind != "duplicate_sentence":
            # Repeats are already removed in final_text; judge this suggestion against that text so
            # the repeats' lower detail counts are not blamed on it (opt_rules_v4).
            mc = check_with_details(MeaningCheckRequest(original=final_text, candidate=candidate,
                                                        language=req.language, protected_terms=req.protected_terms))
        else:
            mc = gate(candidate)
        risks = list(mc.risks)
        status = mc.status
        if kind != "duplicate_sentence" and status == "preserved" and kind != "script_variant"                 and _register_drop(final_text, candidate, markers):
            status = "at_risk"
            risks.append(REGISTER_DROP_RISK)
        if status == "changed" and kind == "duplicate_sentence" and _repeat_only_loss(mc):
            # Removing a repeated copy lowers a detail's count, but every value is still in the
            # first copy. Offered for review with the details named; never applied automatically.
            status = "at_risk"
            risks.append("Removes a repeated copy of: " + ", ".join(
                f"{f.category} '{f.example}'" for f in mc.findings if f.state == "missing")
                + ". The first copy keeps them; check the repetition was not intentional.")
        if status == "changed":
            reject(e, "meaning", _meaning_summary(mc), delta, final_counts, counts, kind)
            continue
        if kind == "script_variant":
            reason = "script change: never applied automatically; needs your review"
        elif kind == "unreviewed_phrase":
            reason = ("wording pending native-speaker review (" + (e.source or "unreviewed list")
                      + "): needs your review" if e.source else
                      "wording from a phrase list not yet reviewed by the team: needs your review")
        elif kind == "approved_phrase":
            reason = (f"approved wording ({e.source}) that is not safe to apply automatically "
                      "(e.g. it changes tone or politeness): needs your review")
        elif kind == "duplicate_sentence":
            reason = ("repeats an earlier sentence; the repeat may be intentional or holds "
                      "critical details: needs your review")
        else:
            reason = "meaning check at_risk: needs your review"
        suggestions.append(OptimizeSuggestion(
            rule=e.rule, start=e.start, end=e.end, before=src[e.start:e.end], after=e.after,
            token_delta=delta, reason=reason, kind=kind, meaning_status=status, risks=risks,
            **extras(e, final_counts, counts, status, True, kind)))

    # Final safety net: the result must pass the gate and never cost more tokens.
    final_check = gate(final_text)
    before_counts = count(req.text)
    has_dup = any(a.rule == "duplicate_sentence" for a in accepted_edits)
    repeat_loss = has_dup and final_check.status == "changed" and _repeat_only_loss(final_check)
    dup_only_risk = has_dup and (_only_lexicon_risk(final_check) or repeat_loss)
    if accepted_edits and ((final_check.status != "preserved" and not dup_only_risk)
                           or any(final_counts[n] > before_counts[n] for n in final_counts)):
        for a in accepted:
            rejected.append(RejectedEdit(**a.model_dump(exclude={"meaning_status", "reason", "validation"}),
                                         reason="final check failed; original returned",
                                         stage="meaning", validation="rejected: final check"))
        accepted, accepted_edits = [], []
        final_text, final_counts = req.text, before_counts
        final_check = gate(req.text)

    if accepted_edits and repeat_loss:
        # Removing repeated copies lowers detail counts; no value disappeared. Reported as
        # at_risk (review recommended), never as 'preserved'.
        lost = ", ".join(f"{f.category} '{f.example}'" for f in final_check.findings if f.state == "missing")
        final_check = final_check.model_copy(update={
            "status": "at_risk",
            "risks": list(final_check.risks) + [
                f"Repeated copies removed ({lost}). Every value is still present once; check the "
                "repetition was not intentional emphasis."]})

    warnings = [BILLING_WARNING]
    skipped = sum(1 for x in rejected if x.stage == "limit")
    if skipped:
        warnings.append(f"Edit limit reached: {MAX_EVALUATED_EDITS} edits were evaluated and "
                        f"{skipped} were not. The unevaluated edits are listed in 'rejected' with "
                        "stage 'limit'; run the optimizer again on the output to continue.")
    if req.mode != "safe" and not any(r.applied for r in list_refs):
        warnings.append("No approved wording rule for this language: no wording was changed. "
                        "Wording rules need native-speaker (Indic) or team (English) approval in the "
                        "review workflow before balanced mode applies them"
                        + (" (aggressive mode shows pending entries as suggestions)."
                           if req.mode == "aggressive" else "."))
    warnings += script_notes
    if not accepted_edits:
        warnings.append("No eligible edit found: the original text is returned unchanged.")
    warnings += [w for w in final_check.warnings if w not in warnings]

    token_counts = []
    for a in adapters:
        n = a.info.name
        b, f = before_counts[n], final_counts[n]
        token_counts.append(OptimizeTokenCount(
            tokenizer=tokenizer_ref(a), status=a.count_status, before=b, after=f, saved=b - f,
            saved_pct=round(100 * (b - f) / b, 2) if b else 0.0))

    by_pos = lambda x: (x.start, x.rule)  # noqa: E731
    return OptimizeResponse(
        method=R.METHOD_ID,
        mode=req.mode,
        mode_policy=MODE_POLICY[req.mode],
        language=resolved_lang,
        script=T.detect_script(T.normalize(src)),
        original=req.text,
        optimized=final_text,
        changed=bool(accepted_edits),
        original_chars=len(req.text),
        optimized_chars=len(final_text),
        chars_saved=len(req.text) - len(final_text),
        token_counts=token_counts,
        accepted=sorted(accepted, key=by_pos),
        suggestions=sorted(suggestions, key=by_pos),
        rejected=sorted(rejected, key=by_pos),
        requires_review=bool(suggestions),
        phrase_lists=list_refs,
        meaning_check=final_check,
        warnings=warnings,
        limitations=OPTIMIZER_LIMITATIONS + MEANING_LIMITATIONS,
    )
