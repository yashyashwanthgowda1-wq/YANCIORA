# Verbose-prompt evaluation (synthetic set v1) — optimizer opt_rules_v4

Run `prompt_eval_20261121T073018Z` · script `research/scripts/run_prompt_eval.py --input research/datasets/verbose_prompts/verbose_prompts_v1.jsonl` · files in `research/reports/prompt_eval_20261121T073018Z/`. Optimizer `opt_rules_v4`, meaning check `rules_v5`, tiktoken 0.14.0. Same encoding before and after every comparison; token counts are tokenizer counts, not provider billing.

## What the data is

- 100 prompts: 20 English, and 20 each for Kannada, Hindi, Tamil and Telugu (16 native script + 4 Romanized / code-mixed). Built by `research/datasets/verbose_prompts/build_verbose_prompts.py` from small sentence banks.
- **Synthetic, AI-drafted, `pending_review`.** Not real user prompts, not native-speaker reviewed. The redundancy is deliberate and known by construction: half the native prompts repeat one instruction word for word, a quarter repeat it in other words (not removable by exact-repeat rules), a quarter have no repeat. English prompts also contain wordy phrases. Results show what the engine does on deliberately verbose text; they are **not** real-world savings.
- Romanized prompts also ran with language `auto`; those rows are in `rows.csv` and omitted below.

## What changed in the engine (decision D64, approved by the project owner 2026-11-21)

1. **English wording rules are active** in balanced and aggressive mode: 76 rules in `backend/app/optimizer/phrases/en.yaml` (wordy connectives, verb phrases such as "conduct an analysis of" → "analyze", redundant pairs, empty openers). Every edit must save tokens under every selected encoding and pass the meaning check, or it is rejected. Rules that remove politeness ("could you please", "I would like you to") or add an opposite-pair word ("prior to" → "before") are only ever suggestions. `backend/tests/test_english_rules_v2.py` runs every rule in a sentence holding a negation, a number and a name.
2. **Repeated instructions that hold details are removed in balanced mode** when every detail value is still in the remaining copy. The result is reported `at_risk` (never `preserved`) with the removed details named. Safe mode still only suggests them. Repeats are matched ignoring case, whitespace and sentence-end punctuation; short repeats ("Hello!") are removed only inside running text, never back to back ("Hurry. Hurry.") or on their own line (list items).
3. **Politeness is checked by count for wording edits**: removing a politeness or request phrase is a suggestion even if another copy remains elsewhere (bug found in the browser test).
4. **Indic wording is unchanged by policy**: the 399 review entries stay `pending_review` and inactive. Kannada, Hindi, Tamil and Telugu text is shortened automatically only by formatting and repeat removal; pending wording appears as aggressive-mode suggestions, and "Select all" in the UI builds one combined alternative for the user to approve.

## Results (Romanized rows with the language given)

