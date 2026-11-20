# REDUTAX — Frontend completion report

Date: 2026-11-20 · Branch: `frontend/ui-phase` · Scope: frontend only (no backend file changed; verified with `git diff --name-only main -- . ':!frontend' ':!docs'` → empty).

Related: [FRONTEND_INSPECTION.md](FRONTEND_INSPECTION.md) · [FRONTEND_IMPLEMENTATION_PLAN.md](FRONTEND_IMPLEMENTATION_PLAN.md) · screenshots in [screenshots/frontend/](screenshots/frontend/)

## 1. Implemented screens

| Route | Screen (PRD §6) | Backend use | State |
|---|---|---|---|
| `/` | Home / Research overview | `GET /health`, `GET /api/tokenizers` | Live |
| `/counter` | Token Counter (F01) | `POST /api/tokenize` (×N for the all-tokenizer comparison) | Live |
| `/compare` | Language & Script Comparison (F02, F06) | `POST /api/compare-languages`, `GET /api/samples/groups` | Live (sample loader empty until data is imported) |
| `/optimize` | Prompt Optimizer (F03, F05) | `POST /api/tokenize` for the original + user rewrites | Partial: generation, meaning checks and approval inactive |
| `/cost` | Cost Calculator (F04) | `POST /api/tokenize` for input tokens | Partial: PRD §10.3 formula on **user-entered** prices only |
| `/models` | Model Recommendation (F07) | — | Inactive; opt-in **MOCK** layout preview |
| `/chat` | AI Chat (F09) | `POST /api/tokenize` (live draft count) | Inactive send; no simulated replies |
| `/voice` | Voice & Call Admin (F08, F10) | `POST /api/tokenize` for transcripts | Partial: browser speech input live, Vapi inactive |
| `/research` | Research Dashboard | `GET /api/benchmarks`, `GET /api/benchmarks/{run_id}/results` | Live (empty until a run is stored) |
| `/settings` | Settings / Privacy | `GET /health`, `GET /api/tokenizers` | Live (browser-local preferences) |
| other | 404 page | — | — |

## 2. Completed interactions

- **Counter:** text input with a 20 000-character limit meter, language (auto/5), script (detect/6), tokenizer, count, copy results, recount, clear. Token segmentation as chips or inline, with byte fragments highlighted and explained. All-tokenizer comparison as a bar chart + table. Latin-script and mixed-script notices.
- **Compare:** 2–12 variant cards (language/script/variant type), reference selector, add/remove variants. Aligned-group loader with dataset/split/language filters and pagination; editing a loaded text removes the alignment flag. Results table, token-count chart, tokens-per-word-ratio chart with a reference line, server warnings shown verbatim, CSV/JSON export (CSV has a UTF-8 BOM for Indic text).
- **Optimizer:** original prompt (kept), target tokenizer, opt-in script-alternatives flag, up to 5 human rewrites counted live. A candidate ledger shows the token change (increases shown in red), "Not evaluated" checks and "Not eligible" decisions. The original is retained per PRD §9.2. Side-by-side view with copy; protected-detail checklist; disabled Approve & send with the reason.
- **Cost:** input tokens from a live count or typed manually; output-token assumption; currency, billing unit, price source URL and checked date. Up to 4 models compared. Formula breakdown, input/output split, total, assumption badges. Optional save to recent activity.
- **Models:** Auto/Manual, language, task, context, quality slider, latency, lock toggle; routing-logic explainer; empty registry; mock preview (fictional rows, hatched banner, `Mock` cells).
- **Chat:** Auto/Manual, lock, dynamic switching (disabled while locked), new chat. Turn-anatomy placeholder, debounced live token count, voice dictation into the composer.
- **Voice:** third-party notice before the first use; recording with 5 language locales; interim transcript; takes table with confidence and low-confidence flag; editable transcript → live count. Vapi call flow, integration checklist, metrics and an empty call log.
- **Research:** filters (dataset, tokenizer, language), run list with pagination, run metadata (dataset version, split, policy IDs, code version, input hash), fertility dot + 95% CI plot by language × tokenizer, summary table with CSV export, per-sample results with filters and pagination. A separate, collapsed **unverified literature reference** panel (PRD §8).
- **Settings:** preferred languages, default tokenizer, approval mode (auto-send disabled), activity logging toggle, clear local data, data-retention table, provider status, auth notice.
- **Shell:** grouped sidebar with live/partial/planned markers; mobile drawer (Esc/scrim closes it); skip link; live API/DB/tokenizer pills.

## 3. Components created

