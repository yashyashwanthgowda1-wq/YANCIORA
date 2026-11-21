# Everyday-prompt evaluation (synthetic set v1)

Run `prompt_eval_20261121T051656Z` (current). Script: `research/scripts/run_prompt_eval.py`. Files: `research/reports/prompt_eval_20261121T051656Z/` (`run.json`, `summary.csv`, `rows.csv`, `examples.json`). Optimizer `opt_rules_v3`, meaning check **`rules_v5`**, tiktoken 0.14.0 (`cl100k_base`, `o200k_base`). The previous run under `rules_v4` (`prompt_eval_20261121T034113Z`) is kept for comparison; see *Changes since the rules_v4 run* below.

**Separate from the FLORES-200 evaluation** (`OPTIMIZER_EVAL_FLORES200.md`); the two are never combined into one savings figure.

## What the data is, and is not

- **Input:** `research/datasets/team_prompts/prompts_v1.jsonl`. It has 100 prompts:
  - 10 categories × Kannada, Hindi, Tamil and Telugu in native script;
  - the same four languages Romanized;
  - 10 English–Indic code-mixed prompts;
  - 10 English prompts.
- **Provenance:** every prompt is **synthetic, AI-drafted** (`provenance: synthetic_ai_drafted`) and **`pending_review`**. It is not team-authored, not native-speaker-reviewed, not a public dataset, and contains no real user prompts.
- **How it was run:** Romanized and code-mixed prompts ran twice: with the language given, and with language `auto`.
- **Same-encoding counts:** every number below compares the same encoding before and after.
- **What a reduction is:** a token reduction under that encoding. It is not a character reduction, and not provider billing.
- **Wording rules:** no Indic wording rule is active. All 399 review entries (Kannada 90, Hindi 113, Tamil 90, Telugu 89, English 17) are `pending_review`, so no rewrite is approved and **0 automatic wording rules** exist. The only automatic changes are lossless formatting and exact-repeat removal.

Columns:
- **Successful optimization:** the prompt changed, saved tokens, and the meaning check did not report `changed`, with every critical detail kept.
- **Needs approval:** the prompt has at least one suggestion.
- **Meaning check P / R / C:** preserved / at_risk / changed.

## Results — balanced mode (o200k_base for the rate columns)

| Group | Prompts | No change | Successful optimization | Mean / median / max reduction, cl100k_base | Mean / median / max reduction, o200k_base | Token increase | Edit rejected by meaning check | Needs approval | Meaning check P / R / C | Details kept |
|---|---|---|---|---|---|---|---|---|---|---|
| Kannada native | 10 | 80% | 20% | 0.15% / 0.00% / 0.76% | 0.79% / 0.00% / 4.35% | 0% | 0% | 20% | 10 / 0 / 0 | 100% |
| Hindi native | 10 | 90% | 10% | 0.15% / 0.00% / 1.47% | 0.39% / 0.00% / 3.85% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Tamil native | 10 | 90% | 10% | 0.08% / 0.00% / 0.85% | 0.36% / 0.00% / 3.57% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Telugu native | 10 | 90% | 10% | 0.08% / 0.00% / 0.79% | 0.33% / 0.00% / 3.33% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Kannada | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.33% / 0.00% / 3.33% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Hindi | 10 | 100% | 0% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Tamil | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.35% / 0.00% / 3.45% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Telugu | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.40% / 0.00% / 4.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized, language 'auto' (all 4) | 40 | 92% | 8% | 0.25% / 0.00% / 3.70% | 0.27% / 0.00% / 4.00% | 0% | 0% | 10% | 40 / 0 / 0 | 100% |
| Code-mixed (language given) | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| Code-mixed, language 'auto' | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| English (reference) | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.37% / 0.00% / 3.70% | 0% | 0% | 20% | 10 / 0 / 0 | 100% |

## Safe mode

