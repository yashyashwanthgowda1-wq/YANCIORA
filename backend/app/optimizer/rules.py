"""Optimizer rules (Feature 3, opt_rules_v2).

Each rule is a pure function that *proposes* edits against the NFC original text. Rules never
apply edits and never decide acceptance: the optimizer service measures every edit with the
tokenizers and passes it through the Feature 5 meaning gate.

v2 (2026-11-21): repeated punctuation is shortened by deleting the extra characters (so the
first '?' — a protected question mark — is never touched); decorative separator runs
(----, ====, ────) are shortened to three characters; repeated sentences are found anywhere in
the text (not only back to back), including unpunctuated lines, from 3 words.

Changing behaviour here means bumping METHOD_ID.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core import text as T

METHOD_ID = "opt_rules_v3"   # v3: review-data phrase rules, own-language rules only (D58-D59), per-edit records
PHRASE_DIR = Path(__file__).with_name("phrases")
MIN_DUPLICATE_WORDS = 3


@dataclass(frozen=True)
class Edit:
    rule: str
    start: int       # offsets into the NFC original
    end: int
    after: str
    source: str = ""     # review-dataset entry id for phrase rules


@dataclass(frozen=True)
class PhraseEntry:
    pattern: str
    replacement: str
    at_sentence_start: bool
    capitalize_next: bool
    id: str = ""          # review-dataset entry id (empty for phrases/*.yaml entries)


@dataclass(frozen=True)
class PhraseList:
    id: str
    language: str
    review_status: str
    entries: tuple[PhraseEntry, ...]
    suggest_only: bool = False   # approved, but not safe for automatic use (e.g. changes register)

    @property
    def reviewed(self) -> bool:
        return self.review_status == "reviewed"


# ---------- safe, language-neutral rules ----------
_INVISIBLE = re.compile("[​­⁠]+")      # ZWSP, soft hyphen, word joiner. NOT ZWJ/ZWNJ.
_BLANK_LINES = re.compile(r"\n(?:[ \t]*\n){2,}")
_TRAILING_WS = re.compile(r"[ \t ]+(?=\r?\n)")
_INLINE_WS = re.compile(r"(?<=\S)[ \t ]{2,}(?=\S)|(?<=\S)\t(?=\S)")
_PUNCT_RUN = re.compile(r"([!?,;])\1+")
_DOT_RUN = re.compile(r"\.{4,}")
# Decorative separators only. Not '#' (heading level), '*' (ratings, emphasis), '_' (fill-in
# blanks) or '~' (code fences): shortening those can change meaning or structure.
_SEPARATOR_RUN = re.compile(r"([-=─━═])\1{3,}")


def invisible_chars(src: str) -> list[Edit]:
    return [Edit("invisible_chars", m.start(), m.end(), "") for m in _INVISIBLE.finditer(src)]


def ws_lines(src: str) -> list[Edit]:
    edits = [Edit("ws_lines", m.start(), m.end(), "\n\n") for m in _BLANK_LINES.finditer(src)]
    edits += [Edit("ws_lines", m.start(), m.end(), "") for m in _TRAILING_WS.finditer(src)]
    lead = len(src) - len(src.lstrip())
    if lead:
        edits.append(Edit("ws_lines", 0, lead, ""))
    trail = len(src.rstrip())
    if trail < len(src) and trail > 0:
        edits.append(Edit("ws_lines", trail, len(src), ""))
    return sorted(edits, key=lambda e: e.start)


def ws_inline(src: str) -> list[Edit]:
    return [Edit("ws_inline", m.start(), m.end(), " ") for m in _INLINE_WS.finditer(src)]


def punct_repeat(src: str) -> list[Edit]:
    """Delete the extra characters of a run ('!!!' → '!', '.....' → '...'). The first character
    stays in place, so a protected question mark is never inside the edit."""
    edits = [Edit("punct_repeat", m.start() + 1, m.end(), "") for m in _PUNCT_RUN.finditer(src)]
    edits += [Edit("punct_repeat", m.start() + 3, m.end(), "") for m in _DOT_RUN.finditer(src)]
    return sorted(edits, key=lambda e: e.start)


def separator_runs(src: str) -> list[Edit]:
    """'----------' → '---', '=======' → '===' (Markdown rules, table rows, underlines keep
    working with three characters)."""
    return [Edit("separator_runs", m.start() + 3, m.end(), "") for m in _SEPARATOR_RUN.finditer(src)]


SAFE_RULES = (invisible_chars, ws_lines, ws_inline, punct_repeat, separator_runs)


def safe_edits(src: str) -> list[Edit]:
    """Safe-mode edits in fixed rule priority order."""
    out: list[Edit] = []
    for rule in SAFE_RULES:
        out.extend(rule(src))
    return out


# ---------- duplicate sentences (always suggestions) ----------
_BOUNDARY = re.compile(r"[.!?।]+|\n")


def _sentences(src: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence: text up to and including a run of . ! ? ।
    Newlines end a fragment without making it a sentence. One linear scan."""
    out, start = [], 0
    for m in _BOUNDARY.finditer(src):
        if m.group(0) != "\n" and m.start() > start:
            out.append((start, m.end()))
        start = m.end()
    return out


