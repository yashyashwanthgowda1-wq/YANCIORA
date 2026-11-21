"""Meaning-preservation check (Feature 5, rules_v5).

Compares the critical details of an original prompt and a candidate rewrite. Statuses:
  changed    a critical detail is missing, added or altered
  at_risk    details all present, but a heuristic warning applies
  preserved  no rule found a problem — NOT a guarantee of semantic equivalence

Framework-free; used by POST /api/meaning-check and by the prompt optimizer (Feature 3).
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from functools import lru_cache

from app.core import details as D
from app.core import text as T
from app.schemas import (
    CriticalDetail, CriticalDetailsRequest, CriticalDetailsResponse, DetailFinding, LexiconRef,
    MeaningCheckRequest, MeaningCheckResponse,
)

ORDERED_CATEGORIES = ("money", "datetime", "number")
LEXICON_RISK_PREFIX = "Negation word lists not yet approved by native speakers were used"
MARKER_RISK_PREFIX = "Indic word lists pending native-speaker review were used"
REGISTER_RISK_PREFIX = "Politeness or formality markers changed"
ROMANIZED_GUESS_RISK = ("Language not given, and the text contains Romanized Kannada/Hindi/Tamil/Telugu words "
                        "({words}): Romanized negations and conditions were not checked. Set the language.")
CODE_MIXED_RISK = ("Code-mixed text without a language: Romanized Kannada/Hindi/Tamil/Telugu words "
                   "(negations, conditions, constraints) were not checked. Set the language.")
OPPOSITE_RISK = ("Words from a list of opposite pairs changed ({words}), e.g. before/after or "
                 "increase/decrease: check the meaning is not reversed.")
MIN_LENGTH_FOR_RATIO = 40      # characters; shorter texts skip the shrink check
SHRINK_RATIO = 0.5

LIMITATIONS = [
    "Rule-based check (rules_v5): it compares critical details only. It cannot confirm that "
    "the overall meaning, tone or intent is unchanged.",
    "Conditions (if, unless, until, …), constraints (must, only, at least, …) and names are "
    "detected in English / Latin script only. Indic-script condition and constraint words and "
    "Indic names are not detected: list important names as protected terms.",
    "Indic and Romanized conditions, constraints, question words, number words, units, month/day "
    "words, titles and politeness markers come from review lists that are pending native-speaker "
    "review: they protect text but cannot confirm preservation (word changes are 'at_risk'). "
    "Inflected forms are often not matched.",
    "'preserved' means no rule found a problem. It is not a guarantee of semantic equivalence.",
    "Not detected: Indic number words outside the pending review lists, units written in Indic "
    "scripts or outside the listed Latin units (kg, km, GB, days, …), English ordinals (first, "
    "second, …), and paraphrases that reverse meaning without a listed negation word. English "
    "number words (five, twenty-one) and relative days (today, tomorrow) are compared; English "
    "opposite words (before/after, increase/decrease, …) only raise a warning.",
    "Negation detection uses word lists. Lists marked 'unreviewed' have not been approved by "
    "native speakers.",
]


def word_content(text: str) -> str:
    """Letters, marks, digits and ZWJ/ZWNJ only: what stays when whitespace, punctuation and
    invisible formatting characters are ignored. Equal word content means no word was edited."""
    return "".join(c for c in D.nfc(text)
                   if unicodedata.category(c)[0] in "LMN" or c in "\u200c\u200d")


@lru_cache(maxsize=1)
def _romanized_forms() -> tuple[tuple[str, str], ...]:
    forms: dict[str, str] = {}
    for lx in D.load_lexicons():
        if lx.script == "Latn" and lx.language != "en":
            for e in lx.entries:
                forms.setdefault(e.form, e.match)
    from app.linguistics.review import marker_lexicons
    for lx in marker_lexicons():
        if lx.script == "Latn" and lx.language != "en":
            for e in lx.entries:
                if e.match != "phrase":
                    forms.setdefault(e.form, e.match)
    return tuple((f, m) for f, m in forms.items() if len(f) >= 3)


def romanized_indic_words(text: str) -> set[str]:
    """Distinct words of Latin-script text that appear in a Romanized Kannada/Hindi/Tamil/Telugu
    negation or marker list (used only to warn when the language was not given)."""
    forms = _romanized_forms()
    return {m.group(0).lower() for m in D.TOKEN.finditer(D.nfc(text))
            if len(m.group(0)) >= 3 and any(D._marker_hit(m.group(0), f, mt) for f, mt in forms)}


@lru_cache(maxsize=1)
def _romanized_critical_lists():
    """All Romanized Kannada/Hindi/Tamil/Telugu negation entries and non-register markers,
    regardless of language (rules_v5). Used only when the language was not given."""
    from app.linguistics.review import marker_lexicons
    neg = tuple((lx.language, e.form, e.match, e.canonical) for lx in D.load_lexicons()
                if lx.script == "Latn" and lx.language != "en" for e in lx.entries)
    mk = tuple((lx.language, e.form, e.match, e.detect_as, e.canonical) for lx in marker_lexicons()
               if lx.script == "Latn" and lx.language != "en" for e in lx.entries
               if e.detect_as != "register")
    return neg, mk


def romanized_critical_markers(text: str) -> Counter:
    """Count of Romanized Indic critical markers ('lang:category:canonical') in Latin text, from
    every Indic language's pending lists. A suffix or substring form needs 3+ letters so short
    fragments do not match ordinary English words."""
    neg, mk = _romanized_critical_lists()
    src = D.nfc(text)
    out: Counter = Counter()
    masked = src
    for lang, form, match, cat, canon in mk:
        if match == "phrase":
            for m in D._phrase_rx(form).finditer(masked):
                out[f"{lang}:{cat}:{canon}"] += 1
                masked = D._blank(masked, m.start(), m.end())
    for m in D.TOKEN.finditer(masked):
        tok = m.group(0)
        for lang, form, match, canon in neg:
            if (match == "word" or len(form) >= 3) and (
                    D._marker_hit(tok, form, match)
                    or (match == "suffix" and D._clean_token(tok).lower() == form)):
                out[f"{lang}:negation:{canon}"] += 1
        for lang, form, match, cat, canon in mk:
            if match != "phrase" and (match == "word" or len(form) >= 3) and D._marker_hit(tok, form, match):
                out[f"{lang}:{cat}:{canon}"] += 1
    return out


ROMANIZED_MARKER_RISK = ("Language not given, and Romanized Kannada/Hindi/Tamil/Telugu words that may be "
                         "negations, conditions, constraints or numbers changed ({words}). Review required: "
                         "set the language.")


def _explicit(language: str) -> str | None:
    return None if language == "auto" else language


def _resolved_language(language: str, text: str) -> str | None:
    return _explicit(language) or T.guess_language(T.detect_script(T.normalize(text)))


def _lexicon_refs(lexes: tuple[D.Lexicon, ...]) -> list[LexiconRef]:
    return [LexiconRef(id=lx.id, language=lx.language, script=lx.script,
                       review_status=lx.review_status) for lx in lexes]


def _language_warnings(language: str, *texts: str) -> list[str]:
    if _explicit(language) is None and any(T.detect_script(T.normalize(t)) in ("Latn", "mixed")
                                           for t in texts):
        return ["Language not given: Romanized Kannada/Hindi/Tamil/Telugu negations were not "
                "checked. Pass 'language' for Romanized or code-mixed text."]
    return []


def _missing_terms(text: str, terms: list[str]) -> list[str]:
    src = D.nfc(text)
    return [f"Protected term not found in the original: '{t}'"
            for t in dict.fromkeys(D.nfc(t).strip() for t in terms) if t and t not in src]


def critical_details(req: CriticalDetailsRequest) -> CriticalDetailsResponse:
    lexes = D.active_lexicons(_explicit(req.language), req.text)
    found = D.extract_details(req.text, protected_terms=req.protected_terms, lexicons=lexes)
    return CriticalDetailsResponse(
        method=D.METHOD_ID,
        language=_resolved_language(req.language, req.text),
        text=D.nfc(req.text),
        details=[CriticalDetail(category=d.category, text=d.text, value=d.value,
                                start=d.start, end=d.end) for d in found],
        negation_lexicons=_lexicon_refs(lexes),
        warnings=_language_warnings(req.language, req.text)
        + _missing_terms(req.text, req.protected_terms),
    )


def check(req: MeaningCheckRequest) -> MeaningCheckResponse:
    return check_with_details(req)


def check_with_details(req: MeaningCheckRequest,
                       original_details: list[D.Detail] | None = None,
                       lexicons: tuple[D.Lexicon, ...] | None = None,
                       markers=None) -> MeaningCheckResponse:
    """Same as check(). Callers that check many candidates against one original (the
    optimizer) pass the original's details and the lexicons once; they must have been
    computed for the same original, language and protected terms."""
    lexes = lexicons if lexicons is not None else D.active_lexicons(
        _explicit(req.language), req.original, req.candidate)
    mk = markers if markers is not None else D.active_markers(
        _explicit(req.language), req.original, req.candidate)
    orig = original_details if original_details is not None else D.extract_details(
        req.original, protected_terms=req.protected_terms, lexicons=lexes, markers=mk)
    cand = D.extract_details(req.candidate, protected_terms=req.protected_terms, lexicons=lexes, markers=mk)

    oc = Counter((d.category, d.value) for d in orig)
    cc = Counter((d.category, d.value) for d in cand)
    example: dict[tuple[str, str], str] = {}
    for d in orig + cand:
        example.setdefault((d.category, d.value), d.text)

    findings = []
    for key in sorted(set(oc) | set(cc), key=lambda k: (D.CATEGORIES.index(k[0]), k[1])):
        o, c = oc[key], cc[key]
        state = "kept" if o == c else ("missing" if c < o else "added")
        findings.append(DetailFinding(category=key[0], value=key[1], example=example[key],
                                      original_count=o, candidate_count=c, state=state))
    missing = sum(1 for f in findings if f.state == "missing")
    added = sum(1 for f in findings if f.state == "added")

    risks: list[str] = []
    differs = T.normalize(req.original) != T.normalize(req.candidate)
    if not missing and not added and differs:
        seq_o = [d.value for d in orig if d.category in ORDERED_CATEGORIES]
        seq_c = [d.value for d in cand if d.category in ORDERED_CATEGORIES]
        if seq_o != seq_c:
            risks.append("The order of numbers, amounts or dates changed; check they still "
                         "refer to the same things.")
        lo, lc = len(T.normalize(req.original)), len(T.normalize(req.candidate))
        if lo >= MIN_LENGTH_FOR_RATIO and lc < SHRINK_RATIO * lo:
            risks.append(f"The candidate is less than {int(SHRINK_RATIO * 100)}% of the original "
                         "length; content beyond the checked details may be lost.")
        words_changed = word_content(req.original) != word_content(req.candidate)
        opp_o, opp_c = D.opposite_words(req.original), D.opposite_words(req.candidate)
        if opp_o != opp_c:
            diff = sorted(set((opp_o - opp_c) + (opp_c - opp_o)))
            risks.append(OPPOSITE_RISK.format(words=", ".join(diff[:6])))
        reg_o = set(D.register_markers(req.original, markers=mk))
        reg_c = set(D.register_markers(req.candidate, markers=mk))
        if reg_o != reg_c:
            bits = [f"removed {', '.join(sorted(reg_o - reg_c))}" if reg_o - reg_c else "",
                    f"added {', '.join(sorted(reg_c - reg_o))}" if reg_c - reg_o else ""]
            risks.append(f"{REGISTER_RISK_PREFIX} ({'; '.join(b for b in bits if b)}): check the "
                         "tone and level of respect are still right.")
        pending = [lx.id for lx in mk if lx.language != "en" and lx.review_status != "reviewed"]
        if pending and words_changed:
            risks.append(MARKER_RISK_PREFIX + " (" + ", ".join(pending) + "): conditions, constraints, "
                         "question words, numbers and names in this language may be missed.")
        if (_explicit(req.language) is None and words_changed
                and any(T.detect_script(T.normalize(t)) == "mixed" for t in (req.original, req.candidate))):
            risks.append(CODE_MIXED_RISK)
        elif _explicit(req.language) is None and words_changed and T.detect_script(T.normalize(req.original)) == "Latn":
            roman = romanized_indic_words(req.original)
            ro, rc = romanized_critical_markers(req.original), romanized_critical_markers(req.candidate)
            if ro != rc:
                diff = sorted({k.split(":", 2)[2] for k in (ro - rc) + (rc - ro)})
                risks.append(ROMANIZED_MARKER_RISK.format(words=", ".join(diff[:4])))
            elif len(roman) >= 2:
                risks.append(ROMANIZED_GUESS_RISK.format(words=", ".join(sorted(roman)[:4])))
        unreviewed = [lx.id for lx in lexes if lx.review_status == "unreviewed"]
        # An unreviewed list matters only when words changed: if letters, marks and digits are
        # identical (only spacing, punctuation repeats or invisible characters differ), no
        # negation word can have been removed or altered (rules_v3).
        if unreviewed and words_changed:
            risks.append(LEXICON_RISK_PREFIX + " ("
                         + ", ".join(unreviewed) + "); negations in this language may be missed.")

    status = "changed" if (missing or added) else ("at_risk" if risks else "preserved")
    return MeaningCheckResponse(
        status=status,
        method=D.METHOD_ID,
        language=_resolved_language(req.language, req.original),
        findings=findings,
        missing_count=missing,
        added_count=added,
        risks=risks,
        warnings=_language_warnings(req.language, req.original, req.candidate)
        + _missing_terms(req.original, req.protected_terms),
        negation_lexicons=_lexicon_refs(lexes),
        marker_lists=[LexiconRef(id=lx.id, language=lx.language, script=lx.script,
                                 review_status=lx.review_status) for lx in mk],
        limitations=LIMITATIONS,
    )