| Group | Prompts | No change | Successful optimization | Mean / median / max reduction, cl100k_base | Mean / median / max reduction, o200k_base | Token increase | Edit rejected by meaning check | Needs approval | Meaning check P / R / C | Details kept |
|---|---|---|---|---|---|---|---|---|---|---|
| Kannada native | 10 | 80% | 20% | 0.15% / 0.00% / 0.76% | 0.79% / 0.00% / 4.35% | 0% | 0% | 20% | 10 / 0 / 0 | 100% |
| Hindi native | 10 | 90% | 10% | 0.15% / 0.00% / 1.47% | 0.39% / 0.00% / 3.85% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Tamil native | 10 | 90% | 10% | 0.08% / 0.00% / 0.85% | 0.36% / 0.00% / 3.57% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Telugu native | 10 | 90% | 10% | 0.08% / 0.00% / 0.79% | 0.33% / 0.00% / 3.33% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Kannada | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.33% / 0.00% / 3.33% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Hindi | 10 | 100% | 0% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Tamil | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.35% / 0.00% / 3.45% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Telugu | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.40% / 0.00% / 4.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized, language 'auto' (all 4) | 40 | 92% | 8% | 0.25% / 0.00% / 3.70% | 0.27% / 0.00% / 4.00% | 0% | 0% | 10% | 40 / 0 / 0 | 100% |
| Code-mixed (language given) | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| Code-mixed, language 'auto' | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| English (reference) | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.37% / 0.00% / 3.70% | 0% | 0% | 20% | 10 / 0 / 0 | 100% |

## Aggressive mode

Aggressive mode applies the same edits as balanced mode. It only adds suggestions, for example pending Indic wording entries.

| Group | Prompts | No change | Successful optimization | Mean / median / max reduction, cl100k_base | Mean / median / max reduction, o200k_base | Token increase | Edit rejected by meaning check | Needs approval | Meaning check P / R / C | Details kept |
|---|---|---|---|---|---|---|---|---|---|---|
| Kannada native | 10 | 80% | 20% | 0.15% / 0.00% / 0.76% | 0.79% / 0.00% / 4.35% | 0% | 0% | 30% | 10 / 0 / 0 | 100% |
| Hindi native | 10 | 90% | 10% | 0.15% / 0.00% / 1.47% | 0.39% / 0.00% / 3.85% | 0% | 0% | 30% | 10 / 0 / 0 | 100% |
| Tamil native | 10 | 90% | 10% | 0.08% / 0.00% / 0.85% | 0.36% / 0.00% / 3.57% | 0% | 0% | 30% | 10 / 0 / 0 | 100% |
| Telugu native | 10 | 90% | 10% | 0.08% / 0.00% / 0.79% | 0.33% / 0.00% / 3.33% | 0% | 0% | 30% | 10 / 0 / 0 | 100% |
| Romanized Kannada | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.33% / 0.00% / 3.33% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Hindi | 10 | 100% | 0% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Tamil | 10 | 90% | 10% | 0.32% / 0.00% / 3.23% | 0.35% / 0.00% / 3.45% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized Telugu | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.40% / 0.00% / 4.00% | 0% | 0% | 10% | 10 / 0 / 0 | 100% |
| Romanized, language 'auto' (all 4) | 40 | 92% | 8% | 0.25% / 0.00% / 3.70% | 0.27% / 0.00% / 4.00% | 0% | 0% | 10% | 40 / 0 / 0 | 100% |
| Code-mixed (language given) | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| Code-mixed, language 'auto' | 10 | 90% | 10% | 0.20% / 0.00% / 1.96% | 0.45% / 0.00% / 4.55% | 0% | 0% | 0% | 10 / 0 / 0 | 100% |
| English (reference) | 10 | 90% | 10% | 0.37% / 0.00% / 3.70% | 0.37% / 0.00% / 3.70% | 0% | 0% | 20% | 10 / 0 / 0 | 100% |

