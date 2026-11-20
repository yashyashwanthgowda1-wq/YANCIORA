"""Text normalization, word counting and script detection (Phase 1).

Policy is documented in research/configs/normalization.md. Changing behaviour here
means bumping NORMALIZATION_ID / WORD_COUNT_METHOD so old benchmark runs stay
distinguishable (BRD §10, §16 reproducibility).
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from functools import lru_cache

NORMALIZATION_ID = "nfc_ws_v1"
WORD_COUNT_METHOD = "unicode_whitespace_v1"

# ZWJ (U+200D) and ZWNJ (U+200C) change how Indic conjuncts render, so they are KEPT.
_REMOVE = {"﻿"}  # byte-order mark only
_WS_RUN = re.compile(r"\s+")  # Python's \s covers Unicode whitespace incl. NBSP

# ISO 15924 code -> inclusive code point ranges
SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "Deva": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "Taml": ((0x0B80, 0x0BFF),),
    "Telu": ((0x0C00, 0x0C7F),),
    "Knda": ((0x0C80, 0x0CFF),),
    "Latn": ((0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F), (0x1E00, 0x1EFF)),
}
SCRIPT_TO_LANGUAGE = {"Knda": "kn", "Deva": "hi", "Taml": "ta", "Telu": "te"}
# Share of letters a second script must reach before text counts as mixed.
MIXED_THRESHOLD = 0.10


def normalize(text: str) -> str:
    """NFC, drop BOM, collapse whitespace runs to one space, trim. Meaning-preserving."""
    text = unicodedata.normalize("NFC", text)
    for ch in _REMOVE:
        text = text.replace(ch, "")
    return _WS_RUN.sub(" ", text).strip()


def _is_wordlike(ch: str) -> bool:
    return unicodedata.category(ch)[0] in {"L", "M", "N"}


def word_count(text: str) -> int:
    """Whitespace-separated chunks that contain at least one letter, mark or digit.

    Punctuation-only chunks ("—", "?") are not words. Input is normalized first.
    """
    return sum(1 for chunk in normalize(text).split(" ") if any(_is_wordlike(c) for c in chunk))


def char_count(text: str) -> int:
    """Unicode code points after normalization (not grapheme clusters)."""
    return len(normalize(text))


@lru_cache(maxsize=8192)
def script_of_char(ch: str) -> str | None:
    cp = ord(ch)
    for script, ranges in SCRIPT_RANGES.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


@lru_cache(maxsize=256)
def detect_script(text: str) -> str | None:
    """Dominant script among letters/marks: a script code, 'mixed', or None (no letters)."""
    counts: Counter[str] = Counter()
    for ch in text:
        if unicodedata.category(ch)[0] in {"L", "M"}:
            counts[script_of_char(ch) or "other"] += 1
    total = sum(counts.values())
    if total == 0:
        return None
    significant = [s for s, n in counts.most_common() if n / total >= MIXED_THRESHOLD]
    if len(significant) > 1:
        return "mixed"
    top = counts.most_common(1)[0][0]
    return None if top == "other" else top


def guess_language(script: str | None) -> str | None:
    """Language implied by a native script within REDUTAX's five languages.

    Latin script returns None: English and Romanized Kannada/Hindi/Tamil/Telugu
    all use it, so the caller must say which. Devanagari maps to Hindi only
    because Hindi is the sole Devanagari language in scope.
    """
    return SCRIPT_TO_LANGUAGE.get(script or "")
