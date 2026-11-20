# Research workspace

Run scripts from the repo root with the backend installed (`pip install -e "backend[dev,research]"`).

| File | Purpose |
|---|---|
| `configs/datasets.yaml` | Licence register. Import is blocked until an entry is fully verified. |
| `configs/normalization.md` | Normalization, word-count and script-detection policy. |
| `scripts/flores_to_jsonl.py` | Converts a downloaded FLORES-200 release into sample rows. |
| `scripts/import_pilot.py` | Validates samples (schema, licence, duplicates, leakage) → `data/processed/`. |
| `scripts/run_benchmark.py` | Counts tokens per tokenizer → `reports/<run_id>/`. |

## Sample format (BRD §9.3)

JSONL or CSV with: `sample_id`, `language_code` (kn/hi/ta/te/en), `script`
(Knda/Deva/Taml/Telu/Latn/mixed), `text`, `aligned_group_id`, `domain`, `variant_type`
(original/translation/transliteration/code_mixed/paraphrase), `source_name`, `source_url`,
`license`, `split` (train/validation/test), `human_verified`, `quality_notes`.

Rows meaning the same thing share an `aligned_group_id`. A group must stay within one split.

## Outputs

- `data/processed/<dataset>/<version>/samples.jsonl` + `import_report.json`
- `reports/<run_id>/run.json` (dataset, file hash, tokenizer versions, policy IDs, commit),
  `rows.csv`, `summary.csv`, `ratio_chart.png`

Raw and processed data stay local (git-ignored). Trained tokenizer files go to object storage in Phase 2.

## Loading into PostgreSQL (optional flags)

Both flags need `DATABASE_URL` (see `.env.example`) and `alembic upgrade head` (from `backend/`).
Without the flags the scripts behave exactly as before and never touch the database.

```bash
# 1. Validate + write processed files + load samples into PostgreSQL (one transaction)
python research/scripts/import_pilot.py --input research/data/raw/flores200_devtest.jsonl \
    --dataset FLORES-200 --load-db

# 2. Benchmark + write report files + store the run in PostgreSQL
python research/scripts/run_benchmark.py \
    --input research/data/processed/FLORES-200/<version>/samples.jsonl --split test --store-db
```

Exit codes: `0` ok · `1` validation errors · `2` licence register blocked (or tokenizer
unavailable for the benchmark) · `3` database step failed and was rolled back (files are still written).

Rules enforced by the loader (`backend/app/services/dataset_store.py`):

- The licence register gate and full validation run again inside the loader, so an
  unverified dataset can never be written.
- Re-running the same import is safe: identical rows are counted as `unchanged`.
- A stored sample cannot change. Different content under the same `sample_id` is refused,
  and so is a changed licence/source/citation/access date for an imported `name@version`.
  Record a new `version` in `datasets.yaml` instead.
- No leakage against stored rows either: an aligned group stays in one split, and the same
  text cannot appear in two splits. A DB trigger enforces the aligned-group rule too.
- Each sample's licence must match the register entry; a missing row licence is filled from it.
- Every import is logged in `dataset_imports` (row counts, input SHA-256, commit).

`--store-db` requires the benchmarked samples to be loaded and unchanged (content hashes are
compared). It stores `benchmark_runs` (run ID, timestamp, dataset version, split, reference
language, normalization and word-count IDs, commit, input SHA-256, full `run.json` as `config`),
one `token_benchmarks` row per sample × tokenizer (token/word/char counts, fertility, count
status, tokenizer name/library/version), and `benchmark_summaries` (the same numbers as `summary.csv`).