Totals across all 150 prompt runs:
- aggressive / cl100k_base: no change 91%, success 9%, mean 0.22%, median 0.00%, increase 0%, needs approval 15%, changed verdicts 0, details kept 100%
- aggressive / o200k_base: no change 91%, success 9%, mean 0.35%, median 0.00%, increase 0%, needs approval 15%, changed verdicts 0, details kept 100%
- balanced / cl100k_base: no change 91%, success 9%, mean 0.22%, median 0.00%, increase 0%, needs approval 10%, changed verdicts 0, details kept 100%
- balanced / o200k_base: no change 91%, success 9%, mean 0.35%, median 0.00%, increase 0%, needs approval 10%, changed verdicts 0, details kept 100%
- safe / cl100k_base: no change 91%, success 9%, mean 0.22%, median 0.00%, increase 0%, needs approval 10%, changed verdicts 0, details kept 100%
- safe / o200k_base: no change 91%, success 9%, mean 0.35%, median 0.00%, increase 0%, needs approval 10%, changed verdicts 0, details kept 100%

## Reading the results

1. **Most everyday prompts have nothing safe to remove:**
   - about 90% of prompts are returned unchanged in every group and mode;
   - when a change is made, it is lossless formatting (double spaces) worth 1 token;
   - mean savings are 0.33–0.79% under o200k_base and 0.08–0.15% under cl100k_base for native scripts;
   - Romanized prompts save about 0.3–0.4% under both encodings.
