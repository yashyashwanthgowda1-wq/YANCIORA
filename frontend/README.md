# REDUTAX frontend

Next.js 15 (App Router) · React 19 · TypeScript (strict) · plain CSS design tokens · hand-written SVG charts.

```bash
npm install
npm run dev          # http://localhost:3000  (backend expected at http://localhost:8000)
npm run typecheck
npm test             # vitest unit tests for lib/
npm run build && npm start
```

Optional: `cp .env.example .env.local` and set `NEXT_PUBLIC_API_BASE_URL`. It's shipped to the browser, so never put secrets in it.

## Layout

```
app/<route>/page.tsx   server wrapper (metadata) → view.tsx (client screen)
app/globals.css        design tokens + all component styles (sectioned)
components/            shell, ui primitives, charts, domain (token pieces, tokenizer select, speech input)
lib/api/types.ts       mirror of backend/app/schemas.py — change both together
lib/api/client.ts      typed fetch client; errors → ApiError(status, code, message)
lib/api/planned.ts     feature availability + names of endpoints that do not exist yet
tests/                 vitest specs
```

## Rules carried from the PRD

- Every count shows its tokenizer, version and status badge (`exact | estimate | provider_reported | research | mock | unsupported`).
- A fertility ratio is labelled a tokenization ratio, never a cost multiplier.
- Features without a backend endpoint render `<InactiveFeature>`. Mock data appears only behind an explicit toggle with a `MockBanner`.
- No model replies, prices or results are simulated.

Status and handoff: `../docs/FRONTEND_COMPLETION_REPORT.md`, `../AGENT_HANDOFF.md`.