| File | Contents |
|---|---|
| `components/shell.tsx` | AppShell, sidebar navigation, top bar status pills |
| `components/ui.tsx` | PageHeader, Badge, CountStatusBadge, TokenizerTag, Callout, ErrorState, EmptyState, Skeleton, LoadingRows, InactiveFeature, MockBanner, Stat, Field, Segmented, Pager |
| `components/charts.tsx` | HBarChart (single series, reference line), DotRangePlot (multi-series with CI whiskers + legend), hover tooltips; series palette validated (all checks pass) |
| `components/domain.tsx` | TokenPieces (segmentation), TokenizerSelect, SpeechInput (Web Speech API) |
| `components/icons.tsx` | Inline SVG icons + brand mark |
| `lib/api/*` | `types.ts` (schema mirror), `client.ts` (typed client + `ApiError`), `planned.ts` (availability + planned endpoint names) |
| `lib/*` | `format`, `languages`, `cost`, `csv`, `pieces`, `storage`, `hooks` |

Styling deviates slightly from the plan: one sectioned `app/globals.css` instead of per-component CSS Modules. The class vocabulary is small and shared across screens, so one file was easier to keep consistent.

## 4. API integration readiness

`frontend/lib/api/types.ts` was checked field by field against `backend/app/schemas.py` and the route code, and against **live responses** from the running backend:
- `GET /health` → `{"status":"ok","database":{"status":"not_configured"}}` ✔
- `GET /api/tokenizers` → `["cl100k_base","o200k_base"]` ✔
- `POST /api/tokenize` (Kannada, cl100k_base) → 44 tokens, `language: "kn"`, `script: "Knda"`, `status: "exact"`, tiktoken 0.14.0, pieces ✔
- `POST /api/compare-languages` → rows with `ratio_vs_reference` + the server's warnings ✔; with `aligned_group_id` → `aligned: true` ✔
- `GET /api/samples/groups` without DB → `503 database_not_configured`, rendered as an error state with a fix hint ✔
- Unknown tokenizer → `400 unknown_tokenizer` parsed into `ApiError` ✔
- CORS: `access-control-allow-origin: http://localhost:3000` present ✔

The DB-backed screens (Research, sample loader) were also rendered against **synthetic fixture responses**, injected by the test browser and never shipped, to verify the populated layout. No fixture data is in the app or the committed screenshots.

## 5. Mock and inactive functionality

| Where | What | How it's labelled |
|---|---|---|
| Model Recommendation | 4 fictional models (`mock-model-a…d`), every metric cell shows `Mock` | Opt-in checkbox (off by default), hatched red "MOCK DATA" banner, dashed red outline |
| Cost Calculator | Prices | Typed by the user; badge "User-entered · unverified"; source/date fields |
| Optimizer / Chat / Models / Voice (Vapi) | Planned features | `InactiveFeature` panels naming the missing endpoint and PRD phase; disabled buttons with tooltips |

No benchmark numbers, token savings, model prices, language-support claims or model replies are invented anywhere.

## 6. Known limitations

- No authentication (the backend has none); admin/research views are open. Must be added before deployment (PRD §17).
- DB-backed screens show empty or 503 states until PostgreSQL is configured and FLORES-200 (or the team set) is licence-verified and imported.
- Browser speech recognition: Chrome/Edge only (no Firefox). Audio goes to the browser vendor's service, and Indic quality is unmeasured. The transcript-to-optimizer handoff is copy/paste (no cross-page state).
- `GET /api/tokenizers` returns names only, so tokenizer versions appear only after a count.
- The Home roadmap is a static snapshot of `docs/STATUS.md`; update both together.
- The chat transcript, call log and model registry have no data contracts yet. Their screens will need wiring once the backend defines them.
- No end-to-end test suite in the repo. Route/interaction checks were run with a scratch Playwright script against the real backend (results below), not committed as CI.
- Desktop full-page screenshots show the sidebar ending at viewport height; that's the sticky sidebar in a stitched capture, not a layout bug.

## 7. Commands

```bash
# backend (unchanged) — from repo root
cd backend && pip install -e ".[dev,research]" && uvicorn app.main:app --reload   # :8000

# frontend
cd frontend
cp .env.example .env.local          # optional; default API URL is http://localhost:8000
npm install
npm run dev                         # http://localhost:3000
npm run typecheck                   # tsc --noEmit
npm test                            # vitest
npm run build && npm start          # production build on :3000
```

## 8. Test and build results (Windows 11, Node 24.16, 2026-11-20)

| Check | Result |
|---|---|
| `npm run typecheck` | 0 errors |
| `npm test` (vitest) | 16 passed, 0 failed |
| `npm run build` | Compiled; 11 routes + icon prerendered as static, first-load JS 103–118 kB |
| Route smoke test (`curl`, production server) | All 10 routes 200; unknown route 404 |
| Scripted interactions (Chrome headless, real backend) | Counter count + all-tokenizer comparison; Compare unaligned + aligned; Optimizer ledger; Cost with 2 models; Models mock toggle; mobile nav open/close; all passed with **no page errors** |
| Responsive (1440 / 820 / 390 px) | 0 px horizontal overflow on every route at every width |
| Console | Only the expected `503 database_not_configured` responses (no DB in this environment) |
| Backend untouched | No changes under `backend/` or `research/` |