2. **Repeated instructions with a restriction stay for the user to decide.** In the native-script and language-given Romanized prompts, the repeated line contains a constraint or negation, so it is a reviewed **suggestion** (approval required), not an automatic edit. Examples:
   - "ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ." twice (ಮಾತ್ರ = only);
   - "हमेशा हिंदी में जवाब दें!!!" twice (हमेशा = always);
   - "…cheppakandi, vaddu." twice (vaddu = don't).
3. **Romanized text with language `auto` is now treated like text with the language given.**
   - Under `rules_v4`, two repeats holding a Romanized restriction were removed automatically when the language was left on `auto`: `hi_roman-10` ("hamesha …", *always*) and `kn_roman-07` ("sign maadade kalisabedi", *do not send without signing*). The second was even reported `preserved`.
   - Under `rules_v5` the meaning check looks for Romanized Kannada/Hindi/Tamil/Telugu negation, condition, constraint and number words from every language's pending list when no language is given. Both repeats are now **suggestions that need approval**, exactly as with the language set.
   - Setting the language is still recommended: the `auto` check cannot tell which language a Romanized word belongs to, so it can only ask for review, never confirm.
   - **Balanced mode now saves no more than safe mode on this set** (o200k_base mean 0.35% in both). Its only extra automatic savings were those two repeat removals.
4. **Safety results across all runs:** 0 token increases, 0 `changed` verdicts, and 100% of critical-detail counts unchanged.
5. **Pending wording entries appear only as aggressive-mode suggestions, never applied.** There are 8 on this set, in 2 of 10 prompts per native-script language, each with meaning status `at_risk` and approval required:

   | Language | Original → proposed |
   |---|---|
   | Kannada | ಈ ಕೆಳಗಿನ → ಕೆಳಗಿನ |
   | Kannada | ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಸಾರಾಂಶ → ಸಾರಾಂಶ |
   | Hindi | कृपया करके → कृपया |
   | Hindi | संक्षेप में सारांश → सारांश |
   | Tamil | கீழே கொடுக்கப்பட்டுள்ள → கீழுள்ள |
   | Tamil | சுருக்கமாக சுருக்கம் → சுருக்கம் |
   | Telugu | కింద ఇచ్చిన → కింది |
   | Telugu | క్లుప్తంగా సారాంశం → సారాంశం |

   That is why "needs approval" rises from 10–20% to 30% in aggressive mode.
6. **The evidence does not support wording-level savings in Kannada, Hindi, Tamil or Telugu yet.** Those need approved review entries, measured afterwards.

## Examples (from `examples.json`)

| Prompt | Original | Result | Why |
|---|---|---|---|
| kn_native-02 | "… ಕೋಡ್ ಮಾತ್ರ ಕೊಡಿ.␣␣ವಿವರಣೆ ಬೇಡ." | double space removed (o200k_base 28 → 27) | lossless formatting; negation ಬೇಡ and constraint ಮಾತ್ರ untouched |
| hi_native-08 | "… तय करो और␣␣␣सबको याद दिला देना।" | spaces fixed (26 → 25) | lossless |
| kn_native-10 | "… ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ. ಕನ್ನಡದಲ್ಲಿ ಮಾತ್ರ ಉತ್ತರಿಸಿ." | repeat **suggested**, not removed | holds the constraint ಮಾತ್ರ (only) |
| te_roman-07 | "password evariki cheppakandi, vaddu.␣␣␣password …, vaddu." | spaces fixed; repeat **suggested** | holds the negation *vaddu* |
| hi_roman-10 (`auto`) | "… hamesha hindi mein jawab dijiye. hamesha hindi mein jawab dijiye." | repeat **suggested**, not removed (was removed under `rules_v4`, 27 → 17) | holds the constraint *hamesha* (always), now detected without the language |
| kn_roman-07 (`auto`) | "… sign maadade kalisabedi.␣␣␣sign maadade kalisabedi." | spaces fixed (o200k_base 30 → 29); repeat **suggested** (was removed and reported `preserved` under `rules_v4`) | holds the negation *-bedi* (don't) |
| en-07 | "… Do not send it without signing.␣␣Do not send it without signing." | spaces fixed; repeat **suggested** | holds negation |

Rejections by the adversarial suite (`backend/tests/test_indic_adversarial.py`, 72 tests), which uses the same check:

| Rewrite | Verdict |
|---|---|
| "कल रिपोर्ट मत भेजो।" → "कल रिपोर्ट भेजो।" | **changed** (negation) |
| "ಮಳೆ ಬಂದರೆ ಮನೆಯಲ್ಲಿ ಇರಿ." → "ಮಳೆ ಬಂತು ಮನೆಯಲ್ಲಿ ಇರಿ." | **changed** (condition) |
| "இரண்டு கிலோ" → "மூன்று கிலோ" | **changed** (number word) |
| "శ్రీ రావు గారికి" → "శ్రీ రెడ్డి గారికి" | **changed** (name after a title) |
| "आप कल आइए।" → "तुम कल आओ।" | **at_risk** (formality) |

## Changes since the rules_v4 run

| Item | `rules_v4` run (034113Z) | `rules_v5` run (051656Z) |
|---|---|---|
| Rows that differ | — | 8 of 600 (2 prompts × 2 modes × 2 encodings), all with language `auto` |
| Romanized `auto`, balanced, o200k_base: mean / max reduction | 1.95% / 37.04% | 0.27% / 4.00% |
| Repeats holding a Romanized restriction removed automatically | 2 | **0** |
| Balanced totals, o200k_base: no change / mean | 90% / 0.80% | 91% / 0.35% |
| Token increases, `changed` verdicts, details kept | 0 / 0 / 100% | 0 / 0 / 100% |

The earlier 33–37% maximum for Romanized `auto` came from these two automatic removals and is withdrawn.

## Limitations

- **The data is synthetic and AI-drafted.** Real prompts may contain more or less redundancy, other spellings, and longer texts.
- **All Indic word lists are pending native-speaker review.** Detection gaps were found during this run and fixed as pending entries:
  - Romanized Kannada endings such as "kalisabedi";
  - Romanized Hindi "hamesha".

  More gaps certainly remain, and inflected forms are often not matched.
- **The meaning check is rule-based.** It compares critical details and politeness markers; `preserved` is not proof of equal meaning.
- **Token counts are tokenizer estimates.** They are not hosted-model billing.
