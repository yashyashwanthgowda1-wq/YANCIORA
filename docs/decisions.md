# Decisions and open questions

## Decisions taken in Phase 0 (change on request)

| # | Decision | Reason |
|---|---|---|
| D1 | Fresh repository, FastAPI + PostgreSQL backend | Stack suggested by PRD §13; no existing repository was provided. |
| D2 | Schema written as plain SQL, run through Alembic | Reviewable and testable with `psql`; Alembic still tracks versions. |
| D3 | Settings read with plain Pydantic, no `pydantic-settings` | One less dependency; easy to test. |
| D4 | Language codes are BCP-47 (`kn`, `hi`, `ta`, `te`, `en`); scripts ISO 15924 | BRD §9.3 allows BCP-47. FLORES codes (e.g. `kan_Knda`) can be mapped at import. |
| D5 | Only Phase 1 tables created now | Optimizer, model registry, chat, voice and audit tables arrive with their phases. |
| D6 | Frontend not scaffolded yet | UI/UX approach still being decided (see below). |

## Decisions taken in Phase 1 persistence (change on request)

| # | Decision | Reason |
|---|---|---|
| D7 | Migration `0002` changes `dataset_samples.sample_id` from globally unique to unique per dataset row `(dataset_id, sample_id)` | A dataset's next version (e.g. a newer FLORES release) reuses the same IDs; global uniqueness made that impossible. No existing code wrote to the table, so nothing breaks. |
| D8 | Imported samples are immutable. Re-importing an identical row is a no-op; a changed row with the same `sample_id` is refused. A changed licence/source/citation/access date for an imported `name@version` is refused too. | Benchmarks must point at exactly the text that was counted (BRD §16 reproducibility). Changes become a new dataset version in `datasets.yaml`. |
| D9 | DB loading always re-runs the licence gate and `validate()`, inside the service (`dataset_store.load_samples`), not only in the CLI | So no caller can write samples for an unverified dataset. |
| D10 | Leakage is checked against already-stored rows too (aligned group in one split; same text not in two splits), and enforced by a DB trigger for aligned groups | Appending a second file (e.g. FLORES `dev` after `devtest`) must not leak across splits. |
| D11 | A missing row-level licence is filled from the verified register entry; a row licence that differs from the register is an error | The register is the verified source; mixed licences need separate register entries. |
| D12 | DB writes are opt-in flags (`import_pilot.py --load-db`, `run_benchmark.py --store-db`); CSV/summary/chart files are written first and do not depend on the DB | Keeps the research scripts working without PostgreSQL. |
| D13 | Benchmark rows reference stored samples (FK) instead of copying language/script/group; summaries are stored as computed, not recomputed by the API | One source of truth for sample metadata; API returns exactly what `summary.csv` contains. |
| D14 | Added `GET /api/benchmarks/{run_id}/results` (paginated per-sample counts) next to `GET /api/benchmarks` | Per-sample results can be large; keeping them off the run list keeps that endpoint small. |
| D15 | Retrieval endpoints return `503 database_not_configured` / `503 database_unavailable` with generic messages; `404 not_found` for an unknown dataset or run | Never expose SQL, hosts or credentials (BRD §14). |

## Decisions taken for Track B (Features 5, 3, 6)

| # | Decision | Reason |
|---|---|---|
| D16 | Team: hosted PostgreSQL on Neon; tests use a separate Neon branch | Team decision 2026-11-20; keeps test databases away from app data. |
| D17 | Build order Feature 5 → 3 → 6; deterministic rules first, no paid LLM APIs without approval | Team decision 2026-11-20. The optimizer is only as safe as its meaning gate. |
| D18 | Meaning-check statuses `preserved / at_risk / changed`; `preserved` never claims guaranteed meaning; fixed `limitations` in every response | Heuristic checks cannot prove semantic equivalence. |
| D19 | Detail offsets refer to NFC text (whitespace kept), not `nfc_ws_v1` | Code indentation must be comparable and protectable. |
| D20 | Indic negation lists ship as `unreviewed` seeds; any non-whitespace edit checked with them is `at_risk` | Team decision: no Indic list is treated as approved until native speakers review it. |
| D21 | Money normalised to `CUR amount` (₹/Rs/rupees → INR …); digits of any script compared as ASCII values | `₹500` vs `Rs. 500` and `೫೦೦` vs `500` are the same detail; `₹500` vs `$500` is not. |

