# Optimizer evaluation run opt_eval_20261121T034128Z

Output of `research/scripts/run_optimizer_eval.py` (opt_rules_v3 optimizer, rules_v4 meaning
check) on FLORES-200 devtest. Write-up: [`research/OPTIMIZER_EVAL_FLORES200.md`](../../OPTIMIZER_EVAL_FLORES200.md).

| File | Content |
|---|---|
| `run.json` | Run metadata: optimizer and meaning-check method ids, tokenizer versions, dataset version, licence and approved use, input SHA-256, the prompt templates, code commit, elapsed time |
| `rows.csv.gz` | One row per sample × mode × condition × tokenizer (91,080): token counts before/after, characters, accepted edits, suggestions, meaning status, detail check, noise removed, recovery, rules applied. **No sentence text.** |
| `summary.csv` | Per language × mode × condition × tokenizer: totals, total/mean/median reduction %, changed/increase counts, meaning statuses, details kept, suggestions, noise removed %, recovered |

Token counts are tokenizer counts (same encoding before and after), not provider billing.

## Attribution and licence

Measurements derived from **FLORES-200** (NLLB Team, 2022; `facebookresearch/flores`, version
2022-07-14), licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
Used for internal research and evaluation only; the source sentences are not included. Keep this
attribution and the share-alike terms if these derived files are shared.
