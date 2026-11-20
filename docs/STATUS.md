# REDUTAX status

Last updated: 2026-11-20

## Phase summary

| Phase | Scope | State |
|---|---|---|
| 0 | Repo, config, DB schema, `/health`, tests | Done |
| 1 | Normalization, tokenizer counters, compare API, licence register, importer, benchmark, DB persistence, retrieval APIs | **Code complete. Not verified:** PostgreSQL tests not yet run against a real server; FLORES-200 licence not verified, so no real data loaded and no baseline run |
| 2 | SentencePiece Unigram training + held-out benchmark | Not started (waits for Phase 1 verification + team approval) |
| 3 | Optimizer + meaning/critical-detail checks (Features 5, 3, 6) | **Features 5, 3 and 6 done** (rules_v2, opt_rules_v1, translit_v1); Feature 6 awaits native-speaker spot checks |
| 4 | Model registry, cost, Auto/Manual routing, chat | Not started |
| 5 | Browser voice + Vapi phone | Not started |
| 6 | Evaluation report + demo | Not started |
| UI | Frontend (Next.js) for all ten PRD §6 screens | **Built, awaiting team review** on branch `frontend/ui-phase`. See `docs/FRONTEND_COMPLETION_REPORT.md` |

## Work tracks (team decision 2026-11-20)

- **Track A — Phase 1 verification:** waiting on the Neon connection in `.env` (team) and the
  verified FLORES-200 metadata (team). `TEST_PSQL_URL` should point at a **separate Neon branch**;
  the DB tests create and drop their own throwaway databases and never touch app data.
- **Track B — stateless features:** Feature 5 → Feature 3 → Feature 6, rules-based, no paid APIs.

## Feature status (10 REDUTAX features)

| # | Feature | State |
|---|---|---|
| 1 | Multilingual Token Counter | Built (`POST /api/tokenize`) |
| 2 | Language Comparison Engine | Built (`POST /api/compare-languages`); DB-backed groups/benchmarks await Track A |
| 3 | Smart Prompt Optimizer | **Done — opt_rules_v1** (`POST /api/optimize`); balanced mode inactive until phrase lists are reviewed |
| 4 | AI Cost Calculator | Not started (needs pricing source decision) |
| 5 | Meaning Preservation Checker | **Done — rules_v2** (units + standalone Romanized negations added 2026-11-21) (`POST /api/meaning-check`, `POST /api/critical-details`); Indic negation lists await native-speaker review |
| 6 | Script and Transliteration Optimizer | **Done — translit_v1** (`POST /api/script-variants`; optimizer aggressive-mode suggestions); native-speaker spot check pending |
| 7 | Smart Model Recommendation | Not started |
| 8 | Voice-to-Optimized Prompt | Not started |
| 9 | Smart AI Chatbot | Not started (needs provider approval) |
| 10 | AI Telephone Voice Assistant (Vapi) | Not started (needs Vapi approval) |

### Feature 5 acceptance criteria — results

| Criterion | Result |
|---|---|
| Detects numbers (any-script digits, grouping, decimals, %, sign, scale), dates, times, money, URLs, emails, code, quoted text, negations, protected terms | Pass (`tests/test_meaning.py`) |
| No double counting (numbers inside URLs, code, money, quotes) | Pass |
| Equivalent rewrites (`don't`→`do not`, `₹500`→`Rs. 500`, Kannada→ASCII digits, whitespace) not flagged as changed | Pass |
| Any removed/added/altered critical detail → `changed`, listed per detail | Pass |
| Heuristic warnings → `at_risk` (order change, >50% shrink, unreviewed negation list) | Pass |
| Never claims guaranteed meaning; `limitations` in every response | Pass |
| Indic word lists marked `unreviewed` until native speakers approve | Pass (enforced by a test) |
| Offsets usable for highlighting (`text[start:end] == detail.text`) | Pass |
| Input validation + standard error shape; documented in OpenAPI | Pass (`tests/test_api_meaning.py`) |

Policy: `research/configs/meaning_check.md`. Improvement backlog (not started):
`docs/backlog/feature5_meaning_check.md` — includes P1 items B5-1 (units, `5 kg` → `5 g` passes)
and B5-13 (standalone Romanized `illa`), neither fixed.

### Feature 3 acceptance criteria — results

