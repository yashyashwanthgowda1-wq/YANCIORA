# REDUTAX everyday-prompt evaluation set v1 (`prompts_v1.jsonl`)

100 short prompts of the kind people type into AI assistants:

| Variant | Prompts |
|---|---|
| Kannada, Hindi, Tamil and Telugu in native script | 10 each |
| Romanized Kannada, Hindi, Tamil and Telugu | 10 each |
| English–Indic code-mixed | 10 |
| English, as a reference | 10 |

The ten categories are education, programming, business communication, agriculture, travel, everyday questions, instructions, scheduling, summarization and AI-assistant prompts.

## Provenance

| Field | Value | Meaning |
|---|---|---|
| `provenance` | `synthetic_ai_drafted` | Every prompt was **written by an AI assistant (Claude) for this project** on 2026-11-21. None is a real user prompt, none was copied from a public dataset, and no private data is included. |
| `review_status` | `pending_review` | **No native speaker has checked these prompts.** Spelling, naturalness and Romanization conventions may be wrong. |

This set is therefore **synthetic test data**. It is not team-authored, not native-speaker-reviewed, and not a public research dataset. Results on it must be reported as such.

Some prompts deliberately contain redundancy that people really write:
- a repeated instruction;
- extra spaces;
- repeated punctuation;
- "brief summary" wording.

Others are clean, so the "no change" case is represented. The amount of redundancy was chosen by the drafter, so savings measured here are **not** an estimate of real-world savings.

## Fields

`id`, `variant` (`kn_native` … `te_roman`, `code_mixed`, `en`), `language`, `script`
(`Knda`, `Deva`, `Taml`, `Telu`, `Latn`, `mixed`), `category`, `text`, `provenance`, `review_status`.

## Using it

`research/scripts/run_prompt_eval.py` (results: `research/PROMPT_EVAL_SYNTHETIC_V1.md`).

## Licence

The text is original to the project, with no third-party content. The team still has to record its licence decision in `research/configs/datasets.yaml` (entry `REDUTAX-synthetic-prompts`, licence `TO_VERIFY`).

## Replacing it with reviewed data

To promote prompts to "native-speaker reviewed", a reviewer:
1. checks each prompt;
2. sets `review_status: reviewed` with their name;
3. corrects or rejects prompts that are unnatural.

Prompts written by team members should use `provenance: team_authored`, and must not include private user prompts without written consent.
