# Token minimization evaluation on FLORES-200 (opt_rules_v3 + rules_v5)

Run `opt_eval_20261121T050911Z` · script `research/scripts/run_optimizer_eval.py` · files in
`research/reports/opt_eval_20261121T050911Z/` (`run.json`, `summary.csv`, `rows.csv.gz`; no sentence text).

**What this measures:** how many tokens the REDUTAX rule-based optimizer removes, under the
public `cl100k_base` and `o200k_base` encodings (tiktoken 0.14.0), and whether the rule-based
meaning check finds every critical detail intact.

**What it does not measure:**
- provider billing (token counts are tokenizer estimates);
- model understanding or answer quality;
- semantic equivalence (the meaning check compares critical details only).

**Data:** FLORES-200 devtest, version 2022-07-14. It provides 1,012 aligned sentences in each of English, Kannada, Hindi, Tamil and Telugu, all native script (5,060 samples). FLORES is approved for evaluation only, under CC BY-SA 4.0; it was not used for training and is not a tokenizer vocabulary.

Code state: commit `9abd1de` plus the uncommitted opt_rules_v3 / rules_v5 changes (`working_tree_dirty: true` in `run.json`). This run replaces the rules_v4 run (`opt_eval_20261121T034128Z`) and the first run (`opt_eval_20261121T004144Z`, opt_rules_v2 / rules_v3); see "Changes since the rules_v4 run" below. Four English register markers (`en-reg-003` … `006`) were added to the review data after this run started; none of their phrases occurs in the 5,060 FLORES samples or in the prompt template, so they cannot change any row.

## Conditions

- **natural** — each sentence exactly as stored.
- **prompt_clean / prompt_noisy** — a synthetic prompt template written by the developers. It has an English instruction ("Summarise the text below in one sentence.") followed by the native-script sentence.
  - The noisy form adds only lossless noise:
    - leading and trailing spaces;
    - 4 blank lines and a 10-character `----------` separator;
    - one zero-width space;
    - every third word gap doubled;
    - the instruction repeated at the end.
  - It is **not** real user data. It shows how much removable redundancy the optimizer actually removes.

Every count uses the same encoding for the input and the output.
- `noise removed` = (noisy tokens before − noisy tokens after) ÷ (noisy tokens before − optimized clean prompt tokens).
- `recovered` = the noisy prompt ends at or below the optimized clean prompt.

## Results

### Natural FLORES-200 sentences (1,012 per language), same result in all three modes

| Language | cl100k_base before → after | reduction | o200k_base before → after | reduction | sentences changed | details kept | meaning check |
|---|---|---|---|---|---|---|---|
| English | 27,182 → 27,181 | 0.004% | 26,873 → 26,872 | 0.004% | 1 | 1012/1012 | 1012 preserved, 0 changed |
| Kannada | 240,818 → 240,400 | 0.174% | 52,975 → 52,558 | 0.787% | 238 | 1012/1012 | 1012 preserved, 0 changed |
| Hindi | 129,364 → 129,345 | 0.015% | 42,292 → 42,273 | 0.045% | 19 | 1012/1012 | 1012 preserved, 0 changed |
| Tamil | 207,772 → 207,693 | 0.038% | 53,199 → 53,118 | 0.152% | 73 | 1012/1012 | 1012 preserved, 0 changed |
| Telugu | 225,286 → 225,025 | 0.116% | 51,863 → 51,600 | 0.507% | 159 | 1012/1012 | 1012 preserved, 0 changed |

### Synthetic noisy prompts

