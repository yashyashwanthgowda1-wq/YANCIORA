# Verbose-prompt test set v1

`verbose_prompts_v1.jsonl`: 100 prompts (20 each for English, Kannada, Hindi, Tamil and Telugu; each Indic language has 16 native-script and 4 Romanized/code-mixed prompts), built by `build_verbose_prompts.py`.

- **Provenance:** synthetic, AI-drafted (`provenance: synthetic_ai_drafted`), `review_status: pending_review`. Not real user prompts, not native-speaker reviewed, no personal data.
- **Purpose:** test whether the optimizer removes deliberate redundancy without losing critical details. The `repeat` field records the redundancy by construction (`exact`, `near`, `none`).
- Do not report results on this set as real-world savings. Keep them separate from FLORES-200 and the everyday-prompt set.
- Rebuild: `python research/datasets/verbose_prompts/build_verbose_prompts.py`. Evaluation: `research/PROMPT_EVAL_VERBOSE_V1.md`.
