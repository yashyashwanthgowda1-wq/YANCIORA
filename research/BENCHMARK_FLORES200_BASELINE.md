# Baseline tokenizer benchmark — FLORES-200 devtest (run `20261120T214425Z`)

First stored REDUTAX benchmark. Measured on 2026-11-21 (IST; `run_at` 2026-11-20T21:44:25Z UTC),
stored in PostgreSQL (Neon, production branch) and shown on the Research Dashboard.

**What this is:** exact token counts of meaning-aligned sentences under two public tiktoken
encodings. **What this is not:** a measure of translation quality, model comprehension, or API
billing. Fewer tokens does not mean better understanding; these encodings are baselines and no
claim is made about which hosted model uses which encoding or what a provider bills.

**Attribution:** measurements derived from FLORES-200 (NLLB Team, 2022, *No Language Left Behind:
Scaling Human-Centered Machine Translation*), licensed CC BY-SA 4.0. No FLORES sentence text is
reproduced here or in `research/reports/20261120T214425Z/`.

## Setup

| Item | Value |
|---|---|
| Dataset | FLORES-200, version `2022-07-14` (`flores200_dataset.tar.gz`, SHA-256 `b8b0b767…`), official `devtest` split (REDUTAX split `test`) |
| Licence / use | CC BY-SA 4.0; approved 2026-11-21 for internal research and evaluation only (`research/configs/datasets.yaml`) |
| Languages | English (eng_Latn), Hindi (hin_Deva), Kannada (kan_Knda), Tamil (tam_Taml), Telugu (tel_Telu) |
| Samples | 1,012 aligned sentence groups × 5 languages = 5,060 sentences (every group has all 5) |
| Tokenizers | tiktoken 0.14.0: `cl100k_base` (n_vocab 100,277), `o200k_base` (n_vocab 200,019); count status `exact` |
| Text counted | `nfc_ws_v1` normalization (Unicode NFC, whitespace collapsed); originals stored verbatim (103 source sentences were not NFC) |
| Word count | `unicode_whitespace_v1` (used only for the tokens-per-word metric) |
| Code | commit `f461474` (+ uncommitted dataset-approval register change); input file SHA-256 `803b7fb9bf18…` |
| Stored | `benchmark_runs` (1), `token_benchmarks` (10,120 = 5,060 × 2), `benchmark_summaries` (10); all 10,120 values cross-checked equal to `research/reports/20261120T214425Z/rows.csv` |

Alignment means FLORES provides professional translations of the same English source sentence;
REDUTAX did not independently verify semantic equivalence, and token counts do not prove it.

## Results — tokens per sentence

| Encoding | Language | Total tokens | Mean | Median | Min | Max | Mean vs English (×) | Median per-sentence ratio vs English (×) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| cl100k_base | English | 27,182 | 26.86 | 26.0 | 9 | 73 | 1.00 | 1.00 |
| cl100k_base | Hindi | 129,567 | 128.03 | 123.0 | 42 | 378 | 4.77 | 4.76 |
| cl100k_base | Kannada | 240,364 | 237.51 | 225.5 | 74 | 676 | 8.84 | 8.81 |
| cl100k_base | Tamil | 207,687 | 205.22 | 197.5 | 65 | 543 | 7.64 | 7.68 |
| cl100k_base | Telugu | 225,022 | 222.35 | 212.0 | 59 | 619 | 8.28 | 8.28 |
| o200k_base | English | 26,873 | 26.55 | 25.0 | 9 | 72 | 1.00 | 1.00 |
| o200k_base | Hindi | 42,241 | 41.74 | 40.0 | 12 | 126 | 1.57 | 1.57 |
| o200k_base | Kannada | 52,534 | 51.91 | 49.0 | 18 | 147 | 1.95 | 1.94 |
| o200k_base | Tamil | 53,114 | 52.48 | 50.0 | 16 | 152 | 1.98 | 1.95 |
| o200k_base | Telugu | 51,610 | 51.00 | 49.0 | 16 | 159 | 1.92 | 1.92 |

