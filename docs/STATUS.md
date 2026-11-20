# REDUTAX status

Last updated: 2026-11-20

## Phase summary

| Phase | Scope | State |
|---|---|---|
| 0 | Repo, config, DB schema, `/health`, tests | Done |
| 1 | Normalization, tokenizer counters, compare API, licence register, importer, benchmark, DB persistence, retrieval APIs | **Code complete. Not verified:** PostgreSQL tests not yet run against a real server; FLORES-200 licence not verified, so no real data loaded and no baseline run |
| 2 | SentencePiece Unigram training + held-out benchmark | Not started (waits for Phase 1 verification + team approval) |
| 3 | Optimizer + meaning/critical-detail checks | Not started |
| 4 | Model registry, cost, Auto/Manual routing, chat | Not started |
| 5 | Browser voice + Vapi phone | Not started |
| 6 | Evaluation report + demo | Not started |
| UI | Frontend (Next.js) for all ten PRD §6 screens | **Built, awaiting team review** on branch `frontend/ui-phase`. See `docs/FRONTEND_COMPLETION_REPORT.md` |

## What works

- Text normalization `nfc_ws_v1`, word count `unicode_whitespace_v1`, script detection.
- Tokenize and compare services, with tokenizer identity and count status on every result.
- Licence register gate: blocks import until licence, citation, version, access date and approved use are filled in.
- Dataset validation: schema, duplicate IDs, duplicate text, split leakage (text and aligned group).
- FLORES-200 converter (line-aligned files → aligned groups).
- Benchmark runner: rows.csv, summary.csv, run.json, chart (unchanged).
- **New — dataset persistence** (`app/services/dataset_store.py`, `import_pilot.py --load-db`):
  - Re-runs the licence gate and validation inside the loader.
  - One transaction per import. Re-imports are idempotent; a changed sample or changed licence metadata is refused.
  - Checks leakage against rows already stored, with a DB trigger as backstop. Every import is logged.
- **New — benchmark persistence** (`app/services/benchmark_store.py`, `run_benchmark.py --store-db`):
  - Stores run metadata and config, per-sample counts with tokenizer name/library/version and count status, and the summaries.
  - Requires the benchmarked samples to be stored and unchanged. Files are still written first.
- **New — retrieval APIs**: `GET /api/samples/groups`, `GET /api/benchmarks`, `GET /api/benchmarks/{run_id}/results`.
  - Paginated, with validated filters and the `{"error": {...}}` error shape. No DB details are exposed.
- DB connections now time out after 5 s (`app/db/session.py`), so `/health` and the API return 503 quickly when the DB is down.

## Test results (Windows 11, Python 3.13, 2026-11-20)

`pytest` → **77 passed, 36 skipped, 0 failed.**

| Skipped | Count | Reason |
|---|---|---|
| `test_dataset_store.py`, `test_benchmark_store.py`, `test_api_data.py` (DB parts) | 26 | No PostgreSQL available in this environment (no Docker, no local server); `TEST_PSQL_URL` unset |
| `test_schema.py` | 4 | Same, plus `psql` not installed |
| `test_tiktoken_adapter.py` | 6 | tiktoken could not download its encoding files (SSLError on this network) |

**PostgreSQL integration (migration 0002, loader, benchmark store, DB-backed API tests) has not been
executed yet.** Run it locally with `TEST_PSQL_URL` (commands below). The DB tests run the real Alembic chain (`upgrade head`) on a throwaway database.

Note for Windows: if pytest fails with `PermissionError` on its temp folder, add `--basetemp .pytest_tmp`.

## Database migrations

| Revision | Content |
|---|---|
| 0001 | languages (seeded), datasets, dataset_samples, tokenizers, token_benchmarks |
| 0002 | Adds `dataset_samples.source_name/source_url/license/normalization/content_sha256`. Changes `sample_id` to unique per dataset. Adds a script CHECK and a split-leakage trigger, plus new tables `dataset_imports`, `benchmark_runs` and `benchmark_summaries`. Adds `token_benchmarks.count_status` and a foreign key to `benchmark_runs`. Has a downgrade. |

## API endpoints

| Endpoint | State |
|---|---|
| `GET /health` | Implemented |
| `GET /api/tokenizers` | Implemented |
| `POST /api/tokenize` | Implemented (cl100k_base, o200k_base) |
| `POST /api/compare-languages` | Implemented |
| `GET /api/samples/groups` | Implemented. Filters: `dataset`, `dataset_version`, `language` (repeatable, groups containing all), `split`, `aligned_group_id`, `page`, `page_size` ≤ 100 |
| `GET /api/benchmarks` | Implemented. Filters: `run_id`, `dataset`, `dataset_version`, `tokenizer`, `language`, `page`, `page_size` ≤ 100 |
| `GET /api/benchmarks/{run_id}/results` | Implemented. Filters: `tokenizer`, `language`, `script`, `aligned_group_id`, `page`, `page_size` ≤ 100 |
| Others in the UI brief | Later phases |

Errors: `422 invalid_request` (bad filter), `404 not_found` (unknown dataset/run),
`503 database_not_configured` / `503 database_unavailable`.

## Remaining blockers for Phase 1 exit

1. **Run the PostgreSQL tests locally** (`TEST_PSQL_URL=... pytest`) and record the result here.
2. **Team: verify FLORES-200 licence.** Download it, read its own licence/terms, and fill in `research/configs/datasets.yaml`:
   `version`, `license`, `license_url`, `citation`, `accessed_at`, `approved_for: [evaluation]`.
   Until then the import is blocked (by design): `BLOCKED: dataset 'FLORES-200': version not verified; license not verified; citation not verified; accessed_at missing; not approved for 'evaluation'`.
3. Then: convert → `import_pilot.py --load-db` → `run_benchmark.py --store-db` → first five-language baseline chart (Phase 1 exit criterion).
4. Run the tiktoken tests on a machine that can download the encodings (or with `TIKTOKEN_CACHE_DIR` pre-filled).
5. Team: Romanized and code-mixed pilot examples with native-speaker review (FLORES has none). This can follow the Phase 1 exit.
6. ~~Frontend: mirror the new response types in `lib/api/types.ts`~~ Done in `frontend/lib/api/types.ts`.

## Frontend (2026-11-20)

Frontend only; no backend file changed. Details: `docs/FRONTEND_COMPLETION_REPORT.md`, handoff: `AGENT_HANDOFF.md`.

| Area | State |
|---|---|
| Live against the backend | Home, Token Counter, Language Comparison (+ aligned sample loader), Research Dashboard, Settings |
| Partial | Prompt Optimizer (counts user rewrites; no generation/meaning checks), Cost Calculator (user-entered prices only), Voice (browser speech input; no Vapi) |
| Inactive until their phase | Model Recommendation (opt-in labelled mock preview), AI Chat send, Vapi admin |
| Checks | `tsc` 0 errors · vitest 16/16 · `next build` OK · all routes 200 · no horizontal overflow at 1440/820/390 px · scripted interactions against the real backend passed |

## Known limitations

- Word count is whitespace-based; check code-mixed text with attached punctuation.
- tiktoken downloads its encoding files on first use; offline machines need the cache.
- Encodings are baselines; which hosted model uses which encoding is not asserted anywhere.
- A stored benchmark run covers one dataset version (one processed `samples.jsonl`).
- Paper figures in the team slide (arXiv:2607.24276) are unverified and not REDUTAX results.
