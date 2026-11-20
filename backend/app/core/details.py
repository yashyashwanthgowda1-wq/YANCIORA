"""Critical-detail extraction (Feature 5, method `rules_v1`).

Finds the parts of a prompt whose loss or change would change its meaning: code, URLs,
emails, quoted text, money, dates/times, numbers, negations and caller-protected terms.
Pure functions, no I/O except reading the bundled negation lexicon once.

Offsets refer to the NFC form of the text (`nfc(text)`), *not* the whitespace-collapsed
`nfc_ws_v1` form, so code whitespace survives. Policy: research/configs/meaning_check.md.
Changing behaviour here means bumping METHOD_ID.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.core import text as T

METHOD_ID = "rules_v1"
CATEGORIES = ("code", "url", "email", "quoted", "money", "datetime", "number",
              "negation", "protected_term")
REVIEW_STATUSES = ("reviewed", "developer_curated", "unreviewed")
LEXICON_PATH = Path(__file__).with_name("lexicons") / "negation.yaml"


@dataclass(frozen=True)
class Detail:
    category: str
    text: str        # exactly as written, slice of nfc(text)
    value: str       # comparison key
    start: int
    end: int


@dataclass(frozen=True)
class LexEntry:
    form: str
    match: str       # word | suffix | substring
    canonical: str


@dataclass(frozen=True)
class Lexicon:
    id: str
    language: str
    script: str
    review_status: str
    entries: tuple[LexEntry, ...]


# ---------- helpers ----------
def nfc(text: str) -> str:
    """NFC + BOM removal. The text that detail offsets point into."""
    return unicodedata.normalize("NFC", text).replace("﻿", "")


def ascii_digits(s: str) -> str:
    """Any-script decimal digits → ASCII (೫೦೦ → 500, ५ → 5)."""
    out = []
    for c in s:
        d = unicodedata.decimal(c, None)
        out.append(str(d) if d is not None else c)
    return "".join(out)


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _blank(masked: str, start: int, end: int) -> str:
    return masked[:start] + " " * (end - start) + masked[end:]


# ---------- patterns ----------
# Possessive quantifiers (++ / *+) and start-of-run lookbehinds keep matching linear on long
# digit or letter runs (a 20,000-digit input previously took ~80 s). Matches are unchanged:
# backtracking into these runs could never let the following part (currency word, '@') match.
_AMOUNT = r"\d++(?:[.,]\d++)*+"
_AMOUNT_START = r"(?<!\d)(?<!\d[.,])"     # begin only where a number begins
_SCALE = r"(?:\s?(?:lakhs?|lacs?|crores?|thousand|million|billion|hundred)\b)?"

CODE_FENCE = re.compile(r"```.*?```", re.S)
CODE_INLINE = re.compile(r"`[^`\n]+`")
URL = re.compile(r"(?:\bhttps?://|\bwww\.)[^\s<>\"'`]+", re.I)
EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]++@[\w-]+(?:\.[\w-]+)+")
QUOTED = re.compile(r'"([^"\n]{1,500})"|“([^”\n]{1,500})”|‘([^’\n]{1,500})’|«([^»\n]{1,500})»')
MONEY_PREFIX = re.compile(
    rf"(?P<cur>₹|\$|€|£|\b(?:rs\.?|inr|usd|eur|gbp)(?![a-z]))\s?(?P<amt>{_AMOUNT}{_SCALE})", re.I)
MONEY_SUFFIX = re.compile(
    rf"{_AMOUNT_START}(?P<amt>{_AMOUNT}{_SCALE})\s?"
    rf"(?P<cur>rupees?|rs\.?|inr|usd|dollars?|euros?|eur|gbp)(?![a-z])", re.I)
_MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
          r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
_ORD = r"(?:st|nd|rd|th)?"
DATES = [
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
    re.compile(rf"\b\d{{1,2}}{_ORD}\s+{_MONTH}\b\.?(?:,?\s+\d{{4}}\b)?", re.I),
    re.compile(rf"\b{_MONTH}\.?\s+\d{{1,2}}{_ORD}\b(?:,?\s+\d{{4}}\b)?", re.I),
    re.compile(rf"\b{_MONTH}\.?\s+\d{{4}}\b", re.I),
]
TIMES = [
    re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s?[ap]\.?m\b\.?)?", re.I),
    re.compile(r"\b\d{1,2}\s?[ap]\.?m\b\.?", re.I),
]
NUMBER = re.compile(rf"{_AMOUNT}{_SCALE}%?", re.I)
TOKEN = re.compile(r"[^\s.,;:!?()\[\]{}\"“”«»<>|/\\]+")
_URL_TRAIL = ".,;:!?)]}'\"’”"

CURRENCY = {
    "₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "rupee": "INR", "rupees": "INR",
    "$": "USD", "usd": "USD", "dollar": "USD", "dollars": "USD",
    "€": "EUR", "eur": "EUR", "euro": "EUR", "euros": "EUR",
    "£": "GBP", "gbp": "GBP",
}


def norm_number(s: str) -> str:
    """ASCII digits, grouping commas removed, scale word lowercased: '1,00,000' → '100000'."""
    s = _ws(ascii_digits(s).replace("−", "-")).lower()
    m = re.match(rf"^(-?)([\d.,]+)(.*)$", s)
    if not m:
        return s
    sign, digits, rest = m.groups()
    return sign + digits.replace(",", "") + rest.replace(" ", "")


def _norm_datetime(s: str) -> str:
    s = _ws(ascii_digits(s)).lower()
    s = re.sub(r"\s*([ap])\.?m\.?$", r"\1m", s)
    return s


# ---------- lexicons ----------
@lru_cache
def load_lexicons(path: Path = LEXICON_PATH) -> tuple[Lexicon, ...]:
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = []
    for lx in data.get("lexicons", []):
        if lx["review_status"] not in REVIEW_STATUSES:
            raise ValueError(f"lexicon {lx['id']}: bad review_status {lx['review_status']}")
        entries = []
        for e in lx.get("entries", []):
            if e["match"] not in ("word", "suffix", "substring"):
                raise ValueError(f"lexicon {lx['id']}: bad match type {e['match']}")
            entries.append(LexEntry(unicodedata.normalize("NFC", str(e["form"])).lower(),
                                    e["match"], str(e["canonical"])))
        out.append(Lexicon(lx["id"], lx["language"], lx["script"], lx["review_status"],
                           tuple(entries)))
    return tuple(out)


def languages_in(text: str) -> set[str]:
    """Languages whose native script appears in the text (Latin implies none)."""
    found = set()
    for ch in text:
        lang = T.SCRIPT_TO_LANGUAGE.get(T.script_of_char(ch) or "")
        if lang:
            found.add(lang)
    return found


def active_lexicons(language: str | None, *texts: str) -> tuple[Lexicon, ...]:
    """English always (code-mixing is common). With an explicit language: that language's
    native and Romanized lists. Without one: native lists of scripts seen in the texts;
    Romanized Indic lists are skipped because Latin script does not reveal the language."""
    if language:
        langs, roman_ok = {"en", language}, True
    else:
        langs, roman_ok = {"en"}.union(*(languages_in(t) for t in texts)), False
    return tuple(lx for lx in load_lexicons()
                 if lx.language in langs
                 and (lx.script != "Latn" or lx.language == "en" or roman_ok))


def _neg_match(token: str, lexicons: Iterable[Lexicon]) -> str | None:
    t = token.lower().replace("’", "'").strip("'")
    if not t:
        return None
    for lx in lexicons:
        for e in lx.entries:
            if (e.match == "word" and t == e.form) or \
               (e.match == "suffix" and t.endswith(e.form) and len(t) > len(e.form)) or \
               (e.match == "substring" and e.form in t):
                return e.canonical
    return None


# ---------- extraction ----------
def extract_details(text: str, language: str | None = None,
                    protected_terms: Iterable[str] = (),
                    lexicons: tuple[Lexicon, ...] | None = None) -> list[Detail]:
    """All critical details in `text`, sorted by position. Offsets point into nfc(text)."""
    src = nfc(text)
    masked = src
    found: list[Detail] = []

    def take(start: int, end: int, category: str, value: str) -> None:
        nonlocal masked
        found.append(Detail(category, src[start:end], value, start, end))
        masked = _blank(masked, start, end)

    for m in CODE_FENCE.finditer(masked):
        take(m.start(), m.end(), "code", m.group(0)[3:-3].strip("\n"))
    for m in CODE_INLINE.finditer(masked):
        take(m.start(), m.end(), "code", m.group(0)[1:-1])
    for m in URL.finditer(masked):
        end = m.end()
        while end > m.start() and src[end - 1] in _URL_TRAIL:
            end -= 1
        take(m.start(), end, "url", src[m.start():end])
    for m in EMAIL.finditer(masked):
        take(m.start(), m.end(), "email", m.group(0).lower())
    for m in QUOTED.finditer(masked):
        inner = next(g for g in m.groups() if g is not None)
        take(m.start(), m.end(), "quoted", _ws(inner))
    for pat in (MONEY_PREFIX, MONEY_SUFFIX):
        for m in pat.finditer(masked):
            cur = CURRENCY.get(m.group("cur").lower(), m.group("cur").upper())
            take(m.start(), m.end(), "money", f"{cur} {norm_number(m.group('amt'))}")
    for pat in DATES + TIMES:
        for m in pat.finditer(masked):
            take(m.start(), m.end(), "datetime", _norm_datetime(m.group(0)))
    for m in NUMBER.finditer(masked):
        start = m.start()
        # A minus sign counts only when it stands alone before the number ("-5", not "A-5").
        if start > 0 and masked[start - 1] in "-−" and (start == 1 or masked[start - 2].isspace()):
            start -= 1
        take(start, m.end(), "number", norm_number(src[start:m.end()]))

    lexes = lexicons if lexicons is not None else active_lexicons(language, src)
    for m in TOKEN.finditer(masked):
        canon = _neg_match(m.group(0), lexes)
        if canon:
            found.append(Detail("negation", m.group(0), canon, m.start(), m.end()))

    for term in dict.fromkeys(nfc(t).strip() for t in protected_terms):
        if term:
            for m in re.finditer(re.escape(term), src):
                found.append(Detail("protected_term", term, term, m.start(), m.end()))

    return sorted(found, key=lambda d: (d.start, CATEGORIES.index(d.category)))
