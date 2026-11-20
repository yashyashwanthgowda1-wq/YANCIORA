"""Smart prompt optimizer (Feature 3, opt_rules_v1).

Pipeline for every proposed edit (all offsets refer to the NFC original):
  1. protection  — an edit touching a critical detail (Feature 5 extraction) is rejected
  2. overlap     — an edit overlapping an earlier-priority edit is rejected
  3. tokens      — must reduce tokens under >= 1 requested tokenizer and increase under none
  4. meaning     — Feature 5 check of original vs candidate:
                     preserved → applied automatically
                     at_risk   → returned as a suggestion (not applied)
                     changed   → rejected
Duplicate-sentence removals and script changes are always suggestions. If nothing is
eligible, the original text is returned exactly as given. Deterministic: fixed rule order,
left to right, no randomness.

Token counts are counts of the exact text under each tokenizer; they are not provider billing.
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
from app.services.meaning import LIMITATIONS as MEANING_LIMITATIONS
from app.services.meaning import check as meaning_check
from app.services.meaning import check_with_details
from app.tokenizers import TokenizerAdapter, get_tokenizer

MAX_EVALUATED_EDITS = 200   # team decision 2026-11-20 (was 500)

BILLING_WARNING = ("Savings are token counts under the listed tokenizers, not provider billing. "
                   "Hosted models may tokenize differently; experimental tokenizers never change "
                   "hosted-model billing.")
OPTIMIZER_LIMITATIONS = [
    "Rule-based optimizer (opt_rules_v1): it only removes redundant whitespace, invisible "
    "characters and repeated punctuation, plus reviewed phrase lists in balanced mode.",
    "Savings on Indic text are usually small: most of the token gap comes from how tokenizers "
    "split the script, which rewriting rules cannot change.",
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


def _phrase_lists(req: OptimizeRequest, src: str, lists: tuple[R.PhraseList, ...]
                  ) -> tuple[list[R.PhraseList], list[PhraseListRef]]:
    langs = {"en"} | ({req.language} if req.language != "auto" else D.languages_in(src))
    considered = [pl for pl in lists if pl.language in langs]
    active = req.mode != "safe"
    refs = [PhraseListRef(id=pl.id, language=pl.language, review_status=pl.review_status,
                          entries=len(pl.entries), applied=active and pl.reviewed)
            for pl in considered]
    return [pl for pl in considered if active and pl.reviewed], refs


def optimize(req: OptimizeRequest, adapters: list[TokenizerAdapter] | None = None,
             phrase_lists: tuple[R.PhraseList, ...] | None = None) -> OptimizeResponse:
    adapters = adapters or [get_tokenizer(n) for n in req.tokenizers]
    count = _Counter(adapters)
    src = D.nfc(req.text)
    explicit = None if req.language == "auto" else req.language
    lexes = D.active_lexicons(explicit, src)
    protected = D.extract_details(src, protected_terms=req.protected_terms, lexicons=lexes)

    lists = phrase_lists if phrase_lists is not None else R.load_phrase_lists()
    active_lists, list_refs = _phrase_lists(req, src, lists)
    auto_candidates = R.safe_edits(src) + R.phrase_edits(src, active_lists)

    # Candidates differ from the original only by edit replacements. If no replacement adds a
    # new script, the lexicons and the original's details are the same for every candidate,
    # so they are computed once (identical result to meaning.check, much faster).
    src_langs = D.languages_in(src)
    reuse = explicit is not None or all(D.languages_in(e.after) <= src_langs
                                        for e in auto_candidates)

    def gate(candidate: str):
        mreq = MeaningCheckRequest(original=src, candidate=candidate, language=req.language,
                                   protected_terms=req.protected_terms)
        if reuse:
            return check_with_details(mreq, original_details=protected, lexicons=lexes)
        return meaning_check(mreq)

    rejected: list[RejectedEdit] = []
    suggestions: list[OptimizeSuggestion] = []
    accepted_edits: list[R.Edit] = []
    accepted: list[AcceptedEdit] = []

    def reject(e: R.Edit, stage: str, reason: str, delta: dict[str, int] | None = None) -> None:
        rejected.append(RejectedEdit(rule=e.rule, start=e.start, end=e.end, before=src[e.start:e.end],
                                     after=e.after, token_delta=delta, reason=reason, stage=stage))

    # 1–2. protection and overlap, in fixed priority order
    viable: list[R.Edit] = []
    for e in auto_candidates:
        hit = next((d for d in protected if _overlaps(e.start, e.end, d.start, d.end)), None)
        if hit:
            reject(e, "protected", f"touches protected detail ({hit.category}: {hit.text})")
            continue
        prior = next((v for v in viable if _overlaps(e.start, e.end, v.start, v.end)), None)
        if prior:
            reject(e, "overlap", f"overlaps an earlier edit by {prior.rule}")
            continue
        viable.append(e)
    # Removing one copy of a repeated sentence that holds a critical detail lowers that
    # detail's count, so the meaning gate rejects it as 'changed'.
    review_only: list[tuple[str, R.Edit]] = [("duplicate_sentence", e)
                                             for e in R.duplicate_sentences(src)]

    # 3–4. tokens, then the meaning gate; one edit at a time
    current = count(src)
    evaluated = 0
    for e in viable:
        if evaluated >= MAX_EVALUATED_EDITS:
            reject(e, "limit", f"not evaluated: limit of {MAX_EVALUATED_EDITS} edits per request")
            continue
        evaluated += 1
        candidate = _apply(src, accepted_edits + [e])
        counts = count(candidate)
        delta = {n: counts[n] - current[n] for n in counts}
        why = _token_verdict(delta)
        if why:
            reject(e, "tokens", why, delta)
            continue
        mc = gate(candidate)
        if mc.status == "changed":
            reject(e, "meaning", _meaning_summary(mc), delta)
        elif mc.status == "at_risk":
            review_only.append(("at_risk_edit", e))
        else:
            accepted_edits.append(e)
            current = counts
            accepted.append(AcceptedEdit(rule=e.rule, start=e.start, end=e.end,
                                         before=src[e.start:e.end], after=e.after,
                                         token_delta=delta, reason="fewer tokens; meaning check preserved"))

    final_text = _apply(src, accepted_edits) if accepted_edits else req.text
    final_counts = count(final_text)

    # Suggestions: each measured on its own against the final optimized text.
    for kind, e in review_only:
        if evaluated >= MAX_EVALUATED_EDITS:
            reject(e, "limit", f"not evaluated: limit of {MAX_EVALUATED_EDITS} edits per request")
            continue
        evaluated += 1
        base = [a for a in accepted_edits if not (e.start <= a.start and a.end <= e.end)]
        candidate = _apply(src, base + [e])
        counts = count(candidate)
        delta = {n: counts[n] - final_counts[n] for n in counts}
        why = _token_verdict(delta)
        if why:
            reject(e, "tokens", why, delta)
            continue
        mc = gate(candidate)
        if mc.status == "changed":
            reject(e, "meaning", _meaning_summary(mc), delta)
            continue
        reason = ("meaning check at_risk: needs your review" if mc.status == "at_risk"
                  else "duplicate sentences may be intentional: needs your review")
        suggestions.append(OptimizeSuggestion(
            rule=e.rule, start=e.start, end=e.end, before=src[e.start:e.end], after=e.after,
            token_delta=delta, reason=reason, kind=kind, meaning_status=mc.status, risks=mc.risks))

    # Final safety net: the result must be preserved and never cost more tokens.
    final_check = gate(final_text)
    before_counts = count(req.text)
    if accepted_edits and (final_check.status != "preserved"
                           or any(final_counts[n] > before_counts[n] for n in final_counts)):
        for a in accepted:
            rejected.append(RejectedEdit(**a.model_dump(exclude={"meaning_status", "reason"}),
                                         reason="final check failed; original returned",
                                         stage="meaning"))
        accepted, accepted_edits = [], []
        final_text, final_counts = req.text, before_counts
        final_check = gate(req.text)

    warnings = [BILLING_WARNING]
    skipped = sum(1 for x in rejected if x.stage == "limit")
    if skipped:
        warnings.append(f"Edit limit reached: {MAX_EVALUATED_EDITS} edits were evaluated and "
                        f"{skipped} were not. The unevaluated edits are listed in 'rejected' with "
                        "stage 'limit'; run the optimizer again on the output to continue.")
    if req.mode != "safe" and not any(r.applied for r in list_refs):
        warnings.append("No reviewed phrase list for this language: only safe rules were applied. "
                        "Phrase lists need team review before balanced mode uses them.")
    if req.mode == "aggressive":
        warnings.append("Script-change suggestions arrive with Feature 6 (not implemented yet).")
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
        language=explicit or T.guess_language(T.detect_script(T.normalize(src))),
        original=req.text,
        optimized=final_text,
        changed=bool(accepted_edits),
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
