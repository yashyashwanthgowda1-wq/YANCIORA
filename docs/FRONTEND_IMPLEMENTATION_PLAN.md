# REDUTAX — Frontend implementation plan

Companion to `docs/FRONTEND_INSPECTION.md`. Frontend only; the backend is not modified.

## 1. Stack decisions

| Decision | Choice | Reason |
|---|---|---|
| Framework | **Next.js 15 (App Router) + React 19 + TypeScript (strict)** | Suggested by PRD §13 and `CLAUDE.md`; file-based routing fits the ten PRD screens |
| Rendering | Static shell + client-side data fetching from the browser | The backend is a separate FastAPI service; CORS is already set for `http://localhost:3000`; no server secrets in the frontend (PRD §17) |
| Styling | Plain CSS: design tokens in `app/globals.css` + CSS Modules per component | No runtime CSS dependency, full control of the visual identity, readable for the team |
| Charts | Small hand-written SVG components (`components/charts/`) | The charts needed are bars, dot plots and ranges; a chart library would add weight and a generic look |
| Fonts | System stacks with Indic fallbacks (`Nirmala UI`, `Noto Sans Kannada/Devanagari/Tamil/Telugu`) | No network font fetch at build time; Indic scripts render with installed system fonts |
| Tests | Vitest for `lib/` (API client, formatting, cost formula, CSV export, piece rendering) + `tsc --noEmit` + `next build` | Fast, no browser dependency |
| Config | `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`) | The only env var; it's public by nature (a URL, not a secret) |

## 2. Directory structure

```
frontend/
  app/
    layout.tsx               shell: sidebar nav, top status bar
    globals.css              design tokens + base styles
    page.tsx                 Home / Research overview
    counter/page.tsx         F01 Token Counter
    compare/page.tsx         F02/F06 Language & Script Comparison
    optimize/page.tsx        F03/F05 Prompt Optimizer (partial)
    cost/page.tsx            F04 Cost Calculator (user-entered prices)
    models/page.tsx          F07 Model Recommendation (inactive + mock preview)
    chat/page.tsx            F09 AI Chat (inactive send, live count, voice input)
    voice/page.tsx           F08/F10 Voice & Call Admin
    research/page.tsx        Research dashboard (benchmarks, results)
    settings/page.tsx        Settings / Privacy
    not-found.tsx
  components/
    shell/                   Sidebar, TopBar, PageHeader
    ui/                      Button, Field, Select, Textarea, Badge, CountStatusBadge,
                             Callout, EmptyState, ErrorState, Skeleton, Tabs, DataTable,
                             Stat, Toggle, MockBanner, InactiveFeature
    charts/                  BarChart, RatioDotPlot, RangePlot
    tokens/                  TokenPieces (segmentation + highlighting)
    voice/                   SpeechInput (Web Speech API wrapper)
  lib/
    api/types.ts             exact mirror of backend/app/schemas.py
    api/client.ts            fetch wrapper, ApiError, typed endpoint functions
    api/planned.ts           endpoints from PRD §15 that do not exist yet (names + phase only)
    format.ts                number/ratio/date formatting
    languages.ts             language + script metadata (labels, native names)
    cost.ts                  PRD §10.3 formula (pure)
    csv.ts                   export helpers
    pieces.ts                token piece display helpers (byte fragments, whitespace)
    storage.ts               localStorage preferences + local activity log (try/catch)
    hooks.ts                 useApi / useHealth / useTokenizers
  tests/                     vitest specs
```

## 3. Routing and navigation

The sidebar is grouped by what the user is doing, not one flat list:

- **Overview** — Home
- **Measure** — Token Counter, Language Comparison
- **Reduce** — Prompt Optimizer, Cost Calculator, Model Recommendation
- **Assist** — AI Chat, Voice & Calls
- **Research** — Research Dashboard
- **System** — Settings & Privacy

Each item has an availability marker: `live`, `partial` or `planned`, taken from one table in
`lib/api/planned.ts`, so navigation never claims more than the backend supports. On mobile the
sidebar becomes a drawer. A top bar shows live backend + database status from `/health`.

## 4. API integration layer

- `lib/api/types.ts` mirrors every model in `schemas.py` field for field (`LanguageCode`, `Script`,
  `VariantType`, `CountStatus`, `TokenizerRef`, `TokenizeRequest/Response`, `CompareVariant/Request/Row/Response`,
  `Split`, `DatasetRef`, `GroupSample`, `SampleGroup`, `SampleGroupsResponse`, `BenchmarkSummary`,
  `BenchmarkRun`, `BenchmarksResponse`, `BenchmarkResultRow`, `BenchmarkResultsResponse`), plus
  `HealthResponse`, `TokenizersResponse` and `ApiErrorBody` from the route code.
