# REDUTAX — Frontend inspection report

Date: 2026-11-20 · Branch: `frontend/ui-phase` · Author: AI coding assistant, for team review.

Scope: a read-only inspection of the repository and the PRD (`REDUTAX_PRD_YANCIORA_Team46_Final`)
before any frontend work. **No backend file was changed.** Everything below comes from reading the
source code, not just the documentation.

---

## 1. Project architecture (as built)

| Layer | Location | State |
|---|---|---|
| FastAPI app | `backend/app/main.py` | CORS for `REDUTAX_CORS_ORIGINS` (default `http://localhost:3000`); methods **GET, POST only**; `x-request-id` header on every response |
| Settings | `backend/app/core/config.py` | Env-only settings: `REDUTAX_ENV`, `REDUTAX_LOG_LEVEL`, `REDUTAX_CORS_ORIGINS`, `DATABASE_URL` |
| Text policy | `backend/app/core/text.py` | Normalization `nfc_ws_v1`, word count `unicode_whitespace_v1`, script detection (Knda/Deva/Taml/Telu/Latn/mixed), script→language guess (Latin → `null`) |
| Metrics | `backend/app/core/metrics.py` | fertility, relative ratio, summary stats (CI only for n ≥ 30) |
| Tokenizers | `backend/app/tokenizers/` | Adapter interface + registry; only `cl100k_base` and `o200k_base` (tiktoken, kind `baseline`, status `exact`) |
| Services | `backend/app/services/` | `counting` (tokenize/compare), `dataset_import` (licence gate, validation), `dataset_store` (DB load + `list_groups`), `benchmark` (runner), `benchmark_store` (DB store + `list_runs`/`list_results`) |
| API | `backend/app/api/` | `health`, `counting`, `samples`, `benchmarks`; uniform error body |
| DB | `backend/migrations/` | Alembic 0001 + 0002 (Phase 0/1 tables only) |
| Research | `research/` | Licence register, FLORES converter, importer, benchmark CLI |
| Frontend | `frontend/` | **Only a README. Not scaffolded.** |

## 2. Available API endpoints (verified in code)

| Method & path | Request | Response | Errors |
|---|---|---|---|
| `GET /health` | – | `{app, version, env, status: "ok"\|"degraded", database: {status: "ok"\|"not_configured"\|"error", error?}}` | 503 when DB configured but unreachable (body still returned) |
| `GET /api/tokenizers` | – | `{tokenizers: string[]}` (names only, no versions) | – |
| `POST /api/tokenize` | `TokenizeRequest {text (1–20 000 chars, not blank), tokenizer, language: kn\|hi\|ta\|te\|en\|"auto" = "auto", script?: Script, include_pieces = false}` | `TokenizeResponse {tokenizer: TokenizerRef, status, language, script, token_count, word_count, char_count, tokens_per_word, normalization, word_count_method, pieces?}` | 400 `unknown_tokenizer`, 503 `tokenizer_unavailable`, 422 `invalid_request` |
| `POST /api/compare-languages` | `CompareRequest {tokenizer, reference_index ≥ 0 = 0, variants: CompareVariant[2..12], aligned_group_id?}` | `CompareResponse {tokenizer, status, aligned, rows: CompareRow[], warnings: string[]}` | same as above; `reference_index` out of range → 422 |
| `GET /api/samples/groups` | query: `dataset, dataset_version, language` (repeatable), `split, aligned_group_id, page ≥ 1, page_size 1–100 (=20)` | `SampleGroupsResponse {items: SampleGroup[], page, page_size, total}` | 422, 404 `not_found`, 503 `database_not_configured`/`database_unavailable` |
| `GET /api/benchmarks` | query: `run_id, dataset, dataset_version, tokenizer, language, page, page_size (=20)` | `BenchmarksResponse {items: BenchmarkRun[], …}` | as above |
| `GET /api/benchmarks/{run_id}/results` | path `run_id` (`^[A-Za-z0-9_.:-]+$`); query: `tokenizer, language, script, aligned_group_id, page, page_size (=50)` | `BenchmarkResultsResponse {run_id, items: BenchmarkResultRow[], …}` | as above |

Error body for all handled errors: `{"error": {"code": string, "message": string}}`.

