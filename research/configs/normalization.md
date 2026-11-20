# Normalization and counting policy

Implemented in `backend/app/core/text.py`. Every benchmark row records the IDs below.

## `nfc_ws_v1` — text normalization

1. Unicode NFC.
2. Remove the byte-order mark (U+FEFF).
3. Collapse every run of Unicode whitespace (including no-break space) to one ASCII space; trim ends.

Deliberately **kept**: ZWJ (U+200D) and ZWNJ (U+200C), because they change how Indic
conjuncts render and can change meaning; punctuation; case; digits (native and ASCII).

The original text is always stored unchanged next to the normalized text.

## `unicode_whitespace_v1` — word count

After normalization, split on spaces. A chunk counts as a word if it contains at least one
letter, combining mark or digit (Unicode categories L*, M*, N*). Punctuation-only chunks
do not count.

Known limitation: languages or styles that join words without spaces would be undercounted.
This does not affect the five initial languages in normal writing, but code-mixed text with
attached punctuation or hashtags should be spot-checked.

## Character count

Unicode code points after normalization (not grapheme clusters). A Kannada conjunct such as
ಕ್ಷ is several code points.

## Script detection

Dominant script among letters and marks. A second script with at least 10% of letters makes
the text `mixed`. Latin-script text does not imply a language: it may be English or Romanized
Indic, so the language must be supplied.