| D22 | Optimizer acceptance: preserved → applied; at_risk → suggestion (not applied); changed → rejected | Team decision 2026-11-20 (Indic negation lists are unreviewed). |
| D23 | An edit must save tokens under ≥ 1 requested tokenizer and add none under any; zero-saving edits rejected | Team decision 2026-11-20. |
| D24 | English phrase list stays inactive until a team member reviews it; developer_curated ≠ reviewed | Team decision 2026-11-20. |
| D25 | Duplicate-sentence removal and script changes are always suggestions | Repetition can be intentional; script changes may affect model understanding. |
| D26 | Optimizer counts tokens on the exact text (not `nfc_ws_v1`), edits proposed on NFC text with offsets into it | The optimized text is what would be sent to a model. |
| D27 | Feature 5 regexes made linear (possessive quantifiers, start-of-run lookbehinds); `core/text.py` caches script lookups | Fixes an ~80 s worst case on 20,000-digit input; outputs unchanged, regression tests added. |
| D28 | At most 200 edits evaluated per request (worst case ~4.6 s at 20,000 characters); a warning reports unevaluated edits, which stay listed in `rejected` | Team decision 2026-11-20 (lowered from 500, ~11 s). |

| D29 | Feature 6 engine `indic-transliteration` 2.3.82 (MIT, code and scheme data; uploaded 2026-04-06; sha256 verified against PyPI) installed with `--no-deps`. Runtime needs pinned: `regex==2026.9.29` (Apache-2.0 AND CNRI-Python; not 2026.11.19), `toml==0.10.2` (MIT), `tqdm==4.70.1` (MPL-2.0 AND MIT), `colorama==0.4.6` on Windows (BSD). Excluded: `typer` (+click, rich, shellingham, pygments, markdown-it-py, mdurl), `roman`, `backports.functools_lru_cache` — never imported by the `sanscript` module. `pip check` lists these three as missing; expected. | Team conditions 2026-11-20: audit, pins, no unnecessary CLI dependencies. Note: the package's main LICENSE.txt names "The Python Packaging Authority" (template leftover); the MIT grant is intact. |
| D30 | ISO 15919 default; ASCII alternatives itrans_dravidian, hk_dravidian, optitrans_dravidian, baraha; IAST not offered | Team decision 2026-11-20. |
| D31 | Romanized → native only from a named scheme; `casual` → `unsupported`; always review; Tamil always lossy | Team decision 2026-11-20. |
| D32 | Transliteration converts only runs of the target script; Feature 5 details (except negations) and digits are never converted | Preserve URLs, emails, code, quotes, protected terms, digits and Latin words. |
| D33 | Script variants are never applied; in the optimizer they are whole-text `script_variant` suggestions in aggressive mode only | Team decision 2026-11-20. |

The new response types in `backend/app/schemas.py` (`SampleGroupsResponse`, `BenchmarksResponse`,
`BenchmarkResultsResponse`, `MeaningCheckResponse`, `CriticalDetailsResponse`, `OptimizeResponse`, `ScriptVariantsResponse`) must be mirrored in the frontend's `lib/api/types.ts`.

## Open questions (BRD §23)

- Repository: is there existing code to merge?
- UI/UX: design tool and frontend framework (Next.js suggested by PRD).
- Which dataset licences permit the intended use (FLORES-200 first)?
- LLM providers and API accounts for the demo.
- Speech providers for Kannada/Hindi/Tamil/Telugu through Vapi.
- Minimum task-quality score and maximum voice latency.
- Prompt/transcript retention period.
- Pricing source and currency for the cost calculator.

## Unverified figures

The fertility ratios in the team slide (e.g. Kannada 12.06× under cl100k_base) come from
Srivastava, arXiv:2607.24276. They have not been reproduced or checked against the paper.
Do not present them as REDUTAX results or as API bill multipliers.
