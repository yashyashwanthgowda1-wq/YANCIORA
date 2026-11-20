# Script and transliteration policy (`translit_v1`)

Implemented in `backend/app/services/transliteration.py`; API `POST /api/script-variants`.
Engine: `indic_transliteration` 2.3.82 (MIT), installed with `--no-deps` from
`backend/requirements-translit.txt` (hash-pinned). Licence audit: `docs/decisions.md` D29.

## Scope (team decisions 2026-11-20)

| Item | Decision |
|---|---|
| Languages | Kannada (Knda), Hindi (Deva), Tamil (Taml), Telugu (Telu). English: no variants (422). |
| Default scheme | ISO 15919 (`iso`) — diacritics; keeps Dravidian short/long e and o |
| ASCII alternatives | `itrans_dravidian`, `hk_dravidian`, `optitrans_dravidian`, `baraha` |
| Not offered | IAST (loses Dravidian e/o) — may return later as an explicitly lossy research comparison |
| Romanized → native | Only from an explicitly named scheme; `casual` → `status: "unsupported"`; always `requires_review`; Tamil always lossy |
| Application | Never applied automatically — not by Feature 6, not by the optimizer (Feature 3 aggressive mode shows `script_variant` suggestions only) |

## What is converted

- **Native → Romanized:** only maximal runs of the language's own script (letters, marks, and
  ZWJ/ZWNJ inside a run). Never converted: digits (any script), URLs, emails, code, quoted
  text, protected terms, money, dates/times (Feature 5 details) and Latin words.
  Negation words *are* converted (they are part of the text); the meaning check compares them.
- **Romanized → native:** every unprotected segment containing Latin letters. English words
  in code-mixed text are converted too unless listed in `protected_terms` (always reviewed).

## Reported per variant

`lossless_round_trip` + `lossy_reasons` (each converted span is converted back and compared),
ZWJ/ZWNJ counts and round-trip preservation, converted/protected span counts, token counts per
tokenizer from the registry (tokens, tokens per word, delta and ratio vs source), the Feature 5
meaning check, warnings, `requires_review: true`.

## Measured behaviour of the engine (tests in `tests/test_transliteration.py`)

| Finding | Handling |
|---|---|
| All 4 scripts × 5 schemes round-trip on the test sentences, **except** Hindi + ITRANS-Dravidian: आऊंगा → `AUMgA` → ॐगा | Reported as lossy with the reason |
| Hindi + Baraha: chandrabindu (ँ) does not round-trip | Reported as lossy |
| Tamil consonants get Sanskrit-style values (த → `dh`, ட → `ḍh`) — not standard Tamil romanization | Warning on every Tamil variant; native-speaker review pending |
| Devanagari ZWJ is written as the marker `{}` in Romanized text (restored on the way back) | Warning |
| Kannada ZWJ/ZWNJ pass through and round-trip | Reported in `joiners` |
| Native digits would be turned into ASCII digits by the engine | Digits are excluded from conversion |
| Hindi inherent vowel is written (`kala` for कल) | Warning: scheme text ≠ everyday typing |

## Native-speaker review

`docs/review/transliteration_spot_check.md` lists real engine output for 20 samples. No
language is approved yet.

## Limitations

Scheme transliteration changes the script, not the language. Round-trip success shows
reversibility, not that the output is how native speakers write. Token counts are tokenizer
counts (not provider billing) and fewer tokens does not mean a model understands the text
equally well.
