# Feature 5 improvement backlog (Meaning Preservation Checker)

Status: **B5-1 partly done and B5-13 done in `rules_v2`** (2026-11-21, regression tests in
`backend/tests/test_meaning.py`); every other item is **not started**. Each item, when done, bumps `METHOD_ID` (e.g. `rules_v2`) and updates
`research/configs/meaning_check.md` and `docs/STATUS.md`.

Priority: P1 = can silently pass a real meaning change; P2 = false alarms or narrower coverage;
P3 = optional extra layer.

| ID | Gap | Effect today | Proposed fix | Needs | Priority |
|---|---|---|---|---|---|
| B5-1 | **[rules_v2: partly done — Latin units only]** **Units after numbers** (`5 kg` → `5 g`, `10 GB` → `10 MB`, `2 km` → `2 m`) | Passes as `preserved` (number kept, unit not compared). *Found while writing this backlog; not previously reported.* | Attach a unit suffix from a closed list (SI + common: kg g mg km m cm mm l ml GB MB KB TB hr hrs min sec %, °C) to the number's key | Unit list review | P1 |
| B5-2 | Numbers written as words (`five`, `twenty-one`, `ಐದು`, `पाँच`) | Not detected; removing "five" passes | English number words first (0–99, hundred, thousand, lakh, crore, million) → numeric value; Indic number words only from native-reviewed lists | Native-speaker lists for kn/hi/ta/te | P1 |
| B5-3 | Indic-script scale words (`ಲಕ್ಷ`, `ಕೋಟಿ`, `लाख`, `करोड़`, `இலட்சம்`, `கோடி`, `లక్ష`, `కోటి`) | `೫ ಲಕ್ಷ` → `೫` passes (digit kept) | Treat as scale suffix like Latin `lakh` | Native-speaker review | P1 |
| B5-4 | Antonym swaps without a negation word (`allow` → `forbid`, `before` → `after`, `increase` → `decrease`) | Passes | Small closed list of high-risk opposite pairs, flag as `at_risk` when one side changes (cannot be exhaustive) | List review; evaluation set (B5-9) to measure false alarms | P1 |
| B5-5 | Indic currency words (`ರೂಪಾಯಿ`, `रुपये`, `ரூபாய்`, `రూపాయి`) | Digits checked as numbers, currency not compared (`೫೦೦ ರೂಪಾಯಿ` → `೫೦೦ ಡಾಲರ್` passes) | Add to money suffix list | Native-speaker review | P2 |
| B5-6 | Indic month names and date words (`ಜನವರಿ`, `जनवरी`, `ஜனவரி`, `జనవరి`, `ನಾಳೆ`/`कल`) | Not detected as dates | Month-name lists per language; relative-day words as a separate `datetime` key | Native-speaker review | P2 |
| B5-7 | Same date in two formats (`12/01/2026` vs `2026-01-12`) | False `changed` | Parse unambiguous formats to ISO; `dd/mm` vs `mm/dd` needs a locale setting (default dd/mm for India) — ambiguous cases stay as-is | Team decision on default locale | P2 |
| B5-8 | Decimal comma (`1,5` read as `15`) | False `changed` / missed change in European-style text | Optional `number_locale` request field | Decision whether needed at all | P3 |
| B5-9 | **No measured accuracy** | Precision/recall of the checker unknown | Labelled evaluation set: original/rewrite pairs per language with human labels (preserved / changed), report detection rates per category | Team-written, native-reviewed pairs | P1 (prerequisite for claiming any accuracy) |
| B5-10 | Native-speaker review of Indic negation lists | Indic edits always `at_risk` | Team review of `backend/app/core/lexicons/negation.yaml`, then mark `reviewed` | Native speakers | P1 (process) |
| B5-11 | Semantic similarity layer | Paraphrase-level changes not caught | Optional local multilingual embedding model (free; large download; licence to verify); can only add `at_risk`, never downgrade `changed` | Model choice + licence check + calibration on B5-9 | P3 |
| B5-13 | **[rules_v2: done]** Standalone forms of `suffix` negation entries (Romanized Kannada `illa` as its own word, e.g. "hesaru haaki illa") | Not detected: `suffix` matching requires the token to be longer than the form. *Found while writing Feature 3 tests.* | Add matching `word` entries (e.g. `illa`, `illai`, `ledu`) or let `suffix` also match the bare form | Native-speaker review (lists are unreviewed) | P1 |
| B5-12 | LLM judge | — | Optional second opinion | **Paid API: needs explicit approval** | P3 |

Rules for working this backlog: one item at a time, with tests; no item is marked done until its
tests pass; no accuracy number is published before B5-9 exists.