| Group | Mode | n | Unchanged | Mean / median saving, cl100k_base | Mean / median saving, o200k_base | Tokens o200k before → after | Token increases | Meaning P / R / C | Needs approval |
|---|---|---|---|---|---|---|---|---|---|
| en_verbose | safe | 20 | 65% | 2.39% / 0.00% | 2.41% / 0.00% | 1,672 → 1,630 | 0 | 20 / 0 / 0 | 10 |
| en_verbose | balanced | 20 | 0% | 16.57% / 16.64% | 16.85% / 17.05% | 1,672 → 1,391 | 0 | 10 / 10 / 0 | 7 |
| en_verbose | aggressive | 20 | 0% | 16.57% / 16.64% | 16.85% / 17.05% | 1,672 → 1,391 | 0 | 10 / 10 / 0 | 7 |
| hi_roman | safe | 4 | 25% | 4.53% / 3.34% | 4.76% / 3.65% | 124 → 118 | 0 | 4 / 0 / 0 | 3 |
| hi_roman | balanced | 4 | 0% | 23.33% / 28.21% | 23.66% / 28.25% | 124 → 93 | 0 | 1 / 3 / 0 | 0 |
| hi_roman | aggressive | 4 | 0% | 23.33% / 28.21% | 23.66% / 28.25% | 124 → 93 | 0 | 1 / 3 / 0 | 0 |
| hi_verbose | safe | 16 | 50% | 0.82% / 0.00% | 2.73% / 0.51% | 1,373 → 1,334 | 0 | 16 / 0 / 0 | 8 |
| hi_verbose | balanced | 16 | 25% | 6.32% / 6.24% | 8.00% / 7.83% | 1,373 → 1,265 | 0 | 8 / 8 / 0 | 0 |
| hi_verbose | aggressive | 16 | 25% | 6.32% / 6.24% | 8.00% / 7.83% | 1,373 → 1,265 | 0 | 8 / 8 / 0 | 0 |
| kn_roman | safe | 4 | 25% | 3.91% / 3.05% | 4.28% / 3.56% | 134 → 128 | 0 | 4 / 0 / 0 | 2 |
| kn_roman | balanced | 4 | 0% | 17.64% / 15.95% | 18.07% / 17.00% | 134 → 107 | 0 | 2 / 2 / 0 | 0 |
| kn_roman | aggressive | 4 | 0% | 17.64% / 15.95% | 18.07% / 17.00% | 134 → 107 | 0 | 2 / 2 / 0 | 0 |
| kn_verbose | safe | 16 | 62% | 0.46% / 0.00% | 2.06% / 0.00% | 1,634 → 1,599 | 0 | 16 / 0 / 0 | 8 |
| kn_verbose | balanced | 16 | 31% | 6.38% / 6.18% | 7.78% / 6.53% | 1,634 → 1,508 | 0 | 8 / 8 / 0 | 0 |
| kn_verbose | aggressive | 16 | 31% | 6.38% / 6.18% | 7.78% / 6.53% | 1,634 → 1,508 | 0 | 8 / 8 / 0 | 5 |
| ta_roman | safe | 4 | 25% | 3.72% / 2.68% | 3.81% / 2.86% | 148 → 142 | 0 | 4 / 0 / 0 | 2 |
| ta_roman | balanced | 4 | 0% | 17.23% / 15.71% | 16.91% / 15.76% | 148 → 122 | 0 | 2 / 2 / 0 | 0 |
| ta_roman | aggressive | 4 | 0% | 17.23% / 15.71% | 16.91% / 15.76% | 148 → 122 | 0 | 2 / 2 / 0 | 0 |
| ta_verbose | safe | 16 | 62% | 0.50% / 0.00% | 1.97% / 0.00% | 1,677 → 1,642 | 0 | 16 / 0 / 0 | 8 |
| ta_verbose | balanced | 16 | 31% | 6.79% / 5.76% | 7.94% / 7.77% | 1,677 → 1,544 | 0 | 8 / 8 / 0 | 0 |
| ta_verbose | aggressive | 16 | 31% | 6.79% / 5.76% | 7.94% / 7.77% | 1,677 → 1,544 | 0 | 8 / 8 / 0 | 0 |
| te_roman | safe | 4 | 25% | 3.62% / 2.98% | 4.22% / 3.17% | 139 → 133 | 0 | 4 / 0 / 0 | 2 |
| te_roman | balanced | 4 | 0% | 16.96% / 15.50% | 16.95% / 14.95% | 139 → 114 | 0 | 2 / 2 / 0 | 0 |
| te_roman | aggressive | 4 | 0% | 16.96% / 15.50% | 16.95% / 14.95% | 139 → 114 | 0 | 2 / 2 / 0 | 0 |
| te_verbose | safe | 16 | 62% | 0.46% / 0.00% | 1.89% / 0.00% | 1,783 → 1,748 | 0 | 16 / 0 / 0 | 8 |
| te_verbose | balanced | 16 | 31% | 6.16% / 5.71% | 8.09% / 7.93% | 1,783 → 1,640 | 0 | 8 / 8 / 0 | 0 |
| te_verbose | aggressive | 16 | 31% | 6.16% / 5.71% | 8.09% / 7.93% | 1,783 → 1,640 | 0 | 8 / 8 / 0 | 0 |

Across all 348 runs (116 prompt runs × 3 modes, including `auto`) and both encodings: **0 token increases, 0 `changed` verdicts**. An independent check over the 300 language-given runs found **0 critical-detail values lost or added** (counts drop only where repeats were removed), and the output kept the input's script in 300/300.

Aggressive mode applies exactly what balanced applies; its extra output is suggestions. Savings from approving them ("Select all") are not included above.

## Before → after (balanced, o200k_base)

| Prompt | Before | After | Tokens |
|---|---|---|---|
| en_verbose-01 | "Hello! I would like you to help me … Please provide a summary of the attached quarterly sales report in a clear and concise manner. … Do not include any customer names. Format the output as a table with two columns. Do not include any customer names." | "Hello! I would like you to help me … Please summarize the attached quarterly sales report clearly and concisely. … Do not include any customer names. Format the output as a table with two columns." | 87 → 70 (19.5%) |
| kn_verbose-01 | "… ಗ್ರಾಹಕರ ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ.␣␣ಉತ್ತರವನ್ನು ಎರಡು ಕಾಲಮ್‌ಗಳ ಕೋಷ್ಟಕದಲ್ಲಿ ಕೊಡಿ.␣␣ಗ್ರಾಹಕರ ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ." | "… ಗ್ರಾಹಕರ ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ. ಉತ್ತರವನ್ನು ಎರಡು ಕಾಲಮ್‌ಗಳ ಕೋಷ್ಟಕದಲ್ಲಿ ಕೊಡಿ." (negation kept once) | 112 → 95 (15.2%) |
| hi_verbose-01 | "… ग्राहकों के नाम शामिल न करें।␣␣उत्तर को दो कॉलम वाली तालिका में दें।␣␣ग्राहकों के नाम शामिल न करें।" | "… ग्राहकों के नाम शामिल न करें। उत्तर को दो कॉलम वाली तालिका में दें।" | 89 → 74 (16.9%) |
| ta_verbose-01 | "… வாடிக்கையாளர் பெயர்களை சேர்க்க வேண்டாம்.␣␣பதிலை இரண்டு நெடுவரிசை அட்டவணையாக கொடுங்கள்.␣␣வாடிக்கையாளர் பெயர்களை சேர்க்க வேண்டாம்." | "… வாடிக்கையாளர் பெயர்களை சேர்க்க வேண்டாம். பதிலை இரண்டு நெடுவரிசை அட்டவணையாக கொடுங்கள்." | 115 → 96 (16.5%) |
| te_verbose-01 | "… కస్టమర్ పేర్లను చేర్చవద్దు.␣␣సమాధానాన్ని రెండు నిలువు వరుసల పట్టికలో ఇవ్వండి.␣␣కస్టమర్ పేర్లను చేర్చవద్దు." | "… కస్టమర్ పేర్లను చేర్చవద్దు. సమాధానాన్ని రెండు నిలువు వరుసల పట్టికలో ఇవ్వండి." | 119 → 99 (16.8%) |
| hi_roman_verbose-01 | "Namaste!␣␣Is report ka summary do.␣␣Customer ke naam mat daalo.␣␣Customer ke naam mat daalo.␣␣Sirf Hindi mein jawab do." | "Namaste! Is report ka summary do. Customer ke naam mat daalo. Sirf Hindi mein jawab do." | 34 → 23 (32.4%) |