"Median per-sentence ratio" = median over the 1,012 groups of (language tokens ÷ English tokens for
the same aligned sentence).

### Language vs English, same encoding (denominator: English total)

| Encoding | Hindi | Kannada | Tamil | Telugu |
|---|---:|---:|---:|---:|
| cl100k_base | +377% | +784% | +664% | +728% |
| o200k_base | +57% | +95% | +98% | +92% |

### o200k_base vs cl100k_base (denominator: cl100k_base)

| Language | cl100k_base total | o200k_base total | Change | Sentences where o200k_base uses fewer tokens |
|---|---:|---:|---:|---:|
| English | 27,182 | 26,873 | −1.1% | 281 / 1,012 |
| Hindi | 129,567 | 42,241 | −67.4% | 1,012 / 1,012 |
| Kannada | 240,364 | 52,534 | −78.1% | 1,012 / 1,012 |
| Tamil | 207,687 | 53,114 | −74.4% | 1,012 / 1,012 |
| Telugu | 225,022 | 51,610 | −77.1% | 1,012 / 1,012 |

### Tokens per word (stored summaries, as on the dashboard)

| Encoding | English | Hindi | Kannada | Tamil | Telugu |
|---|---:|---:|---:|---:|---:|
| cl100k_base mean fertility | 1.25 | 5.09 | 15.10 | 12.50 | 13.39 |
| cl100k_base ratio vs English | 1.00 | 4.08 | 12.05 | 10.00 | 10.72 |
| o200k_base mean fertility | 1.24 | 1.67 | 3.31 | 3.20 | 3.09 |
| o200k_base ratio vs English | 1.00 | 1.34 | 2.66 | 2.59 | 2.49 |

95% confidence intervals of mean fertility (n = 1,012, normal approximation) are in
`summary.csv` and on the dashboard.

## Interpretation

- Under `cl100k_base` the same aligned content costs **4.8× (Hindi) to 8.8× (Kannada)** the
  English token count per sentence. Under `o200k_base` the gap shrinks to **1.6× to 2.0×**.
- `o200k_base` uses 67–78% fewer tokens than `cl100k_base` for the four Indic languages, and fewer
  tokens on every one of the 4,048 Indic sentences; for English the two are within ~1%.
- **Per-sentence vs per-word ratios differ** (Kannada 8.84× per sentence vs 12.05× per word under
  cl100k_base): Dravidian languages are agglutinative, so their sentences have fewer
  whitespace-separated "words". Per-sentence comparison on aligned text is the fairer measure of
  the token gap; the tokens-per-word figure is kept because the stored summaries and the dashboard
  use it.
- The team slide's unverified literature figure (Kannada 12.06× under cl100k_base,
  arXiv:2607.24276) is close to this run's per-word ratio (12.05×), but that paper's method has not
  been checked, so this is an observation, not a reproduction.

## Limitations

- One dataset (FLORES-200 devtest: formal, Wikipedia-style sentences); no Romanized or code-mixed
  text; results may differ for chat prompts.
- Encodings are public baselines; the encoding a hosted model uses, and its billing, are not
  asserted. No custom tokenizer was trained.
- Token efficiency only: translation quality and model comprehension were not measured.
- Whitespace word counting affects the tokens-per-word metric (see above).

## Reproduce

```bash
# repo root, backend venv, DATABASE_URL in .env, FLORES-200 approved in the register
python research/scripts/flores_to_jsonl.py --flores-dir research/data/raw/flores200_dataset --split devtest \
    --out research/data/raw/flores200_devtest.jsonl
python research/scripts/import_pilot.py --input research/data/raw/flores200_devtest.jsonl --dataset FLORES-200 --load-db
python research/scripts/run_benchmark.py --input research/data/processed/FLORES-200/2022-07-14/samples.jsonl \
    --tokenizers cl100k_base o200k_base --split test --store-db
```

The import is idempotent (re-run: 0 inserted, 5,060 unchanged). Each benchmark run gets a new
`run_id`; storing the same `run_id` twice is refused. Token counts are deterministic for a given
tiktoken version and normalization policy.