| Language | Mode | cl100k_base reduction | o200k_base reduction | noise removed (cl100k / o200k) | recovered to clean (cl100k / o200k) | details kept | meaning check (o200k rows) |
|---|---|---|---|---|---|---|---|
| English | safe | 17.73% | 17.83% | 50.4% / 50.42% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| English | balanced | 17.73% | 17.83% | 50.4% / 50.42% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Kannada | safe | 3.32% | 10.82% | 46.77% / 46.72% | 1 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Kannada | balanced | 3.32% | 10.82% | 46.77% / 46.72% | 1 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Hindi | safe | 7.09% | 15.95% | 51.52% / 54.0% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Hindi | balanced | 7.09% | 15.95% | 51.52% / 54.0% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Tamil | safe | 3.62% | 10.34% | 45.0% / 44.99% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Tamil | balanced | 3.62% | 10.34% | 45.0% / 44.99% | 0 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Telugu | safe | 3.43% | 10.68% | 45.31% / 45.3% | 1 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |
| Telugu | balanced | 3.43% | 10.68% | 45.31% / 45.3% | 1 / 0 of 1012 | 1012/1012 | 1012 preserved, 0 at_risk, 0 changed |

Aggressive mode applies exactly what balanced mode applies. Its extra outputs are suggestions only, never applied. Summed over the three conditions under o200k_base:

| Language | Suggestions (aggressive, o200k_base, all conditions) | of which in balanced mode |
|---|---|---|
| Kannada | 1181 | 1012 |
| Telugu | 1084 | 1012 |
| English | 1024 | 1012 |
| Hindi | 1014 | 1012 |
| Tamil | 1012 | 1012 |

The 1,012 balanced-mode suggestions per language are the repeated instruction in each noisy prompt (one per prompt).

Across all 91,080 measured rows:

| Measure | Result |
|---|---|
| Token increases | 0 |
| Meaning check "changed" | 0 |
| Critical-detail counts unchanged | 91,080 / 91,080 |

## Reading the results

1. **Natural text gains almost nothing, by design.** FLORES sentences are clean edited prose; the only removable redundancy is stray whitespace (mostly in the Kannada and Telugu files). The rules don't paraphrase, so on natural Indic text the large token gap against English (see `BENCHMARK_FLORES200_BASELINE.md`) stays: it comes from how the encodings split the scripts.
2. **About half of the injected noise is removed automatically, in safe and balanced mode alike (45–54%).** The other half is the repeated instruction "Summarise the text below in **one** sentence.". Under `rules_v5` "one" is a number, and a repeat that holds a number is offered as a suggestion that needs approval, not removed (the same rule as for repeated digits, opt_rules_v2). If the user approves it, the earlier 97–99% recovery is reached. The rules_v4 figure of 97–99% *automatic* removal is withdrawn: it depended on the number word not being detected.
3. **The same edit saves very different amounts depending on the encoding.**
   - Under cl100k_base an Indic sentence already costs so many tokens that the removed noise is a small share: about 3.3–3.6% for Kannada, Tamil and Telugu, 7.1% for Hindi (automatic edits).
   - Under o200k_base it is about 10.3–16.0%.
   - The absolute number of tokens removed is similar under both encodings.
4. **No noisy prompt is recovered to the clean prompt automatically** (0–1 of 1,012 per language), because the repeated instruction now waits for approval.
   - Besides that repeat, the gap is mostly one token per prompt, for example a trailing newline.
   - Some edits are skipped because they save no token under one of the selected encodings; an edit must not add tokens under any of them.
   - Several whitespace runs, like `\n\n\n\n\n` and `----------`, are single tokens in these encodings, so shortening them saves nothing and is correctly not done.
5. **All noisy-prompt rows are now `preserved`.** Under rules_v4, balanced-mode Indic rows were `at_risk` because removing the repeated instruction changed the word content while the Indic lists were unreviewed. Now that removal is a suggestion, only formatting is applied, so no words change. No detail count changed in any row.
6. **The extra metric does not change the comparison with the Phase 1 baseline.**
   - The Phase 1 benchmark (`20261120T214425Z`) counts the *normalized* text (`nfc_ws_v1`, whitespace collapsed). This evaluation counts the *exact* text, so the Indic "before" totals differ from that report. English is identical (27,182 / 26,873).
   - Example: Kannada cl100k_base is 240,818 exact, 240,400 after optimization and 240,364 normalized.
