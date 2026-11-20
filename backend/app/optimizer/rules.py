"""Optimizer rules (Feature 3, opt_rules_v1).

Each rule is a pure function that *proposes* edits against the NFC original text. Rules never
apply edits and never decide acceptance: the optimizer service measures every edit with the
tokenizers and passes it through the Feature 5 meaning gate.

Changing behaviour here means bumping METHOD_ID.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core import text as T

METHOD_ID = "opt_rules_v1"
PHRASE_DIR = Path(__file__).with_name("phrases")
MIN_DUPLICATE_WORDS = 5


@dataclass(frozen=True)
class Edit:
    rule: str
    start: int       # offsets into the NFC original
    end: int
    after: str


@dataclass(frozen=True)
class PhraseEntry:
    pattern: str
    replacement: str
    at_sentence_start: bool
    capitalize_next: bool


@dataclass(frozen=True)
class PhraseList:
    id: str
    language: str
    review_status: str
    entries: tuple[PhraseEntry, ...]

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
    edits = [Edit("punct_repeat", m.start(), m.end(), m.group(1)) for m in _PUNCT_RUN.finditer(src)]
    edits += [Edit("punct_repeat", m.start(), m.end(), "...") for m in _DOT_RUN.finditer(src)]
    return sorted(edits, key=lambda e: e.start)


SAFE_RULES = (invisible_chars, ws_lines, ws_inline, punct_repeat)


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


def duplicate_sentences(src: str) -> list[Edit]:
    """Back-to-back identical sentences with >= MIN_DUPLICATE_WORDS words. Proposes deleting
    the second copy (with the whitespace before it). Never applied automatically."""
    sents = _sentences(src)
    edits = []
    for (ps, pe), (cs, ce) in zip(sents, sents[1:]):
        a, b = T.normalize(src[ps:pe]), T.normalize(src[cs:ce])
        if src[pe:cs].strip() == "" and a == b and T.word_count(a) >= MIN_DUPLICATE_WORDS:
            edits.append(Edit("duplicate_sentence", pe, ce, ""))
    return edits


# ---------- phrase lists (balanced / aggressive, reviewed lists only) ----------
_WORDCHAR = r"\wऀ-෿"   # letters/digits plus Indic blocks (marks are not \w)


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
                                      _keep_case(m.group(0), e.replacement)))
                    continue
                nxt = re.compile(r"\s+(\S)").match(src, m.end())
                if not nxt:
                    continue
                edits.append(Edit(f"phrase:{pl.id}", m.start(), nxt.end(), nxt.group(1).upper()))
    return sorted(edits, key=lambda x: (x.start, x.rule))
