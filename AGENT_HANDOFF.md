# Agent handoff — REDUTAX

Last updated: 2026-11-20 · Branch: `frontend/ui-phase` (not merged to `main`)

Read `CLAUDE.md`, `docs/STATUS.md` and `docs/FRONTEND_COMPLETION_REPORT.md` first.

## Where things stand

- **Frontend work is complete for review.** The team approves the UI before backend integration starts.
  **No backend work has begun, and the backend was not modified.**
- Backend: Phase 0 done; Phase 1 code complete (not yet verified against PostgreSQL; FLORES-200 licence unverified).

## What the frontend has

All ten PRD §6 screens in `frontend/` (Next.js 15, React 19, TypeScript strict). See the completion report for details.

| Screen | Data source today |
|---|---|
| Home, Settings | Live: `/health`, `/api/tokenizers` |
| Token Counter | Live: `POST /api/tokenize` |
| Language Comparison | Live: `POST /api/compare-languages`; `GET /api/samples/groups` (empty or 503 until data is imported) |
| Research Dashboard | Live: `GET /api/benchmarks`, `/api/benchmarks/{run_id}/results` (empty or 503 until a run is stored) |
| Prompt Optimizer | Partial: live counts of user rewrites; generation/meaning checks/approval inactive |
| Cost Calculator | Partial: formula on user-entered prices; no registry |
| Voice & Calls | Partial: browser speech input; Vapi inactive |
| Model Recommendation | Inactive; opt-in labelled MOCK preview (fictional rows) |
| AI Chat | Inactive send; live draft token count; no simulated replies |

## Backend APIs ready for integration (already wired in the frontend)

`GET /health`, `GET /api/tokenizers`, `POST /api/tokenize`, `POST /api/compare-languages`,
`GET /api/samples/groups`, `GET /api/benchmarks`, `GET /api/benchmarks/{run_id}/results`.
The contract is `frontend/lib/api/types.ts`, which mirrors `backend/app/schemas.py`. **Change both together.**

## Next steps for backend integration (after team approval)

1. **Data so the live screens show something:** run the PostgreSQL tests, verify the FLORES-200 licence in
   `research/configs/datasets.yaml`, import it, store a baseline benchmark. Research + the Compare sample loader then fill in with no frontend change.
2. **When a planned endpoint lands** (`/api/optimize`, `/api/evaluate-meaning`, `/api/cost/estimate`, `/api/models/recommend`, `/api/chat`, `/api/vapi/*`, `POST /api/benchmarks/run`):
   - add its Pydantic models to `schemas.py`, then mirror them in `frontend/lib/api/types.ts`;
   - add a function to `api` in `frontend/lib/api/client.ts`;
   - flip `availability` in `frontend/lib/api/planned.ts` and replace that screen's `<InactiveFeature>` with real calls.
   - Do not reuse the Model Recommendation `MOCK_ROWS` for real data; delete them when the registry exists.
3. Optional backend improvements that would help the UI (team decision; not done here):
   - `GET /api/tokenizers` returning versions/kinds, not just names;
   - an endpoint exposing the licence register status (read-only).
4. Authentication: define it in the backend first (PRD §17, §22); the UI then adds sign-in and protects Research/Voice admin.
5. If the frontend dev server runs on a port other than 3000, add it to `REDUTAX_CORS_ORIGINS` (env only).

## Commands

```bash
docker compose up -d db                                     # optional; DB-backed screens need it
cd backend && pip install -e ".[dev,research]"
alembic upgrade head                                        # if using the DB
uvicorn app.main:app --reload                               # http://localhost:8000

cd frontend && npm install && npm run dev                   # http://localhost:3000
npm run typecheck && npm test && npm run build              # checks
```

## Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` (optional) | Backend URL; default `http://localhost:8000`. Public by design; never put secrets in `NEXT_PUBLIC_*` |
| `REDUTAX_CORS_ORIGINS` | root `.env` (backend) | Must include the frontend origin (default `http://localhost:3000`) |
| `DATABASE_URL` | root `.env` (backend) | Needed for the samples/benchmarks endpoints |

## Known issues

- tiktoken must download its encoding files on first use on the backend machine; offline servers return `503 tokenizer_unavailable`, which the UI shows.
- Browser voice input works in Chrome/Edge only and uses the browser vendor's speech service (third-party disclosure shown).
- `CLAUDE.md` still says the frontend will come from Grok. This frontend replaced that plan at the user's request; the team may want to update that line.
- No committed E2E suite; interaction checks used a scratch Playwright script (see the completion report).