7. **Two English noisy prompts save one token less in safe mode** (`flores-devtest-0565-en`, `-0610-en`). The noise doubled the space inside "two  million" / "seven  million"; that span is now a protected number, so the whitespace edit inside it is not applied. This is deliberately conservative.

## Changes since the rules_v4 run (`034128Z` → `050911Z`)

| Item | rules_v4 | rules_v5 |
|---|---|---|
| Summary rows that differ | — | 22 of 90, all `prompt_noisy` |
| Natural sentences (all languages, modes, encodings) | — | identical |
| Noisy prompts, balanced: noise removed automatically (o200k_base) | 97.56–99.46% | 44.99–54.0% (+1 approval-required suggestion per prompt) |
| Noisy prompts, balanced: total reduction (o200k_base) | 22.5–35.0% | 10.3–17.8% |
| Noisy prompts, balanced Indic meaning check | 1012 at_risk per language | 1012 preserved per language |
| English noisy, safe | 17.736% / 17.832% | 17.733% / 17.828% (two prompts, see point 7) |
| Token increases / `changed` / details kept | 0 / 0 / 91,080 of 91,080 | 0 / 0 / 91,080 of 91,080 |

## Changes since the first run (opt_rules_v2 / rules_v3 → opt_rules_v3 / rules_v4)

- **Natural sentences:** identical results (every number in the first table is unchanged).
- **Noisy prompts, balanced mode:** recovery is equal or higher in every language. The table shows the new values; the first run had Kannada 952 / 952, Hindi 620 / 954, Tamil 935 / 935, Telugu 929 / 929 and English 916 / 922.
  - During this milestone the new Indic word lists first *lowered* recovery: Kannada fell to 908 of 1012. Spaces inside multi-word markers or after titles, and zero-width spaces inside newly detected words, were being protected or misread as added details.
  - Three fixes, each with regression tests, brought it back:
    1. invisible characters are ignored when matching words;
    2. spacing fixes are allowed inside condition, constraint, name and negation spans;
    3. invisible-character fixes are allowed inside detected words. Quoted text, code, URLs, money and protected terms stay fully protected.
- **Aggressive mode:** 2 additional Hindi suggestions (pending native-speaker wording entries), never applied.

## Compared with opt_rules_v1 (audit run on the same data, before this milestone)

| Natural sentences, o200k_base | opt_rules_v1 | opt_rules_v2 |
|---|---|---|
| English | 0.004% | 0.004% |
| Kannada | 0.787% | 0.787% |
| Hindi | 0.043% (1 invisible-character fix left as suggestion) | 0.045% |
| Tamil | 0.139% (5 left as suggestions) | 0.152% |
| Telugu | 0.469% (18 left as suggestions) | 0.507% |
| Balanced vs safe | identical (no active rule) | balanced removes exact repeats |

v1 was not run on the synthetic prompts, so its noisy-prompt numbers are not available.

## Limitations

- The synthetic template and noise are developer-designed; real prompts will have other kinds and amounts of redundancy. Romanized and code-mixed text is not in FLORES and is covered only by unit tests with developer-written examples.
- The meaning check is rule-based (`rules_v5`). Indic condition, constraint, question, number, title and formality lists exist, but **all are pending native-speaker review**, as are the Indic negation lists.
- Token counts are encoding counts, not provider billing; hosted models may tokenize differently.

## Attribution and licence

Measurements derived from **FLORES-200** (NLLB Team, 2022, *No Language Left Behind: Scaling
Human-Centered Machine Translation*; `facebookresearch/flores`, archive `flores200_dataset.tar.gz`,
version 2022-07-14), licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
REDUTAX uses FLORES-200 for internal research and evaluation only. The source sentences are not
included in the outputs. If these derived files are shared, keep this attribution and the
CC BY-SA 4.0 share-alike terms.
