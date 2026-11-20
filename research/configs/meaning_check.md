# Meaning-preservation check policy (`rules_v2`)

Implemented in `backend/app/core/details.py` (extraction) and `backend/app/services/meaning.py`
(comparison). Negation word lists: `backend/app/core/lexicons/negation.yaml`. Changing behaviour
means bumping `METHOD_ID`.

## What it is and is not

A deterministic, rule-based check of **critical details** between an original prompt and a
rewrite. It does not use an LLM or embeddings and cannot judge overall meaning, tone or intent.
`preserved` means *no rule found a problem*, never "meaning guaranteed".

## Extraction (priority order)

Each match is blanked before the next rule runs, so nothing is counted twice (e.g. the `7` in a
URL is part of the URL, not a separate number). Offsets refer to the NFC text (BOM removed,
whitespace kept so code indentation is compared).

| # | Category | Detected | Comparison key |
|---|---|---|---|
| 1 | code | ```` ```…``` ```` fences, `` `…` `` inline | exact inner text (whitespace significant) |
| 2 | url | `http://`, `https://`, `www.` up to whitespace; trailing `.,;:!?)]}'"’”` removed | exact |
| 3 | email | `local@domain.tld` | lowercased |
| 4 | quoted | `"…"`, `“…”`, `‘…’`, `«…»` (≤ 500 chars, single line) | inner text, whitespace collapsed |
| 5 | money | `₹ $ € £ Rs Rs. INR USD EUR GBP` + amount, or amount + `rupee(s) rs inr usd dollar(s) euro(s) eur gbp`; optional lakh/crore/thousand/million/billion/hundred | `CUR amount`, e.g. `INR 500`, `INR 5lakh` |
| 6 | datetime | `yyyy-mm-dd`, `dd/mm/yyyy` (`/ . -`), `12 Jan 2026`, `3rd March`, `Jan 12, 2026`, `March 2026`, `17:30`, `9:15 AM`, `5 pm`, `5 p.m.` | lowercased, ASCII digits, `5 p.m.` → `5pm` |
| 7 | number | digits in any script, grouping commas, decimals, leading minus (only when standalone), `%`, scale word, and (v2) an optional Latin unit from a closed list: mg g kg tonne · mm cm m km ft mile · ml l · KB MB GB TB · ms sec min hour day week month year · °C °F (singular/plural/abbreviation forms) | ASCII digits, commas removed (`1,00,000` → `100000`, `೫೦೦` → `500`); unit canonicalised and appended (`5kg`, `5 kilograms` → `5 kg`) |
| 8 | negation | word lists per language (`word` / `suffix` / `substring` match) | canonical value shared by equivalent forms (`don't` = `do not` = `not`) |
| 9 | protected_term | caller-supplied strings, case-sensitive | exact |

Matching note (v2): a `suffix` entry that is itself a word (letters only, e.g. Romanized `illa`, `illai`, `ledu`) also matches the bare token; fragments like `n't` or native endings starting with a vowel sign (`ಿಲ್ಲ`) still require a longer token.

Negation lists applied: English always; with an explicit `language`, that language's native
and Romanized lists; with `language: auto`, native lists of scripts present in the texts
(Romanized Indic lists are skipped because Latin script does not reveal the language).

## Status rules

1. **changed** — any (category, key) count differs between original and candidate
   (missing, added, or altered = missing + added).
2. **at_risk** — no count differs, the texts differ beyond whitespace, and at least one of:
   - the order of money/datetime/number values changed;
   - the candidate is under 50% of the original length (originals ≥ 40 characters);
   - an `unreviewed` negation list was in effect.
3. **preserved** — otherwise. Every response carries the fixed `limitations` list.

## Review status of word lists

| Lists | Status |
|---|---|
| `en` | `developer_curated` (written from standard grammar; team review welcome) |
| `hi-*`, `kn-*`, `ta-*`, `te-*` | `unreviewed` seed lists — **need native-speaker approval** |

Per team decision (2026-11-20) the Indic lists stay `unreviewed` until native speakers approve
them. To approve: correct the entries, set `review_status: reviewed` and add `reviewed_by`, then
update `tests/test_meaning.py::test_lexicon_file_is_valid_and_indic_lists_unreviewed`.

## Known gaps

Units outside the closed Latin list, and units written in Indic scripts, are not compared; numbers written as words;
Indic-script month names, dates and scale words (ಲಕ್ಷ, लाख, …);
Indic currency words (ರೂಪಾಯಿ, रुपये, …) are not money (their digits are still checked as numbers);
`1,5` is read as `15` (comma = grouping); date formats are not cross-matched
(`12/01/2026` vs `2026-01-12` → changed); paraphrases that reverse meaning without a listed
negation word are not caught.

Planned fixes, with priorities, are tracked in `docs/backlog/feature5_meaning_check.md`
(B5-1 partly and B5-13 done in `rules_v2`; the rest not started).
