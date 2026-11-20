# Changelog

## Unreleased — frontend (branch `frontend/ui-phase`, 2026-11-20)

Frontend only. No backend, database, migration, tokenizer or research files changed.

### Added
- `frontend/`: Next.js 15 + React 19 + TypeScript app with a red/white/blue design system.
- Typed API layer: `lib/api/types.ts` mirrors `backend/app/schemas.py`; `lib/api/client.ts` parses the `{"error": {code, message}}` body into `ApiError`; `lib/api/planned.ts` lists PRD endpoints that don't exist yet (names only).
- Screens: Home, Token Counter, Language Comparison, Prompt Optimizer, Cost Calculator, Model Recommendation, AI Chat, Voice & Calls, Research Dashboard, Settings & Privacy, 404.
- Token segmentation view with byte-fragment highlighting; SVG bar and dot/CI charts with a validated series palette; CSV/JSON export.
- Browser speech input (Web Speech API) behind a third-party notice.
- Unit tests (vitest, 16) for the API client, cost formula, CSV, token-piece display and formatting.
- Docs: `docs/FRONTEND_INSPECTION.md`, `docs/FRONTEND_IMPLEMENTATION_PLAN.md`, `docs/FRONTEND_COMPLETION_REPORT.md`, `docs/screenshots/frontend/`, `AGENT_HANDOFF.md`.

### Not included (by design)
- No invented benchmark results, token savings, model prices or model replies. Planned features render as inactive panels. The Model Recommendation layout preview uses clearly labelled fictional mock rows and is off by default.
