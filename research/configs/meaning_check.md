# Meaning-preservation check policy (`rules_v5`)

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
| 8 | condition (v3) | English only: if, only if, if and only if, in the event that, in case, provided (that), as long as, unless, until/till, otherwise/else, except (for)/excluding, whenever, whether | canonical: `in the event that` = `if`; `till` = `until`; `else` = `otherwise` |
| 9 | constraint (v3) | English only: must, have/has to, should, shall, only, always, exactly, at least / minimum / no less than, at most / maximum / no more than / up to, required/mandatory, strictly, all, every, each | canonical: `minimum` = `at least`, `maximum` = `at most`, `have to` = `must` |
| 10 | question (v3) | each run of `?` (any script); only the first `?` of a run is the detail, so `???` → `?` keeps it | `?` |
| 11 | negation | word lists per language (`word` / `suffix` / `substring` match) | canonical value shared by equivalent forms (`don't` = `do not` = `not`) |
| 12 | entity (v3) | Latin-script word starting with a capital letter that is not at a sentence/line start (after `. ! ? । :`, a newline, a bullet or a list number), and all-caps acronyms of 2+ letters; words already found as negations or covered by a protected term are skipped | exact word, possessive `'s` removed |
| 13 | protected_term | caller-supplied strings, case-sensitive | exact |

Matching note (v2): a `suffix` entry that is itself a word (letters only, e.g. Romanized `illa`, `illai`, `ledu`) also matches the bare token; fragments like `n't` or native endings starting with a vowel sign (`ಿಲ್ಲ`) still require a longer token.

Negation lists applied: English always; with an explicit `language`, that language's native
and Romanized lists; with `language: auto`, native lists of scripts present in the texts
(Romanized Indic lists are skipped because Latin script does not reveal the language).

## rules_v5: gaps found by an adversarial probe (2026-11-21)

A probe of 29 new rewrites (English, kn/hi/ta/te, Romanized, code-mixed) found 6 that changed meaning but returned `preserved`. All 6 are now `changed` or `at_risk`. Regression tests: `backend/tests/test_meaning_rules_v5.py`.

| Gap (rules_v4 → `preserved`) | rules_v5 | Status |
|---|---|---|
| Language `auto`, Latin text with **one** Romanized Indic negation removed ("Please share the file, password **beda**." → "… password.") — the warning needed 2+ Romanized words | Romanized negation, condition, constraint, question, number, month/day and title markers from **every** Indic language's pending lists are counted; any count change → `at_risk` ("review required: set the language"). Not `changed`: without the language a Romanized word can also be English (*mat*) | `at_risk` |
| English number words ("five" → "six") — backlog B5-2, English part | `number` detail with the numeric value; "five" ≡ "5", "twenty-one" ≡ "21", "five lakh" ≡ "5 lakh". Words inside a protected term ("Bengaluru One") are skipped | `changed` |
| English relative days ("tomorrow" → "today") | `datetime` detail (today, tomorrow, yesterday, tonight, day after tomorrow, day before yesterday) | `changed` |
| English opposite pairs (before/after, increase/decrease, include/exclude, enable/disable, public/private, …) — backlog B5-4 | closed list of 19 pairs; a count change → `at_risk` (heuristic: context decides the meaning) | `at_risk` |

Side effect: a repeated sentence that contains "today" or "one" now carries a critical detail, so removing the repeat is a reviewed suggestion (as for repeated digits), not an automatic edit.

English review data also gained four request-frame register markers (`en-reg-003` … `en-reg-006`: *I would like you to*, *I want you to*, *could you*, *can you*), after the English validation matrix (`docs/review/english_phrase_validation.md`) showed "I would like you to explain" → "Explain" passing as `preserved`.

## rules_v4: Indic and Romanized markers from the review data (2026-11-21)

Source: `backend/app/linguistics/review/<lang>.yaml`, the native-speaker review datasets (D56).
- **Usage:** every entry except `rejected` is used, PROTECTIVELY. Today all entries are `pending_review`.
- **List selection:** the same as for negation lists. With an explicit language, that language's native and Romanized lists are used; with `auto`, the native lists of the scripts present.