def _units(src: str) -> list[tuple[int, int]]:
    """Sentences (ending in . ! ? ।) and non-empty unpunctuated lines, as (start, end) with
    surrounding whitespace excluded."""
    out, start = [], 0
    for m in list(_BOUNDARY.finditer(src)) + [None]:
        end = len(src) if m is None else (m.start() if m.group(0) == "\n" else m.end())
        seg = src[start:end]
        if seg.strip():
            lead = len(seg) - len(seg.lstrip())
            out.append((start + lead, start + len(seg.rstrip())))
        if m is None:
            break
        start = m.end()
    return out


def _dup_key(s: str) -> str:
    return T.normalize(s).casefold()


def duplicate_sentences(src: str) -> list[Edit]:
    """A sentence or line that exactly repeats an earlier one (whitespace- and case-insensitive)
    with >= MIN_DUPLICATE_WORDS words. Proposes deleting the later copy together with the
    whitespace before it. The service decides whether it is applied (balanced mode, no critical
    details inside) or only suggested."""
    seen: set[str] = set()
    edits = []
    for s, e in _units(src):
        key = _dup_key(src[s:e])
        if T.word_count(key) < MIN_DUPLICATE_WORDS:
            continue
        if key in seen:
            start = s
            while start > 0 and src[start - 1].isspace():
                start -= 1
            edits.append(Edit("duplicate_sentence", start, e, ""))
        else:
            seen.add(key)
    return edits


# ---------- phrase lists (balanced / aggressive, reviewed lists only) ----------
_WORDCHAR = r"\wऀ-෿"   # letters/digits plus Indic blocks (marks are not \w)


@lru_cache
def review_phrase_lists(directory: Path | None = None) -> tuple[PhraseList, ...]:
    """Phrase lists built from the native-speaker review datasets (D58): per language an
    approved list (applied in balanced mode), an approved-but-suggestion-only list (e.g. register
    changes) and a pending list (aggressive-mode suggestions labelled pending review)."""
    from app.linguistics.review import REVIEW_DIR, phrase_rule_sets

    out = []
    for lang, sets in phrase_rule_sets(directory or REVIEW_DIR).items():
        for key, status, suggest_only in (("auto", "reviewed", False), ("approved_suggest", "reviewed", True),
                                          ("pending", "unreviewed", False)):
            entries = tuple(PhraseEntry(e.original, e.proposed, e.proposed == "", e.proposed == "", e.id)
                            for e in sets[key])
            if entries:
                out.append(PhraseList(f"review-{lang}-{key}", lang, status, entries, suggest_only))
    return tuple(out)


@lru_cache
def load_phrase_lists(directory: Path = PHRASE_DIR) -> tuple[PhraseList, ...]:
    import yaml

    out = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("review_status") not in ("reviewed", "developer_curated", "unreviewed"):
            raise ValueError(f"{path.name}: bad review_status {data.get('review_status')}")
        entries = []
        for e in data.get("entries") or []:
            entry = PhraseEntry(str(e["pattern"]), str(e.get("replacement", "")),
                                bool(e.get("at_sentence_start", False)),
                                bool(e.get("capitalize_next", False)))
            if entry.replacement == "" and not (entry.at_sentence_start and entry.capitalize_next):
                raise ValueError(f"{path.name}: '{entry.pattern}': an empty replacement needs "
                                 "at_sentence_start and capitalize_next")
            if len(entry.replacement) >= len(entry.pattern):
                raise ValueError(f"{path.name}: '{entry.pattern}': replacement must be shorter")
            entries.append(entry)
        out.append(PhraseList(str(data["id"]), str(data["language"]), data["review_status"],
                              tuple(entries)))
    return tuple(out)


def _at_sentence_start(src: str, pos: int) -> bool:
    before = src[:pos].rstrip(" \t")
    return before == "" or before[-1] in ".!?।\n"


def _keep_case(matched: str, replacement: str) -> str:
    if replacement and matched[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def phrase_edits(src: str, lists: list[PhraseList]) -> list[Edit]:
    edits = []
    for pl in lists:
        for e in pl.entries:
            body = r"\s+".join(re.escape(w) for w in e.pattern.split())
            rx = re.compile(rf"(?<![{_WORDCHAR}']){body}(?![{_WORDCHAR}'])", re.I)
            for m in rx.finditer(src):
                if e.at_sentence_start and not _at_sentence_start(src, m.start()):
                    continue
                if e.replacement:
                    edits.append(Edit(f"phrase:{pl.id}", m.start(), m.end(),
                                      _keep_case(m.group(0), e.replacement), e.id))
                    continue
                nxt = re.compile(r"\s+(\S)").match(src, m.end())
                if not nxt:
                    continue
                edits.append(Edit(f"phrase:{pl.id}", m.start(), nxt.end(), nxt.group(1).upper(), e.id))
    return sorted(edits, key=lambda x: (x.start, x.rule))
