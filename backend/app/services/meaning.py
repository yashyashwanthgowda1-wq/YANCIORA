"""Meaning-preservation check (Feature 5, rules_v1).

Compares the critical details of an original prompt and a candidate rewrite. Statuses:
  changed    a critical detail is missing, added or altered
  at_risk    details all present, but a heuristic warning applies
  preserved  no rule found a problem — NOT a guarantee of semantic equivalence

Framework-free; used by POST /api/meaning-check and by the prompt optimizer (Feature 3).
"""
from __future__ import annotations

from collections import Counter

from app.core import details as D
from app.core import text as T
from app.schemas import (
    CriticalDetail, CriticalDetailsRequest, CriticalDetailsResponse, DetailFinding, LexiconRef,
    MeaningCheckRequest, MeaningCheckResponse,
)

ORDERED_CATEGORIES = ("money", "datetime", "number")
MIN_LENGTH_FOR_RATIO = 40      # characters; shorter texts skip the shrink check
SHRINK_RATIO = 0.5

LIMITATIONS = [
    "Rule-based check (rules_v1): it compares critical details only. It cannot confirm that "
    "the overall meaning, tone or intent is unchanged.",
    "'preserved' means no rule found a problem. It is not a guarantee of semantic equivalence.",
    "Not detected: numbers written as words, units after numbers (e.g. '5 kg' vs '5 g'), "
    "Indic-script month names and dates, Indic-script scale words (e.g. lakh/crore written in "
    "native script), and paraphrases that reverse meaning without a listed negation word.",
    "Negation detection uses word lists. Lists marked 'unreviewed' have not been approved by "
    "native speakers.",
]


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
                       lexicons: tuple[D.Lexicon, ...] | None = None) -> MeaningCheckResponse:
    """Same as check(). Callers that check many candidates against one original (the
    optimizer) pass the original's details and the lexicons once; they must have been
    computed for the same original, language and protected terms."""
    lexes = lexicons if lexicons is not None else D.active_lexicons(
        _explicit(req.language), req.original, req.candidate)
    orig = original_details if original_details is not None else D.extract_details(
        req.original, protected_terms=req.protected_terms, lexicons=lexes)
    cand = D.extract_details(req.candidate, protected_terms=req.protected_terms, lexicons=lexes)

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
        unreviewed = [lx.id for lx in lexes if lx.review_status == "unreviewed"]
        if unreviewed:
            risks.append("Negation word lists not yet approved by native speakers were used ("
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
        limitations=LIMITATIONS,
    )