| detect_as | Examples | Detail key |
|---|---|---|
| condition | ದರೆ (ending), ಒಂದು ವೇಳೆ, अगर, यदि, वरना, जब तक, ால் (ending), என்றால், స్తే (ending), ఒకవేళ | `kn:if`, `hi:otherwise`, … |
| constraint | ಮಾತ್ರ, ಬೇಕು (ending), केवल, सिर्फ़, कम से कम, மட்டும், வேண்டும் (ending), మాత్రమే, ాలి (ending) | `kn:only`, `hi:at_least`, … |
| question | ಏನು ಯಾರು ಯಾವಾಗ …, क्या कौन कब …, என்ன யார் …, ఏమి ఎవరు … | `kn:what`, … |
| number | number words 1–10, 100, 1000, lakh, crore; units ಕೆಜಿ, किलो, கிலோ, కిలో … | the digits (`5`), or `unit:kg` |
| datetime | month names; today / tomorrow / yesterday | `month:3`, `day:+1`; Hindi कल is `day:+-1` (ambiguous) |
| entity | titles ಶ್ರೀ, श्री, திரு, శ్రీ …: the title **and the next word** | the next word (the name) |
| negation | gaps not in `negation.yaml` (ಬಾರದು, मना, கூடாது, కూడదు, …; Romanized *bedi*, *koodathu*, *nai*) | `kn:baaradu`, … |
| register | politeness and formality: ದಯವಿಟ್ಟು, ನೀವು/ನೀನು, कृपया, आप/तुम/तू, जी, தயவுசெய்து, நீங்கள்/நீ, దయచేసి, మీరు/నువ్వు, గారు; English *please*, *kindly* | not a detail; see the status rules |

Match types are `word`, `suffix` (endings), `substring` and `phrase` (multi-word, matched before single words). Inflected forms are often not matched; for example, Telugu కిలోల is not matched by కిలో.

Script variants (Feature 6) and transliteration ignore these markers: they are words of one script, and a script change keeps the word.

## Status rules

1. **changed** — any (category, key) count differs between original and candidate
   (missing, added, or altered = missing + added).
2. **at_risk** — no count differs, the texts differ beyond whitespace, and at least one of:
   - the order of money/datetime/number values changed;
   - the candidate is under 50% of the original length (originals ≥ 40 characters);
   - an `unreviewed` negation list was in effect **and the word content changed** (v3): letters,
     marks, digits and ZWJ/ZWNJ differ. Edits that only change spacing, repeated punctuation or
     invisible formatting characters cannot remove a negation word, so they are not flagged;
   - (v4) a review-data marker list of the language is pending and the word content changed;
   - (v4) a politeness or formality marker was removed or added; a lower count of a marker that is still present does not count;
   - (v4) language `auto` on code-mixed (Indic script and Latin) text with changed words;
   - (v4) language `auto` on Latin-only text that contains at least 2 distinct Romanized Kannada/Hindi/Tamil/Telugu list words, with changed words;
   - (v5) language `auto` on Latin-only text where the count of any Romanized Indic critical marker (from all four languages' lists) differs;
   - (v5) the count of an English opposite-pair word differs.
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

rules_v3 categories are **English / Latin script only**: Indic condition words (e.g. ಆದರೆ, अगर,
என்றால், అయితే), Indic constraint words and Indic names are not detected; they need
native-speaker word lists. The entity rule is a heuristic: it misses lower-case names and
flags capitalised ordinary words in title-case text (protective only — such words are kept).

Units outside the closed Latin list, and units written in Indic scripts, are not compared; numbers written as words;
Indic-script month names, dates and scale words (ಲಕ್ಷ, लाख, …);
Indic currency words (ರೂಪಾಯಿ, रुपये, …) are not money (their digits are still checked as numbers);
`1,5` is read as `15` (comma = grouping); date formats are not cross-matched
(`12/01/2026` vs `2026-01-12` → changed); paraphrases that reverse meaning without a listed
negation word are not caught.

Planned fixes, with priorities, are tracked in `docs/backlog/feature5_meaning_check.md`
(B5-1 partly and B5-13 done in `rules_v2`; the rest not started).
