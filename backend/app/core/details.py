"""Critical-detail extraction (Feature 5, method `rules_v2`).

Finds the parts of a prompt whose loss or change would change its meaning: code, URLs,
emails, quoted text, money, dates/times, numbers, conditions, constraints, questions,
negations, names/entities and caller-protected terms.
Pure functions, no I/O except reading the bundled negation lexicon once.

rules_v3 (2026-11-21) adds four categories. Their word lists are English only (developer
curated); Indic condition/constraint words and Indic names are NOT detected and need
native-speaker lists (use protected terms meanwhile):
  condition   if, unless, until, otherwise, except, whenever, only if, as long as, …
  constraint  must, should, only, always, exactly, at least / minimum, at most / maximum, …
  question    each run of '?' (any script)
  entity      Latin-script capitalised words not at a sentence start, and acronyms
              (heuristic; Indic scripts have no letter case)

rules_v4 (2026-11-21) adds Indic and Romanized markers from the native-speaker review datasets
(backend/app/linguistics/review/*.yaml): conditions, constraints, question words, number words,
units, month and day words, titles (the title and the following word are a name), and extra
negation forms. Every entry except `rejected` is used, PROTECTIVELY: all are pending review
today. Register (politeness/formality) markers are returned by `register_markers`, not as details.

Offsets refer to the NFC form of the text (`nfc(text)`), *not* the whitespace-collapsed
`nfc_ws_v1` form, so code whitespace survives. Policy: research/configs/meaning_check.md.
Changing behaviour here means bumping METHOD_ID.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.core import text as T

METHOD_ID = "rules_v5"   # v2 units, suffix words; v3 condition/constraint/question/entity; v4 Indic/Romanized markers from review data; v5 English number/day words, opposites, Romanized markers without a language
CATEGORIES = ("code", "url", "email", "quoted", "money", "datetime", "number",
              "condition", "constraint", "question", "negation", "entity", "protected_term")
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
# Units after a number (rules_v2, backlog B5-1): a closed list of Latin-script units. The unit is
# part of the number's comparison key, so "5 kg" → "5 g" is a change. Indic-script units are not
# covered (they need native-speaker review).
UNITS: dict[str, str] = {}
for _canon, _forms in {
    "mg": ["mg", "milligram", "milligrams"], "g": ["g", "gm", "gms", "gram", "grams"],
    "kg": ["kg", "kgs", "kilo", "kilos", "kilogram", "kilograms"], "tonne": ["tonne", "tonnes", "ton", "tons"],
    "mm": ["mm", "millimetre", "millimetres", "millimeter", "millimeters"],
    "cm": ["cm", "centimetre", "centimetres", "centimeter", "centimeters"],
    "m": ["m", "metre", "metres", "meter", "meters"],
    "km": ["km", "kms", "kilometre", "kilometres", "kilometer", "kilometers"],
    "ft": ["ft", "foot", "feet"], "mile": ["mile", "miles"],
    "ml": ["ml", "millilitre", "millilitres", "milliliter", "milliliters"],
    "l": ["l", "litre", "litres", "liter", "liters", "ltr"],
    "kb": ["kb"], "mb": ["mb"], "gb": ["gb"], "tb": ["tb"],
    "ms": ["ms", "millisecond", "milliseconds"], "sec": ["sec", "secs", "second", "seconds"],
    "min": ["min", "mins", "minute", "minutes"], "hour": ["hr", "hrs", "hour", "hours"],
    "day": ["day", "days"], "week": ["week", "weeks"], "month": ["month", "months"],
    "year": ["yr", "yrs", "year", "years"],
    "°c": ["°c", "°"], "°f": ["°f"],
}.items():
    for _f in _forms:
        UNITS[_f] = _canon
_UNIT_RE = "|".join(re.escape(u) for u in sorted(UNITS, key=len, reverse=True))
NUMBER = re.compile(rf"{_AMOUNT}{_SCALE}%?(?:\s?(?P<unit>{_UNIT_RE})(?![\w°]))?", re.I)
TOKEN = re.compile(r"[^\s.,;:!?()\[\]{}\"“”«»<>|/\\]+")

# rules_v3 — English condition and constraint markers (developer_curated). Multi-word forms
# first; forms with the same meaning share a canonical value so "in the event that" → "if"
# keeps the condition. Indic equivalents are not listed (they need native-speaker review).
_PHRASES = lambda pairs: [(re.compile(r"(?<![\w'])" + r"\s+".join(map(re.escape, f.split())) + r"(?![\w'])", re.I), c)  # noqa: E731
                          for f, c in sorted(pairs, key=lambda p: -len(p[0]))]
CONDITIONS = _PHRASES([
    ("only if", "only if"), ("if and only if", "only if"), ("if", "if"), ("in the event that", "if"),
    ("in case", "in case"), ("provided that", "provided"), ("provided", "provided"),
    ("providing that", "provided"), ("as long as", "as long as"), ("unless", "unless"),
    ("until", "until"), ("till", "until"), ("otherwise", "otherwise"), ("else", "otherwise"),
    ("except", "except"), ("except for", "except"), ("excluding", "except"),
    ("whenever", "whenever"), ("whether", "whether"),
])
CONSTRAINTS = _PHRASES([
    ("must", "must"), ("have to", "must"), ("has to", "must"), ("should", "should"),
    ("shall", "shall"), ("only", "only"), ("always", "always"), ("exactly", "exactly"),
    ("at least", "at least"), ("minimum", "at least"), ("no less than", "at least"),
    ("at most", "at most"), ("maximum", "at most"), ("no more than", "at most"),
    ("up to", "at most"), ("required", "required"), ("mandatory", "required"),
    ("strictly", "strictly"), ("all", "all"), ("every", "every"), ("each", "each"),
])
# rules_v5 — English number words (backlog B5-2, English part) and relative-day words become
# critical details, so "five" → "six" or "tomorrow" → "today" is 'changed' like a digit change.
_NUM_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_NUM_TENS = {w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())}
_NUM_SCALES = {"hundred": 100, "thousand": 1000, "lakh": 100_000, "lakhs": 100_000,
               "million": 1_000_000, "crore": 10_000_000, "crores": 10_000_000,
               "billion": 1_000_000_000}
_NUM_WORD = "|".join(sorted([*_NUM_UNITS, *_NUM_TENS, *_NUM_SCALES], key=len, reverse=True))
NUMBER_WORDS = re.compile(rf"(?<![\w'-])(?:{_NUM_WORD})(?:(?:[\s-]+|\s+and\s+)(?:{_NUM_WORD}))*(?![\w'-])", re.I)
RELATIVE_DAYS = _PHRASES([
    ("day after tomorrow", "day after tomorrow"), ("day before yesterday", "day before yesterday"),
    ("today", "today"), ("tomorrow", "tomorrow"), ("yesterday", "yesterday"), ("tonight", "tonight"),
])
# rules_v5 — closed list of English opposite pairs (backlog B5-4). A change in these words is a
# heuristic warning ('at_risk'), never proof of a change: context decides what they mean.
OPPOSITES = (("before", "after"), ("increase", "decrease"), ("include", "exclude"),
             ("allow", "forbid"), ("allow", "deny"), ("enable", "disable"), ("add", "remove"),
             ("more", "less"), ("more", "fewer"), ("above", "below"), ("higher", "lower"),
             ("earliest", "latest"), ("first", "last"), ("accept", "reject"), ("true", "false"),
             ("open", "close"), ("start", "stop"), ("public", "private"), ("inside", "outside"))
_OPPOSITE_WORDS = {w for pair in OPPOSITES for w in pair}
_OPPOSITE_RX = re.compile(r"(?<![\w'-])(" + "|".join(sorted(_OPPOSITE_WORDS, key=len, reverse=True))
                          + r")(?:s|d|ed|es|ing)?(?![\w'-])", re.I)


def opposite_words(text: str) -> Counter:
    """Count of listed opposite-pair words (with simple -s/-ed/-ing endings) in `text`."""
    return Counter(m.group(1).lower() for m in _OPPOSITE_RX.finditer(nfc(text)))


def number_word_value(phrase: str) -> str | None:
    """'twenty-one' → '21', 'two hundred and five' → '205'. A single trailing scale word stays a
    word, as `norm_number` keeps it for digits: 'five lakh' → '5lakh' (same key as '5 lakh')."""
    words = [w for w in re.split(r"[\s-]+", phrase.lower()) if w and w != "and"]
    if len(words) > 1 and words[-1] in _NUM_SCALES and not any(w in _NUM_SCALES for w in words[:-1]):
        head = number_word_value(" ".join(words[:-1]))
        return f"{head}{words[-1]}" if head is not None else None
    total = current = 0
    seen = False
    for w in re.split(r"[\s-]+", phrase.lower()):
        if w == "and":
            continue
        if w in _NUM_UNITS:
            current += _NUM_UNITS[w]
        elif w in _NUM_TENS:
            current += _NUM_TENS[w]
        elif w == "hundred":
            current = (current or 1) * 100
        elif w in _NUM_SCALES:
            total += (current or 1) * _NUM_SCALES[w]
            current = 0
        else:
            return None
        seen = True
    return str(total + current) if seen else None


QUESTION = re.compile(r"\?+")
_ENTITY = re.compile(r"[A-Z][A-Za-z]*(?:['’]s)?")
_LEAD_CHARS = " \t\r\"'“‘([*•-–—"          # spaces, opening quotes/brackets, bullets
_BOUNDARY_CHARS = ".!?।:\n"
_LIST_NUMBER = re.compile(r"(?:^|\n)[ \t]*\d{1,3}[.)]$")


def _at_sentence_start(text: str, start: int) -> bool:
    before = text[:start].rstrip(_LEAD_CHARS)
    return before == "" or before[-1] in _BOUNDARY_CHARS or bool(_LIST_NUMBER.search(before))


def _is_entity(token: str, text: str, start: int) -> str | None:
    """Comparison key for a Latin name/acronym token, or None. Heuristic: a capitalised word
    not at a sentence/line start, or an all-caps acronym of 2+ letters anywhere."""
    token = _clean_token(token)
    if token == "I" or not _ENTITY.fullmatch(token):
        return None
    word = re.sub(r"['’]s$", "", token)
    if len(word) >= 2 and word.isupper():
        return word
    return None if _at_sentence_start(text, start) else word
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


def _is_word_form(form: str) -> bool:
    """A suffix entry that is itself a word (e.g. Romanized 'illa', 'ledu') also matches the bare
    token (rules_v2, backlog B5-13). Fragments such as "n't" or a native ending starting with a
    vowel sign (ಿಲ್ಲ) are not words, so they still need a longer token."""
    return form.isalpha()


_INVISIBLE_IN_TOKEN = re.compile("[\u200b\u00ad\u2060]")   # ZWSP, soft hyphen, word joiner (not ZWJ/ZWNJ)


def _clean_token(token: str) -> str:
    """Invisible formatting characters must not hide a word from the lists (rules_v4)."""
    return _INVISIBLE_IN_TOKEN.sub("", token)


def _neg_match(token: str, lexicons: Iterable[Lexicon]) -> str | None:
    t = _clean_token(token).lower().replace("’", "'").strip("'")
    if not t:
        return None
    for lx in lexicons:
        for e in lx.entries:
            if (e.match == "word" and t == e.form) or \
               (e.match == "suffix" and t.endswith(e.form)
                and (len(t) > len(e.form) or _is_word_form(e.form))) or \
               (e.match == "substring" and e.form in t):
                return e.canonical
    return None


# ---------- review-data markers (rules_v4) ----------
_IND = r"\wऀ-෿"


def active_markers(language: str | None, *texts: str):
    """Marker lists from the review data, chosen like `active_lexicons`: English always; with an
    explicit language that language's native and Romanized lists; without one, native lists of
    the scripts present (Romanized lists need the language)."""
    from app.linguistics.review import marker_lexicons

    if language:
        langs, roman_ok = {"en", language}, True
    else:
        langs, roman_ok = {"en"}.union(*(languages_in(t) for t in texts)), False
    return tuple(lx for lx in marker_lexicons()
                 if lx.language in langs and (lx.script != "Latn" or lx.language == "en" or roman_ok))


@lru_cache(maxsize=4096)
def _phrase_rx(form: str) -> re.Pattern:
    body = r"\s+".join(re.escape(w) for w in form.split())
    return re.compile(rf"(?<![{_IND}']){body}(?![{_IND}'])", re.I)


def _marker_hit(token: str, form: str, match: str) -> bool:
    t = _clean_token(token).lower().replace("’", "'").strip("'")
    if not t:
        return False
    if match == "word":
        return t == form
    if match == "suffix":
        return t.endswith(form)
    return match == "substring" and form in t


def register_markers(text: str, language: str | None = None, markers=None) -> Counter:
    """Politeness / formality markers (canonical value → count). Not critical details: a change
    makes the meaning check ask for review (at_risk), it never counts as 'changed'."""
    src = nfc(text)
    mk = markers if markers is not None else active_markers(language, src)
    found: Counter = Counter()
    masked = src
    for lx in mk:
        for e in lx.entries:
            if e.detect_as == "register" and e.match == "phrase":
                for m in _phrase_rx(e.form).finditer(masked):
                    found[e.canonical] += 1
                    masked = _blank(masked, m.start(), m.end())
    for m in TOKEN.finditer(masked):
        for lx in mk:
            hit = next((e for e in lx.entries if e.detect_as == "register" and e.match != "phrase"
                        and _marker_hit(m.group(0), e.form, e.match)), None)
            if hit:
                found[hit.canonical] += 1
                break
    return found


# ---------- extraction ----------
def extract_details(text: str, language: str | None = None,
                    protected_terms: Iterable[str] = (),
                    lexicons: tuple[Lexicon, ...] | None = None,
                    markers=None) -> list[Detail]:
    """All critical details in `text`, sorted by position. Offsets point into nfc(text)."""
    src = nfc(text)
    protected_terms = tuple(protected_terms)     # iterated twice (number words, terms)
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
        unit = m.group("unit")
        num_end = m.start("unit") if unit else m.end()
        value = norm_number(src[start:num_end].rstrip())
        take(start, m.end(), "number", f"{value} {UNITS[unit.lower()]}" if unit else value)
    # rules_v5: English number words and relative days (Latin script only). A protected term
    # ("Bengaluru One") keeps its own words: they are not read as numbers.
    term_spans = [(m.start(), m.end()) for t in dict.fromkeys(nfc(t).strip() for t in protected_terms) if t
                  for m in re.finditer(re.escape(t), src)]
    for m in NUMBER_WORDS.finditer(masked):
        if any(s < m.end() and m.start() < e for s, e in term_spans):
            continue
        value = number_word_value(m.group(0))
        if value is not None:
            take(m.start(), m.end(), "number", value)
    for rx, canon in RELATIVE_DAYS:
        for m in rx.finditer(masked):
            take(m.start(), m.end(), "datetime", canon)

    # rules_v3: conditions, constraints, questions (masked so later passes skip them)
    for category, table in (("condition", CONDITIONS), ("constraint", CONSTRAINTS)):
        for rx, canon in table:
            for m in rx.finditer(masked):
                take(m.start(), m.end(), category, canon)
    for m in QUESTION.finditer(masked):
        take(m.start(), m.start() + 1, "question", "?")   # first '?' of a run: '??' → '?' keeps it

    # rules_v4: multi-word markers from the review data (masked so token passes skip them)
    mk = markers if markers is not None else active_markers(language, src)
    for lx in mk:
        for e in lx.entries:
            if e.match == "phrase" and e.detect_as != "register":
                for m in _phrase_rx(e.form).finditer(masked):
                    take(m.start(), m.end(), e.detect_as, e.canonical)

    lexes = lexicons if lexicons is not None else active_lexicons(language, src)
    tokens = list(TOKEN.finditer(masked))
    negated: set[int] = set()
    for m in tokens:
        canon = _neg_match(m.group(0), lexes)
        if canon:
            found.append(Detail("negation", m.group(0), canon, m.start(), m.end()))
            negated.add(m.start())
    # rules_v4: single-word markers (one detail per category per word)
    titled: set[int] = set()
    for i, m in enumerate(tokens):
        tok, seen = m.group(0), set()
        for lx in mk:
            for e in lx.entries:
                if e.match == "phrase" or e.detect_as in ("register",) or e.detect_as in seen:
                    continue
                if not _marker_hit(tok, e.form, e.match):
                    continue
                if e.detect_as == "negation":
                    if m.start() in negated:
                        continue
                    negated.add(m.start())
                seen.add(e.detect_as)
                if e.detect_as == "entity":            # a title: protect it and the following word
                    nxt = tokens[i + 1] if i + 1 < len(tokens) else None
                    end = nxt.end() if nxt else m.end()
                    found.append(Detail("entity", src[m.start():end], nxt.group(0) if nxt else tok, m.start(), end))
                    if nxt:
                        titled.add(nxt.start())
                else:
                    found.append(Detail(e.detect_as, tok, e.canonical, m.start(), m.end()))
    terms: list[Detail] = []
    for term in dict.fromkeys(nfc(t).strip() for t in protected_terms):
        if term:
            for m in re.finditer(re.escape(term), src):
                terms.append(Detail("protected_term", term, term, m.start(), m.end()))
    for m in tokens:
        if m.start() in negated or m.start() in titled or any(t.start < m.end() and m.start() < t.end for t in terms):
            continue                           # a protected term already covers this name
        key = _is_entity(m.group(0), src, m.start())   # sentence starts judged on the real text
        if key:
            found.append(Detail("entity", m.group(0), key, m.start(), m.end()))
    found.extend(terms)

    return sorted(found, key=lambda d: (d.start, CATEGORIES.index(d.category)))