## Everyday-prompt set (earlier synthetic v1 set, balanced, run `prompt_eval_20261121T073031Z`)

| Group | Mode | n | Unchanged | Mean / median saving, cl100k_base | Mean / median saving, o200k_base | Tokens o200k before → after | Token increases | Meaning P / R / C | Needs approval |
|---|---|---|---|---|---|---|---|---|---|
| code_mixed | balanced | 10 | 90% | 0.20% / 0.00% | 0.45% / 0.00% | 201 → 200 | 0 | 10 / 0 / 0 | 0 |
| en | balanced | 10 | 70% | 6.80% / 0.00% | 6.80% / 0.00% | 175 → 161 | 0 | 8 / 2 / 0 | 0 |
| hi_native | balanced | 10 | 80% | 3.44% / 0.00% | 3.38% / 0.00% | 246 → 239 | 0 | 9 / 1 / 0 | 0 |
| hi_roman | balanced | 10 | 90% | 3.67% / 0.00% | 3.70% / 0.00% | 189 → 179 | 0 | 9 / 1 / 0 | 0 |
| kn_native | balanced | 10 | 70% | 5.62% / 0.00% | 6.00% / 0.00% | 320 → 299 | 0 | 8 / 2 / 0 | 0 |
| kn_roman | balanced | 10 | 90% | 3.23% / 0.00% | 3.33% / 0.00% | 183 → 173 | 0 | 9 / 1 / 0 | 0 |
| ta_native | balanced | 10 | 80% | 3.73% / 0.00% | 3.56% / 0.00% | 254 → 245 | 0 | 9 / 1 / 0 | 0 |
| ta_roman | balanced | 10 | 90% | 5.16% / 0.00% | 5.17% / 0.00% | 180 → 165 | 0 | 9 / 1 / 0 | 0 |
| te_native | balanced | 10 | 80% | 4.09% / 0.00% | 4.04% / 0.00% | 256 → 245 | 0 | 9 / 1 / 0 | 0 |
| te_roman | balanced | 10 | 90% | 5.19% / 0.00% | 5.20% / 0.00% | 177 → 164 | 0 | 9 / 1 / 0 | 0 |

On these short everyday prompts 70–90% stay unchanged: they contain little removable redundancy, which is the correct outcome.

## Browser acceptance (real UI, Optimize button)

`docs/integration/optimizer-acceptance/` (`accept.json`, screenshots, script): **23/23** at `http://127.0.0.1:3000`. That is 7 long prompts (English ~650 tokens, Kannada, Hindi, Tamil, Telugu, Romanized Kannada) × 3 modes, plus "Select all" in aggressive mode and the rewrite-editing workflow. Each check compared the prompt shown on the page with the backend's output and required fewer tokens in balanced/aggressive, the original script, no `changed` verdict, and the meaning-check line visible. The ~650-token English prompt (three copies of a verbose block) went 652 → 148 tokens under cl100k_base and 646 → 146 under o200k_base. It kept the 13 distinct instructions, every number, date and negation, and the politeness frame (offered only as a suggestion).

## Limitations

- Synthetic, AI-drafted data with redundancy added on purpose; real prompts will usually save less.
- Indic wording is never rewritten automatically: Indic savings come only from formatting and repeated sentences. Near-repeats (same instruction, different words) are not merged in any language.
- No LLM is configured, so there is no semantic paraphrasing; the engine is deterministic and rule-based.
- `at_risk` after repeat removal means "every value is still present once; the repetition may have been intentional emphasis". The meaning check is rule-based and is not proof of equal meaning.
- The English rules were approved in a working session by the project owner; a second reviewer is advisable.