| Criterion | Result |
|---|---|
| No accepted edit increases tokens under any requested tokenizer; zero-saving edits rejected | Pass (`test_edit_increasing_any_tokenizer_rejected`, `test_zero_saving_edit_rejected`) |
| Feature 5 gate on every edit: preserved → applied, at_risk → suggestion, changed → rejected | Pass (`test_gate_*`, `test_at_risk_edit_becomes_suggestion_not_applied`) |
| Protected details untouched (all 9 categories) | Pass (`test_edits_inside_protected_details_rejected`, `test_all_categories_preserved_in_rich_prompt`) |
| Every proposed edit reported as accepted / suggestion / rejected with reason and token delta | Pass (`test_every_proposed_edit_is_accounted_for`) |
| Original returned exactly when no eligible edit | Pass (`test_no_eligible_edit_returns_original_exactly`) |
| Deterministic; second pass makes no further change | Pass (`test_deterministic_and_idempotent`) |
| Balanced mode only uses `reviewed` lists; duplicates and script changes suggestions only | Pass (mode tests) |
| Kannada, Hindi, Tamil, Telugu, English (native, Romanized, code-mixed) | Pass (`test_languages`, 8 cases) |
| Multiple tokenizers | Pass with test tokenizers; real cl100k/o200k test **skipped here** (encoding download blocked) |
| Limitations + billing disclaimer in every response; 20,000-char limit; standard errors; OpenAPI | Pass (`tests/test_api_optimizer.py`) |
| At most 200 edits evaluated; over the limit a warning is returned and every unevaluated edit is listed (`stage: limit`); deterministic at the boundary | Pass (`test_at_or_below_limit_*`, `test_over_limit_*`, `test_limit_behaviour_is_deterministic`) |

Policy: `research/configs/optimizer.md`.

### Feature 6 acceptance criteria — results

| Criterion | Result |
|---|---|
| Licence audit of direct + transitive dependencies; versions pinned; CLI dependencies excluded | Pass (D29; `requirements-translit.txt` hash-pinned, `--no-deps`; regex pinned to 2026.9.29) |
| Native → Romanized for kn/hi/ta/te in ISO 15919 + 4 ASCII schemes | Pass (`test_round_trip_matrix`, 20 cases) |
| Round trip reported per request; measured losses flagged, not hidden | Pass — Hindi+ITRANS-Dravidian (आऊंगा → ॐगा) and Hindi+Baraha (ँ) reported lossy |
| URLs, emails, code, quoted text, protected terms, digits, Latin words untouched | Pass (`test_protected_content_untouched`, `test_native_digits_never_converted`) |
| ZWJ/ZWNJ preservation tested and losses reported | Pass (Kannada preserved; Devanagari ZWJ shown as `{}` marker, warned) |
| Romanized → native only with a named scheme; `casual` → unsupported; always review; Tamil always lossy | Pass |
| Token counts from the existing registry; billing / model-understanding disclaimers | Pass |
| Never applied automatically (Feature 6 and Feature 3) | Pass (`test_optimizer_aggressive_offers_script_variants_only_as_suggestions`, safe/balanced never propose) |
| Deterministic; 20,000-char limit; standard errors; 503 when the engine is missing; OpenAPI | Pass (`tests/test_api_transliteration.py`) |
| Native-speaker spot check | **Pending** — `docs/review/transliteration_spot_check.md` |

Policy: `research/configs/transliteration.md`. Tamil output uses Sanskrit-style consonant values
(warned on every Tamil variant) — please prioritise Tamil in the spot check.

### Fixed while building Feature 3 (behaviour unchanged, regression tests added)

- **Feature 5 performance defect:** the money-suffix and email patterns backtracked
  quadratically; a 20,000-digit input took ~80 s per `/api/meaning-check`. Now linear
  (< 0.15 s); matches unchanged (`test_extraction_is_linear_on_adversarial_input`,
  `test_money_and_email_matches_unchanged_by_performance_fix`).
- `core/text.py`: `script_of_char` and `detect_script` cached; BOM removal uses `str.replace`.
  Same outputs, much faster.

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
- **New — Feature 5 meaning check** (`app/core/details.py`, `app/services/meaning.py`,
  `app/api/meaning.py`): rule-based critical-detail extraction and comparison with statuses
  `preserved` / `at_risk` / `changed`; reusable by the optimizer.
- **New — Feature 3 optimizer** (`app/optimizer/`, `app/services/optimizer.py`,
  `app/api/optimizer.py`): safe rules gated by Feature 5; at_risk edits returned as
  suggestions; every edit reported with its token delta.
- **New — Feature 6 script variants** (`app/services/transliteration.py`,
  `app/api/transliteration.py`): native ↔ Romanized with round-trip and ZWJ/ZWNJ reports,
  registry token counts; never applied automatically.
