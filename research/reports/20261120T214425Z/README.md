# Benchmark run 20261120T214425Z

Output of `research/scripts/run_benchmark.py` for the first stored REDUTAX baseline. Write-up:
[`research/BENCHMARK_FLORES200_BASELINE.md`](../../BENCHMARK_FLORES200_BASELINE.md).

| File | Content |
|---|---|
| `run.json` | Run metadata: dataset and version, input file SHA-256, tokenizer versions, normalization and word-count policy IDs, code commit |
| `rows.csv` | One row per sample × tokenizer (10,120): sample and aligned-group IDs, language, script, token / word / character counts, tokens per word. **No sentence text.** |
| `summary.csv` | Per tokenizer × language: totals, mean/median/stdev tokens per word, 95% CI, ratio vs English |

## Attribution and licence

These are measurements derived from **FLORES-200** (NLLB Team, 2022, *No Language Left Behind:
Scaling Human-Centered Machine Translation*; `facebookresearch/flores`, archive
`flores200_dataset.tar.gz`, version 2022-07-14), licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). REDUTAX uses FLORES-200 for
internal research and evaluation only. The source sentences are not included here; if these
derived files are shared, keep this attribution and the CC BY-SA 4.0 share-alike terms.

Token counts are exact counts under tiktoken 0.14.0 `cl100k_base` / `o200k_base`. They are not
API billing figures and say nothing about translation quality or model comprehension.
