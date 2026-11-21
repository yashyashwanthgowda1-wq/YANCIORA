# REDUTAX Phase 2 features (4, 7, 8, 9, 10)

State on 2026-11-21, branch `integration/round1`. Decisions are D42–D49 in `docs/decisions.md`.

All Phase 2 features work **without any paid provider**:
- The model registry ships empty.
- Chat runs in analysis mode.
- Server speech-to-text and the Vapi webhook stay inactive until their environment variables are set.

Nothing in this phase invents model prices, language support, quality scores or transcripts.

## Feature 4 — AI Cost Calculator (`cost_v1`)

- **Endpoint**: `POST /api/cost/estimate`.
- **Input**: `text`, optional `optimized_text`, `model_ids` (registry), `custom_models` (user-entered, at most 10), `expected_output_tokens`, `fallback_encoding`.
- **Token counts**:
  - Each model's input is counted with its configured tiktoken encoding.
  - A model without an encoding is counted with `fallback_encoding`, and `encoding_status: fallback_encoding` is shown.
  - Every count has `count_status: "estimate"`, because an encoding count is not provider billing.
- **Cost formula**: `tokens / 1,000,000 × price per 1M` for input and output.
  - When `optimized_text` is given, the response also has the optimized cost, the savings and the savings percent.
- **Price provenance (`price_status`)**:
  - `verified`: the registry entry has `source_url` and `verified_at`.
  - `unverified`: a registry price without that provenance.
  - `user_entered`: the price came from the browser.
  - `missing`: no price; no cost is computed.
- **Warnings**: mixed currencies and unknown model ids produce warnings.
- **UI** (`/cost`):
  - Text mode calls the backend, with an optional comparison against the optimized prompt.
  - Manual mode keeps the existing local formula.
  - User models can be saved for the other screens (browser `localStorage` only).

## Feature 7 — Smart Model Recommendation (`rec_rules_v1`)

- **Endpoint**: `POST /api/models/recommend`. Rule-based and deterministic; it makes no AI calls.
- **Exclusions**: a model is excluded, with the reason stated, when:
  - it is marked `unsupported` for the language;
  - it does not meet `require_language_support` (`verified` / `claimed` / `any`);
  - the prompt plus expected output exceeds its context window;
  - `min_context_tokens` is set and its context window is unknown;
  - a required task is missing;
  - it is below `min_quality_tier`.
- **Ranking by `cost_preference`**:
  - `lowest`: cost, then language support, then quality tier.
  - `quality`: quality tier, then support, then cost.
  - `balanced`: support, then cost, then quality.
- **Labels**: unknown cost, support or quality is ranked last and named as a limitation.
- **Locking**: `locked_model_id` keeps the user's manual choice, even when the rules would exclude it (a warning is shown).
- **UI** (`/models`):
  - Recommend button, ranked and excluded tables with reasons, manual pick and Lock.
  - An "Add user-entered model" panel.
  - The old mock preview was removed. Latency stays disabled, because there is no measured data.

## Feature 8 — Voice-to-Optimized Prompt (`pipeline_v1`)

- **Endpoints**:
  - `POST /api/pipeline/analyze`: token count, then Feature 3 optimization in safe mode by default (gated by the Feature 5 meaning check), then recommendation, then cost, then `next_step`.
  - `POST /api/pipeline/apply`: applies the user-approved edits. Edits are validated (no overlap, within bounds), and the meaning check runs on the final text; `allowed: false` when it reports `changed`.
  - `POST /api/voice/transcribe`: server transcription through any OpenAI-compatible `/audio/transcriptions` endpoint.
    - Input: base64 audio in JSON, at most 10 MB of audio.
    - Without `STT_*` it returns **503 `stt_not_configured`**.
    - Audio is never simulated and never stored. Transcripts are labelled `provider_transcript`.
- **UI** (`/voice`), with three ways to get the text:
  - browser speech input, as before;
  - server recording, when STT is configured;
  - typing.

  The flow is: Process prompt → approve uncertain changes → Apply → original vs final comparison.

## Feature 9 — Smart AI Chatbot

