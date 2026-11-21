"""Native-speaker review datasets (schema `redutax-review/v1`).

Source of truth: backend/app/linguistics/review/<lang>.yaml. Every entry carries a reviewer
decision: `pending_review` (default for everything drafted so far), `approved`, `rejected` or
`corrected` (approved with the reviewer's correction applied). Decisions are added by the merge
script research/scripts/apply_review_decisions.py from a file exported by the review screen or
the spreadsheet — never invented in code.

How entries are used (D56–D60):
  detection entries (negation, condition, constraint, question, entity, quantity, register,
  romanized): every entry except `rejected` is used PROTECTIVELY by the meaning check
  (text it matches is a critical detail; register markers make the check ask for review).
  While a language's entries are pending, word changes in that language are `at_risk`.
  rewrite entries (redundant_expression, shortening): applied automatically in balanced mode
  ONLY when approved AND meaning-preserving AND register-neutral AND safe for automatic use.
  Approved but register-changing or not-safe entries are suggestions; pending entries are
  suggestions in aggressive mode only, labelled as pending review; rejected entries are unused.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REVIEW_DIR = Path(__file__).with_name("review")
SCHEMA = "redutax-review/v1"
LANGUAGES = ("kn", "hi", "ta", "te", "en")
CATEGORIES = ("negation", "condition", "constraint", "question", "entity", "quantity",
              "redundant_expression", "shortening", "register", "romanized")
REWRITE_CATEGORIES = ("redundant_expression", "shortening")
DECISIONS = ("pending_review", "approved", "rejected", "corrected")
DETECT_AS = ("negation", "condition", "constraint", "question", "entity", "number", "datetime", "register")
MATCH = ("word", "suffix", "substring", "phrase")
SCRIPTS = ("Knda", "Deva", "Taml", "Telu", "Latn")
TRI = ("yes", "no", "unknown")
CORRECTABLE = ("expression", "gloss", "original", "proposed", "canonical", "match",
               "preserves_meaning", "changes_register", "safe_for_auto")


class ReviewDataError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    id: str
    language: str
    category: str
    script: str
    expression: str
    gloss: str
    decision: str
    provenance: str
    reviewer: str | None = None
    reviewed_at: str | None = None
    review_notes: str = ""
    note: str = ""
    match: str | None = None
    detect_as: str | None = None
    canonical: str | None = None
    lexicon_ref: str | None = None
    phrase_ref: str | None = None
    original: str | None = None
    proposed: str | None = None
    preserves_meaning: str = "unknown"
    changes_register: str = "unknown"
    safe_for_auto: bool = False
    corrected_fields: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_rewrite(self) -> bool:
        return self.category in REWRITE_CATEGORIES

    @property
    def is_approved(self) -> bool:
        return self.decision in ("approved", "corrected")

    @property
    def auto_eligible(self) -> bool:
        """Balanced mode may apply it without asking."""
        return (self.is_rewrite and self.is_approved and self.safe_for_auto
                and self.preserves_meaning == "yes" and self.changes_register == "no")


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _tri(v, where: str) -> str:
    v = str(v).lower() if v is not None else "unknown"
    if v not in TRI:
        raise ReviewDataError(f"{where}: expected yes/no/unknown, got {v!r}")
    return v


def parse_entry(raw: dict, language: str, provenance: str, where: str) -> Entry:
    def need(key: str):
        if raw.get(key) in (None, ""):
            raise ReviewDataError(f"{where}: missing '{key}'")
        return raw[key]

    cat = need("category")
    if cat not in CATEGORIES:
        raise ReviewDataError(f"{where}: unknown category {cat!r}")
    script = need("script")
    if script not in SCRIPTS:
        raise ReviewDataError(f"{where}: unknown script {script!r}")
    review = raw.get("review") or {}
    decision = review.get("decision")
    if decision not in DECISIONS:
        raise ReviewDataError(f"{where}: review.decision must be one of {DECISIONS} (unreviewed = pending_review)")
    if decision != "pending_review" and not (review.get("reviewer") and review.get("reviewed_at")):
        raise ReviewDataError(f"{where}: a '{decision}' decision needs review.reviewer and review.reviewed_at")
    data = dict(raw)
    corrected: list[str] = []
    if decision == "corrected":
        corr = review.get("correction") or {}
        if not corr:
            raise ReviewDataError(f"{where}: 'corrected' needs review.correction")
        for k, v in corr.items():
            if k not in CORRECTABLE:
                raise ReviewDataError(f"{where}: correction of '{k}' is not allowed")
            data[k] = v
            corrected.append(k)
    for k in ("preserves_meaning", "changes_register", "safe_for_auto"):   # reviewer's own assessment wins
        if k in review and review[k] is not None:
            data[k] = review[k]
    e = Entry(
        id=str(need("id")), language=language, category=cat, script=script,
        expression=_nfc(str(data.get("expression") or need("expression"))), gloss=str(data.get("gloss", "")),
        decision=decision, provenance=str(raw.get("provenance") or provenance),
        reviewer=review.get("reviewer"), reviewed_at=str(review["reviewed_at"]) if review.get("reviewed_at") else None,
        review_notes=str(review.get("notes") or ""), note=str(raw.get("note") or ""),
        match=data.get("match"), detect_as=data.get("detect_as"),
        canonical=str(data["canonical"]) if data.get("canonical") is not None else None,
        lexicon_ref=raw.get("lexicon_ref"), phrase_ref=raw.get("phrase_ref"),
        original=_nfc(str(data["original"])) if data.get("original") is not None else None,
        proposed=_nfc(str(data["proposed"])) if data.get("proposed") is not None else None,
        preserves_meaning=_tri(data.get("preserves_meaning"), where) if cat in REWRITE_CATEGORIES else "unknown",
        changes_register=_tri(data.get("changes_register"), where) if cat in REWRITE_CATEGORIES else "unknown",
        safe_for_auto=bool(data.get("safe_for_auto", False)), corrected_fields=tuple(corrected),
    )
    if e.is_rewrite:
        if e.original is None or e.proposed is None:
            raise ReviewDataError(f"{where}: rewrite entries need 'original' and 'proposed'")
        if len(e.proposed) >= len(e.original):
            raise ReviewDataError(f"{where}: 'proposed' must be shorter than 'original'")
    else:
        if e.match not in MATCH or e.detect_as not in DETECT_AS or not e.canonical:
            raise ReviewDataError(f"{where}: detection entries need match {MATCH}, detect_as {DETECT_AS} and canonical")
    return e


def load_file(path: Path) -> tuple[Entry, ...]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if data.get("schema") != SCHEMA:
        raise ReviewDataError(f"{path.name}: schema must be {SCHEMA}")
    lang = data.get("language")
    if lang not in LANGUAGES or path.stem != lang:
        raise ReviewDataError(f"{path.name}: language must be one of {LANGUAGES} and match the file name")
    prov = str(data.get("default_provenance") or "")
    entries = tuple(parse_entry(raw, lang, prov, f"{path.name}#{i}") for i, raw in enumerate(data.get("entries") or []))
    ids = [e.id for e in entries]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ReviewDataError(f"{path.name}: duplicate ids {sorted(dup)}")
    return entries


@lru_cache
def load_all(directory: Path = REVIEW_DIR) -> dict[str, tuple[Entry, ...]]:
    return {p.stem: load_file(p) for p in sorted(directory.glob("*.yaml"))}


def summary(entries_by_lang: dict[str, tuple[Entry, ...]] | None = None) -> dict:
    data = entries_by_lang if entries_by_lang is not None else load_all()
    out = {}
    for lang, entries in data.items():
        by_dec = {d: sum(1 for e in entries if e.decision == d) for d in DECISIONS}
        by_cat = {}
        for e in entries:
            c = by_cat.setdefault(e.category, {d: 0 for d in DECISIONS})
            c[e.decision] += 1
        out[lang] = {"total": len(entries), "decisions": by_dec, "categories": by_cat,
                     "auto_rules": sum(1 for e in entries if e.auto_eligible)}
    return out


# ---------- detection lexicons ----------
@dataclass(frozen=True)
class MarkerEntry:
    form: str
    match: str
    detect_as: str
    canonical: str
    entry_id: str


@dataclass(frozen=True)
class MarkerLexicon:
    id: str
    language: str
    script: str
    review_status: str            # "reviewed" only when every entry in it is approved/corrected
    entries: tuple[MarkerEntry, ...]


def _form(e: Entry) -> str:
    f = e.expression.strip()
    if e.match != "phrase":
        f = f.rstrip(".")
    return f.lower() if e.script == "Latn" else f


@lru_cache
def marker_lexicons(directory: Path = REVIEW_DIR) -> tuple[MarkerLexicon, ...]:
    """Detection word lists per (language, script). Negation entries mirrored from negation.yaml
    (lexicon_ref) are left to that file; everything else except rejected entries is included."""
    out = []
    for lang, entries in load_all(directory).items():
        groups: dict[str, list[Entry]] = {}
        for e in entries:
            if e.is_rewrite or e.decision == "rejected" or (e.detect_as == "negation" and e.lexicon_ref):
                continue
            groups.setdefault(e.script, []).append(e)
        for script, es in sorted(groups.items()):
            status = "reviewed" if all(e.is_approved for e in es) else "unreviewed"
            out.append(MarkerLexicon(f"{lang}-{script}-markers", lang, script, status, tuple(
                MarkerEntry(_form(e), e.match, e.detect_as, e.canonical, e.id) for e in es)))
    return tuple(out)


# ---------- optimizer phrase rules ----------
def phrase_rule_sets(directory: Path = REVIEW_DIR) -> dict[str, dict[str, list[Entry]]]:
    """Per language: {'auto': [...], 'approved_suggest': [...], 'pending': [...]} rewrite entries.
    English entries that mirror phrases/en.yaml (phrase_ref) are included only once approved,
    because the developer-curated file already supplies the pending suggestions."""
    out: dict[str, dict[str, list[Entry]]] = {}
    for lang, entries in load_all(directory).items():
        sets = {"auto": [], "approved_suggest": [], "pending": []}
        for e in entries:
            if not e.is_rewrite or e.decision == "rejected":
                continue
            if e.auto_eligible:
                sets["auto"].append(e)
            elif e.is_approved:
                sets["approved_suggest"].append(e)
            elif not e.phrase_ref:
                sets["pending"].append(e)
        out[lang] = sets
    return out