- DB connections now time out after 5 s (`app/db/session.py`), so `/health` and the API return 503 quickly when the DB is down.

## Test results (Windows 11, Python 3.13, 2026-11-20)

`pytest` → **318 passed, 30 skipped, 0 failed** (after Feature 5 `rules_v2`, with the tiktoken encoding files installed; only the 30 PostgreSQL tests skip).

| Skipped | Count | Reason |
|---|---|---|
| `test_dataset_store.py`, `test_benchmark_store.py`, `test_api_data.py` (DB parts) | 26 | No PostgreSQL available in this environment (no Docker, no local server); `TEST_PSQL_URL` unset |
| `test_schema.py` | 4 | Same, plus `psql` not installed |
| `test_tiktoken_adapter.py` + 1 optimizer test | 7 | tiktoken could not download its encoding files (SSLError on this network) |

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
| `POST /api/meaning-check` | Implemented (Feature 5, rules_v2) |
| `POST /api/critical-details` | Implemented (Feature 5, offsets for highlighting) |
| `POST /api/optimize` | Implemented (Feature 3, opt_rules_v1) |
| `POST /api/script-variants` | Implemented (Feature 6, translit_v1) |
| `GET /api/benchmarks/{run_id}/results` | Implemented. Filters: `tokenizer`, `language`, `script`, `aligned_group_id`, `page`, `page_size` ≤ 100 |
| Others in the UI brief | Later phases |

Errors: `422 invalid_request` (bad filter), `404 not_found` (unknown dataset/run),
`503 database_not_configured` / `503 database_unavailable`.

## Remaining blockers for Phase 1 exit

1. **Run the PostgreSQL tests locally** (`TEST_PSQL_URL=... pytest`) and record the result here.
2. **Team: approve FLORES-200 use.** Licence facts were verified from the official source on 2026-11-21 and recorded in `research/configs/datasets.yaml` (CC-BY-SA-4.0, archive + SHA-256, citation, access date); the archive is downloaded (git-ignored) and line-aligned. The only remaining gate: add `approved_for: [evaluation]` once the team agrees.
   Current gate message: `BLOCKED: dataset 'FLORES-200': not approved for 'evaluation'`.
3. Then: convert → `import_pilot.py --load-db` → `run_benchmark.py --store-db` → first five-language baseline chart (Phase 1 exit criterion).
4. Run the tiktoken tests on a machine that can download the encodings (or with `TIKTOKEN_CACHE_DIR` pre-filled).
5. Team: Romanized and code-mixed pilot examples with native-speaker review (FLORES has none). This can follow the Phase 1 exit.
6. Frontend: mirror the new response types (`SampleGroupsResponse`, `BenchmarksResponse`, `BenchmarkResultsResponse`, `MeaningCheckResponse`, `CriticalDetailsResponse`, `OptimizeResponse`, `ScriptVariantsResponse`) in `frontend/lib/api/types.ts`.
   Frontend progress: `SampleGroupsResponse`, `BenchmarksResponse` and `BenchmarkResultsResponse` were mirrored by the frontend team; the rest are added by the Round 1 integration (see below).
8. Native speakers: fill in `docs/review/transliteration_spot_check.md` (Tamil first).
7. Native speakers: review the Kannada/Hindi/Tamil/Telugu negation lists in `backend/app/core/lexicons/negation.yaml`. Until then, edits to Indic text are reported `at_risk`.

## Round 1 integration (2026-11-20, branch `integration/round1`, not pushed)

Frontend connected to five backend features; runbook: `docs/ROUND1_DEMO.md`.

| Feature | Screen | State (tested through the UI in Edge, 27/27 checks on 2026-11-21) |
|---|---|---|
| Token Counter | `/counter` | Live — en/kn/hi/ta/te, cl100k_base and o200k_base |
| Language Comparison | `/compare` | Live — stateless; the aligned-sample loader still needs the database |
| Script variants (F6) | `/compare` → Script variants panel | Live — schemes, round trip, warnings, review, add to comparison, casual → unsupported |
| Prompt Optimizer (F3) | `/optimize` → Automatic optimization | Live — accepted / suggestions / rejected, meaning status, critical details |
| Meaning check (F5) | `/optimize` → rewrites ledger + result panels | Live — per-rewrite status and findings |

No database is required for these. Backend tests with real tiktoken encodings: 318 passed,
30 skipped (PostgreSQL only). Frontend: `tsc` 0 errors, vitest 16/16, `next build` OK.

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