- **`POST /api/chat`**: analysis mode, which always works.
  - The reply starts with "REDUTAX analysis mode — this is not a live AI conversation."
  - It contains the same analysis as Feature 8.
  - The response has `llm_available`.
- **`POST /api/chat/{session_id}/send`**: sends the approved prompt and the earlier sent turns to the configured LLM (any OpenAI-compatible `/chat/completions` endpoint).
  - Without `LLM_*` it returns **503 `llm_not_configured`**.
  - Usage numbers are labelled `provider_reported`.
  - Provider failures: timeout or HTTP error → 502 `provider_error`; HTTP 429 → 429 `provider_rate_limited` (with the provider's Retry-After). A failed send never changes the history.
- **`GET` / `DELETE /api/chat/{session_id}`**: history, or end the session; returns 404 for an unknown session.
- **Sessions**: held in backend memory only.
  - Limits: 200 sessions, 40 turns each, removed after 2 h idle.
  - Lost on restart. Never written to the database or logs.
- **UI** (`/chat`):
  - Analyse → transcript with an "analysis" badge → approve suggestions → Apply approved edits → Send to model.
  - Send to model is disabled, with the reason shown, when no LLM is configured.

## Feature 10 — Vapi telephone assistant (prepared, not live)

- **`POST /api/vapi/webhook`**:
  - **Auth**: Bearer / `X-Vapi-Secret` and/or HMAC-SHA256 over `{timestamp}.{body}`. Comparisons are constant-time. The HMAC timestamp header is required and must be within 5 minutes (replay protection).
  - **Responses, in check order**: 413 → 503 `vapi_not_configured` (no secret on the server) → 401 `unauthorized` (missing/wrong credential) → 422 → 200. Tool results are `{"toolCallId", "name", "result" | "error"}`, always HTTP 200. Checked against Vapi's OpenAPI spec on 2026-11-21.
  - **Limits**: 1 MB body; per-tool timeout.
  - **Tools**: `detect_language`, `analyze_tokens`, `optimize_prompt` (safe mode only), `check_meaning`, `recommend_model`, `estimate_cost`. They wrap the same services as the web screens.
  - **Logs**: event type, call id, tool, outcome and duration only.
- **`GET /api/vapi/status`**: auth modes and tool list; never secrets.
- **Assistant definition**: `config/vapi/redutax-assistant.json`. Provider and model fields are placeholders.
- **Remaining steps**: in `docs/VAPI_FINAL_CONNECTION_GUIDE.md`.
- **UI**:
  - `/voice` shows Implemented / Secret not set / Live call verified: Not yet.
  - `/settings` shows the provider statuses.

## Cross-feature integration

- `/api/pipeline/analyze` is shared by Voice (8) and Chat (9). It chains Features 1 → 3/5 (6 in aggressive mode) → 7 → 4.
- The six Vapi tools (10) call the same services directly (tokenizer counting, optimizer in safe mode, meaning check, recommendation, cost). They need no LLM or STT provider.
- User-entered models are saved once (`redutax:custom-models` in the browser). Cost, Models, Chat and Voice all send them to the backend with `source: "user"`, so every result labels them.
- `GET /api/integrations/status` reports these components, never secret values:
  - database;
  - registry;
  - STT;
  - LLM;
  - Vapi.

## API reference (Phase 2)

| Method | Path | Success | Errors |
|---|---|---|---|
| GET | `/api/models` | `ModelRegistryResponse` | 503 `registry_invalid` |
| POST | `/api/cost/estimate` | `CostEstimateResponse` | 422, 503 `registry_invalid` / `tokenizer_unavailable` |
| POST | `/api/models/recommend` | `RecommendResponse` | 422, 503 |
| POST | `/api/pipeline/analyze` | `AnalyzeResponse` | 400 `unknown_tokenizer`, 422, 503 |
| POST | `/api/pipeline/apply` | `ApplyEditsResponse` | 422 (overlapping / out-of-range edits) |
| POST | `/api/voice/transcribe` | `TranscribeResponse` | 422, 503 `stt_not_configured`, 429 `provider_rate_limited`, 502 `provider_error` |
| POST | `/api/chat` | `ChatAnalyzeResponse` | 422, 503 |
| POST | `/api/chat/{id}/send` | `ChatSendResponse` | 404, 503 `llm_not_configured`, 429 `provider_rate_limited`, 502 `provider_error` |
| GET | `/api/chat/{id}` | `ChatHistoryResponse` | 404 |
| DELETE | `/api/chat/{id}` | 204 | 404 |
| GET | `/api/integrations/status` | `IntegrationsResponse` | — |
| GET | `/api/vapi/status` | `VapiStatusResponse` | — |
| POST | `/api/vapi/webhook` | 200 `{"results":[…]}` or `{}` | 401 `unauthorized`, 413, 422 `invalid_request`, 503 `vapi_not_configured` |

- Errors use `{"error": {"code", "message"}}`.
- Types are in `backend/app/schemas.py`, mirrored in `frontend/lib/api/types.ts`.
- Interactive docs: `http://localhost:8000/docs`.

## Environment variables (all optional; placeholders in `.env.example`)

| Variable | Used by | Effect when unset |
|---|---|---|
| `REDUTAX_MODELS_REGISTRY` | 4, 7 | Uses `config/models.yaml` (empty) |
| `STT_BASE_URL`, `STT_API_KEY`, `STT_MODEL` | 8 | `/api/voice/transcribe` → 503; browser voice and typing still work |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_PROVIDER_NAME`, `LLM_TIMEOUT_SECONDS` (30) | 9 | Chat stays in analysis mode; `/send` → 503 |
| `VAPI_WEBHOOK_SECRET` | 10 | With no Vapi secret, the webhook refuses all requests (503) |
| `VAPI_HMAC_SECRET`, `VAPI_HMAC_SIGNATURE_HEADER` (`x-signature`), `VAPI_HMAC_TIMESTAMP_HEADER` (`x-timestamp`) | 10 | HMAC disabled |
| `VAPI_TOOL_TIMEOUT_SECONDS` (8) | 10 | — |

- Keys stay in the backend `.env` and never reach the frontend.
- `/api/integrations/status` and the startup log show only "configured" and the URL scheme.
- Using a paid provider needs team approval first (CLAUDE.md).

### Adding a verified model to the registry

```yaml
models:
  - id: <provider-model-id>
    provider: <Provider>
    encoding: o200k_base            # only if the provider documents it; else omit (fallback is labelled)
    encoding_source: <URL>
    context_window_tokens: <int>
    pricing: {currency: USD, input_per_1m: <num>, output_per_1m: <num>, source_url: <URL>, verified_at: 2026-11-21}
    languages: {kn: claimed, hi: claimed}   # verified | claimed | unknown | unsupported
    language_source: <URL>
    tasks: [general, summarization]
    quality_tier: 3                 # only with quality_source
    quality_source: <URL or internal eval id>
```

## Testing

```bash
cd backend
pytest tests/test_phase2.py tests/test_vapi.py tests/test_api_phase2.py    # no network, no keys
python scripts/run_db_tests.py .. tests -q --basetemp .pytest_tmp          # full suite incl. PostgreSQL (test branch)
cd ../frontend && npx tsc --noEmit && npx vitest run && npm run build
```

- Providers are tested with `httpx.MockTransport`. Vapi is tested with signed and unsigned mock events. No test calls a real provider.

## Limitations

- The registry is empty until the team adds verified models. Until then, recommendation and cost use user-entered data, which is labelled as such.
- Token counts use public tiktoken encodings. They are estimates, not provider billing; which hosted model uses which encoding must come from the provider.
- Recommendation is rule-based on configured metadata. There is no task-quality evaluation and no latency data.
- Chat sessions are kept in memory: one backend process, lost on restart.
- Server STT and LLM work with OpenAI-compatible APIs only; other APIs need a new adapter.
- Kannada, Tamil and Telugu STT quality depends on the chosen provider (open question).
- `detect_language` uses the script. It cannot separate English from Romanized Indic text, or Hindi from Marathi.
- Vapi has been tested with mocked events and with live HTTP requests to a local backend (throwaway secrets), not with a real Vapi call. A live call is still pending (see the connection guide).
- Analysis-mode optimization is safe mode by default. Indic negation lists still await native-speaker review, so many Indic edits are reported `at_risk` and need approval.