Important details for the client:
- `TokenizeResponse.language` is `null` for Latin-script text when `language="auto"` (English vs Romanized Indic is ambiguous). The UI must ask the user instead of guessing.
- `pieces` are byte-level decodes; partial characters appear as `U+FFFD` (`�`). The UI must show these as byte fragments, not as errors.
- `ratio_vs_reference` is a **fertility ratio** (tokens-per-word over the reference's tokens-per-word), not a token-count ratio and never a cost multiplier.
- `compare` adds its own warnings (unaligned, script mismatch, empty reference, ratio note). Show them as returned.
- `tiktoken` downloads encoding files on first use; offline servers return `503 tokenizer_unavailable`. This is a normal state the UI must handle.

## 3. Database-backed functionality

Tables (0001 + 0002): `languages` (seeded), `datasets`, `dataset_samples`, `tokenizers`,
`token_benchmarks`, `dataset_imports`, `benchmark_runs`, `benchmark_summaries`.

Exposed read-only through the API: aligned sample groups, benchmark runs + summaries, per-sample results.
Not exposed: the dataset/licence register, import logs, the `languages` table, tokenizer metadata (vocab size, config).
There are **no write endpoints** (imports and benchmark runs are CLI-only).

**Current data state:** no dataset has been imported (FLORES-200 licence is `TO_VERIFY`) and no
benchmark has been stored, so every DB-backed screen will show an empty state, or a 503 where no database is configured.

## 4. Research and tokenizer functionality

- Licence register `research/configs/datasets.yaml`: FLORES-200 and REDUTAX-team-pilot, both blocked (`TO_VERIFY`, `approved_for: []`).
- `flores_to_jsonl.py`, `import_pilot.py` (`--load-db`), `run_benchmark.py` (`--store-db`): all CLI tools; outputs `rows.csv`, `summary.csv`, `run.json`, `ratio_chart.png`.
- Experimental SentencePiece tokenizer: **not started** (Phase 2). The registry's `kind: "experimental"` → `status: "research"` path exists but no adapter uses it.
- Tests: 77 passed / 36 skipped (per `docs/STATUS.md`). The PostgreSQL and tiktoken tests have not run in this environment.

## 5. Existing frontend files

`frontend/README.md` only. `CLAUDE.md` and `STATUS.md` say a Grok-generated Next.js app was planned
and that `lib/api/types.ts` must mirror `backend/app/schemas.py`. That Grok output is **not in the
repository**. This frontend is built in its place, at the user's request, and keeps the same
`lib/api/types.ts` convention.

## 6. PRD requirements mapped to backend capability

| PRD | Feature / screen | Backend support today | Frontend treatment |
|---|---|---|---|
| F01 | Token Counter | ✅ `POST /api/tokenize`, `GET /api/tokenizers` | **Live**: counts, pieces, multi-tokenizer comparison, status + version labels |
| F02 | Language Comparison | ✅ `POST /api/compare-languages`; ✅ `GET /api/samples/groups` (empty until data import) | **Live**: variant editor, aligned sample loader, table + chart, warnings, export |
| F03 | Prompt Optimizer | ❌ no `/api/optimize` | **Partial**: the original and any user-written rewrites are counted with the live tokenizer. Automatic candidate generation, meaning checks and approval are **inactive** |
| F04 | Cost Calculator | ❌ no `/api/cost/estimate`, no price registry | **Partial**: the formula (PRD §10.3) runs client-side **only on prices the user types in**, labelled "user-entered, unverified". Input tokens come from a live encoding count, labelled as an estimate for any hosted model. No built-in prices |
| F05 | Meaning Preservation | ❌ no `/api/evaluate-meaning` | Inactive panels inside the Optimizer |
| F06 | Script alternatives | ⚠️ compare API handles native/Romanized/code-mixed variants | Live through Compare (script/variant selectors); no automatic transliteration |
| F07 | Model Recommendation | ❌ no registry, no `/api/models/recommend` | Constraint form + empty registry state; optional **MOCK** layout preview (fictional models, hatched banner) |
| F08 | Voice-to-prompt | ❌ no backend STT | Browser Web Speech API (where the browser has it), with a third-party notice; the transcript goes to the live tokenizer |
| F09 | Chat | ❌ no `/api/chat` | Composer with live token count; sending is disabled. **No simulated replies** |
| F10 | Vapi phone | ❌ no Vapi endpoints | Voice/Call Admin with "not configured" status and empty call log |
| Research | Dashboard | ✅ `GET /api/benchmarks`, `/results` (empty until a run is stored) | **Live**: run list, summary table + charts, per-sample results, filters; literature figures in a separate, clearly labelled unverified panel |
| §6 | Home | ✅ `/health`, `/api/tokenizers` | Live system status, phase roadmap, recent activity in this browser only |
| §6 | Settings/Privacy | ✅ `/health` for provider/DB status | Preferences stored in this browser; approval mode fixed to "required" (PRD §22) |

## 7. Frontend features that need mock data or an inactive state

- **Inactive (no data shown):** optimizer candidate generation, meaning/critical-detail checks, approve/send, chat send, Vapi status/call logs, dataset licence register view, audit events.
- **Clearly labelled mock (opt-in toggle, off by default):** the Model Recommendation layout preview. The models are fictional (`mock-model-a`…) and the prices are shown as `MOCK`. Never used in any calculation shown as real.
- **User-supplied, not invented:** cost-calculator prices.
- No fabricated benchmark numbers, token savings, model outputs or prices anywhere.

## 8. Cannot be connected yet (backend missing)

`POST /api/optimize`, `/api/evaluate-meaning`, `/api/cost/estimate`, `/api/models/recommend`,
`/api/chat`, `/api/vapi/webhook`, `/api/vapi/optimize-and-answer`, `POST /api/benchmarks/run`,
any auth/session endpoint, the dataset register endpoint and the experimental SentencePiece tokenizer.
Their planned contracts are listed in `frontend/lib/api/planned.ts` as names only. **No request or response types are invented for them.**

## 9. Architectural concerns and ambiguities

1. **No authentication** anywhere. PRD §17 says admin/research endpoints must be authenticated. The frontend has no login, by design, until the backend defines one.
2. **CORS allows only GET/POST** and one origin. Fine for this frontend; a different dev port needs `REDUTAX_CORS_ORIGINS` updated (env only, no code change).
3. `GET /api/tokenizers` returns names only. Versions appear only after a count, so the selector shows "version shown after first count".
4. **No model ↔ encoding association** is asserted anywhere (correctly). The cost calculator therefore can't say "exact" for any hosted model; it always labels input tokens as an estimate.
5. `ratio_vs_reference` is a fertility ratio. A chart titled "token ratio" would mislead, so the UI labels it "tokens-per-word ratio vs reference".
6. The literature figures in PRD §8 (arXiv:2607.24276) are unverified. They appear only on the Research page, in a separate panel marked "not reproduced, not a cost multiplier".
7. Docs disagree on the PRD file type (`.docx` in README, `.pdf` provided). Not material.
8. `STATUS.md` says the UI is "being generated by Grok". It is updated to reflect this frontend.
9. Browser speech recognition (Chrome/Edge) sends audio to the browser vendor's service. That is a third-party disclosure, so the UI shows a notice and needs an explicit click. The team should confirm (open question: speech providers).