- `client.ts`: one `request<T>()` that parses `{"error": {code, message}}` into `ApiError(status, code, message)`.
  A network failure becomes `ApiError(0, "network_error")`. Query strings support repeatable `language`.
- Client-side validation mirrors server limits (`MAX_TEXT_CHARS = 20000`, `MAX_VARIANTS = 12`, `page_size ≤ 100`),
  and the server stays the authority.
- Planned endpoints: **no invented types**. Screens that need them render `<InactiveFeature>` with the endpoint name and PRD phase.

## 5. Design system

**Identity: red, white, blue — a research instrument, not a marketing site.**

| Token | Value | Use |
|---|---|---|
| `--red-600` | `#C1121F` | primary actions, focus of attention, important states |
| `--red-50` | `#FDF1F2` | primary tint backgrounds |
| `--blue-700` | `#1B3A8C` | technical information, secondary actions, links |
| `--blue-500` | `#2F5BD3` | data series, chart marks |
| `--blue-50` | `#EEF3FD` | data/technical tint |
| `--ink` | `#0E1525` | headings, primary text |
| `--grey-600 / 400 / 200 / 100` | `#4A5263 / #8A91A0 / #DCDFE5 / #F3F4F6` | supporting text, borders, dividers, subtle surfaces |
| `--white` | `#FFFFFF` | main surfaces |

Status colours come from the same palette: `exact` = blue solid, `estimate` = blue outline,
`provider_reported` = ink, `research` = blue hatched, `mock` = red hatched, `unsupported` = grey. Each
badge always carries a text label too, so it never relies on colour alone.

Typography: a system sans for UI text, a system monospace for token pieces and IDs, tabular numerals for every metric.
Scale: 12 / 13 / 14 / 16 / 20 / 28 / 40 px. 4 px spacing grid. Radius 6 px on controls, 10 px on panels.
Motion: only state transitions (≤ 150 ms), turned off under `prefers-reduced-motion`.

Accessibility: AA contrast for all text, visible focus rings (blue), labelled controls, keyboard-reachable
navigation, `lang` attributes on Indic text samples, `aria-live` regions for results.

## 6. Screen layouts (each purpose-specific)

| Screen | Layout idea |
|---|---|
| Home | Editorial header stating the problem; a "how REDUTAX measures" pipeline strip; live system panel; phase roadmap timeline; quick-start tiles; local recent activity |
| Token Counter | Two-column workbench: input on the left; on the right a large count readout, then the segmentation view; multi-tokenizer comparison strip below |
| Language Comparison | A variant grid (one card per language/script); a reference selector; results as a table + horizontal bar chart + fertility-ratio dot plot; warnings rail |
| Prompt Optimizer | Side-by-side original vs candidate columns; a candidate ledger table; meaning-check and approval panels shown as inactive with the reason |
| Cost Calculator | Calculator layout: token inputs (live count or manual), a price entry form, a formula breakdown shown as an equation, assumption notes |
| Model Recommendation | Constraint panel (language, task, context, quality, latency) on the left; routing pipeline diagram and an empty registry table on the right; mock preview toggle |
| AI Chat | Full-height conversation layout: model control bar (Auto/Manual/Lock), empty transcript with turn anatomy, composer with live token count and voice input |
| Voice & Calls | Two zones: browser voice test bench (transcribe → count) and the Vapi admin (integration status checklist, empty call log table, call flow diagram) |
| Research | Run selector rail; summary metric table; fertility-by-language chart with CI ranges; per-sample results table with filters; literature reference panel (unverified) |
| Settings | Form sections: language preferences, optimizer approval mode, data and privacy notice, provider configuration status, local data reset |

## 7. Delivery steps (frontend-only)

1. Scaffold Next.js + tooling; design tokens; shell + navigation. *(commit)*
2. API types + client + hooks + unit tests. *(commit)*
3. Live screens: Counter, Compare, Research, Home, Settings. *(commit)*
4. Partial/inactive screens: Optimizer, Cost, Models, Chat, Voice. *(commit)*
5. Typecheck, build, unit tests, route smoke tests against the real backend, headless screenshots,
   completion report, handoff docs. *(commit)*

## 8. Risks

- Live counts depend on tiktoken loading its encodings on the backend machine (`503 tokenizer_unavailable` otherwise). The UI shows this state clearly.
- Without PostgreSQL + imported data, Compare's sample loader and the Research dashboard show empty states only.
- Browser speech recognition support varies by browser and language. Firefox has none, and Indic language quality is unmeasured.
