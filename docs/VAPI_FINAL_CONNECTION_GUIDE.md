# Vapi final connection guide (Feature 10)

The REDUTAX side is built and tested:
- **Mocked Vapi events:** `backend/tests/test_vapi.py`, 34 tests.
- **Live HTTP check (2026-11-21):** a local backend with throwaway secrets passed 26/26 checks.
- **Spec check (2026-11-21):** the assistant JSON and the webhook contract were compared with Vapi's documentation and its OpenAPI spec (`https://api.vapi.ai/api-json`).

**No live telephone call has been verified yet.** Mark the integration live in `docs/STATUS.md` only after a real call succeeds.

## What REDUTAX provides

| Item | Value |
|---|---|
| Webhook (server URL) | `POST <PUBLIC_BACKEND_URL>/api/vapi/webhook` |
| Status check | `GET <PUBLIC_BACKEND_URL>/api/vapi/status`: auth modes and tool list, never secrets |
| Bearer authentication | env `VAPI_WEBHOOK_SECRET`; header `Authorization: Bearer <secret>`, or the legacy `X-Vapi-Secret: <secret>` with no prefix |
| HMAC authentication (optional) | env `VAPI_HMAC_SECRET`. SHA256 over `{timestamp}.{body}`, hex-encoded (a `sha256=` prefix is accepted). Headers `x-signature` and `x-timestamp`; **the timestamp is required** and must be within 5 minutes (seconds or milliseconds) |
| Tools | `detect_language`, `analyze_tokens`, `optimize_prompt`, `check_meaning`, `recommend_model`, `estimate_cost` |
| Tool request | `message.type = "tool-calls"`. Calls are read from `toolCallList`, or from `toolWithToolCallList` only when the first is empty, so a call is never run twice. `function.arguments` may be a JSON string (the spec type) or an object |
| Tool response | HTTP 200 `{"results":[{"toolCallId":"…","name":"…","result":"<flat JSON string>"}]}`. A failed tool returns `"error"` instead of `"result"`, still with HTTP 200 |
| Other events | `status-update`, `end-of-call-report`, `transcript` and the rest get HTTP 200 `{}`. Their content is not stored or logged |
| Timeouts | Each tool is limited to `VAPI_TOOL_TIMEOUT_SECONDS` (default 8 s), then returns an `error` string. Vapi's own server timeout defaults to 20 s, so REDUTAX always answers first |
| Logging | Event type, Vapi call id, tool name, outcome and duration only. Never transcripts, arguments or secrets |
| External providers | None. The tools run REDUTAX's local services (tiktoken, optimizer, meaning check, recommendation, cost) and **do not need** `LLM_*` or `STT_*` |
| Assistant definition | `config/vapi/redutax-assistant.json`, with placeholders `<PUBLIC_BACKEND_URL>`, `<VAPI_CREDENTIAL_ID>`, `<LLM_PROVIDER>`, `<LLM_MODEL>`, `<TRANSCRIBER_PROVIDER>`, `<TRANSCRIBER_MODEL>`, `<TRANSCRIBER_LANGUAGE_OR_MULTI>`, `<VOICE_PROVIDER>`, `<VOICE_ID>` |

### HTTP responses, in the order they are checked

| # | Condition | Response |
|---|---|---|
| 1 | Body over 1 MB | 413 `payload_too_large` |
| 2 | **No secret configured on the server** (`VAPI_WEBHOOK_SECRET` and `VAPI_HMAC_SECRET` both empty) | 503 `vapi_not_configured`, whatever headers are sent |
| 3 | Secret configured, but the credential is missing, wrong, lacks the `Bearer ` prefix, or the HMAC is wrong, unsigned by timestamp, older than 5 min or tampered | 401 `unauthorized` |
| 4 | Authenticated, but the body is not a JSON object with a `message` object | 422 `invalid_request` |
| 5 | Authenticated `tool-calls` | 200 `{"results":[…]}`, including per-tool errors |
| 6 | Authenticated non-tool event | 200 `{}` |

So 503 means the server isn't set up yet, and 401 means the server is set up but the request isn't authorized.

Vapi ignores non-200 responses to tool calls. During a call, a 401 or 503 shows up as a failed tool, and the assistant follows its prompt rule to apologise and continue.

## Call flow

```
Caller speaks → Vapi transcriber (speech → text)
             → Vapi assistant model (<LLM_PROVIDER>/<LLM_MODEL>, configured in Vapi)
                 ├─ calls REDUTAX tools when useful ──► POST /api/vapi/webhook
                 │     detect_language · analyze_tokens · optimize_prompt (safe) ·
                 │     check_meaning · recommend_model · estimate_cost
                 │     (same services as the web app) ◄── flat JSON result strings
                 └─ writes the reply using those results
             → Vapi voice (text → speech) → caller hears the reply
```

- The model you configure **in Vapi** generates the spoken reply. REDUTAX supplies the analysis through the tools.
- The backend's `LLM_*` adapter (Feature 9 chat) is separate and is not used during calls.

## Step 1 — Make the backend reachable over HTTPS

- **Deployed backend:** use its HTTPS URL as `<PUBLIC_BACKEND_URL>`.
- **Local testing:** start the backend (`cd backend && uvicorn app.main:app --port 8000`), then run a tunnel such as `cloudflared tunnel --url http://127.0.0.1:8000` or `ngrok http 8000`. Use the printed `https://…` URL. Tunnel URLs change on restart, so update Vapi when they do.

Check: `curl <PUBLIC_BACKEND_URL>/health` returns `"status": "ok"`.

## Step 2 — Set the webhook secret on the backend

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add it to the repository-root `.env`, which is git-ignored and must never be committed:

```
VAPI_WEBHOOK_SECRET=<the generated secret>
# optional, for an HMAC credential instead of bearer:
# VAPI_HMAC_SECRET=<another generated secret>
# VAPI_TOOL_TIMEOUT_SECONDS=8
```

Restart the backend, then run `curl <PUBLIC_BACKEND_URL>/api/vapi/status`. Expect:
- `"auth_configured": true`;
- `"auth_modes": ["bearer", "x-vapi-secret"]`, plus `"hmac-sha256"` if the HMAC secret is set;
- `"live_call_verified": false`.

## Step 3 — Create the matching credential in Vapi

In the Vapi dashboard, create a webhook credential. Use one of these:

- **Bearer token (recommended):**
  - token: the same value as `VAPI_WEBHOOK_SECRET`;
  - header name: `Authorization`;
  - *Include Bearer Prefix*: **on**.
- **Legacy variant:** header name `X-Vapi-Secret`, *Include Bearer Prefix* **off**.
- **HMAC:**
  - secret: `VAPI_HMAC_SECRET`;
  - algorithm: SHA256;
  - signature header: `x-signature`;
  - timestamp header: `x-timestamp` (**required by REDUTAX**);
  - payload format: `{timestamp}.{body}`;
  - signature encoding: Hex.

  If you use other header names, set `VAPI_HMAC_SIGNATURE_HEADER` and `VAPI_HMAC_TIMESTAMP_HEADER` to match.

Note the credential id (`cred_…`); it replaces `<VAPI_CREDENTIAL_ID>`.

**Important:** Vapi attaches a credential only when the server URL comes from a **saved** assistant, tool, phone number or org setting. With a transient assistant (defined inline in `POST /call` or `assistantOverrides`), Vapi sends no credential, and REDUTAX answers 401. Always use the saved assistant from Step 5.

## Step 4 — Choose the speech, voice and model providers

REDUTAX doesn't make these choices for you; they are open decisions in `docs/decisions.md`.

- **Transcriber** (`transcriber.provider`, `model`, `language`):
  - Some transcribers in Vapi's API list the codes `kn`, `hi`, `ta`, `te` (e.g. Deepgram's `language` enum), and some list `multi`.
  - A code in the schema does not prove good recognition. Check the provider's documentation for each language and model, then test.
- **Voice** (`voice.provider`, `voiceId`):
  - The provider values are Vapi's, e.g. `11labs` for ElevenLabs and `azure` for Azure.
  - The voice must speak the caller's languages.
- **Model** (`model.provider`, `model.model`): the LLM Vapi uses to talk and to call the tools. The value must be one Vapi lists for that provider.

## Step 5 — Create the assistant

**Option A — API, using the prepared JSON:**

1. Copy `config/vapi/redutax-assistant.json` to `config/vapi/redutax-assistant.filled.json`. That name is git-ignored.
2. Replace every `<…>` placeholder.
3. Send it:

```bash
curl -X POST https://api.vapi.ai/assistant \
  -H "Authorization: Bearer <YOUR_VAPI_PRIVATE_API_KEY>" \
  -H "Content-Type: application/json" \
  --data @config/vapi/redutax-assistant.filled.json
```

The response contains the assistant `id`. Keep your Vapi private API key out of the repository; the backend does not need it.

**Option B — Dashboard:**

1. Create an assistant named *REDUTAX Indic AI Assistant*.
2. Paste the `firstMessage` and the system message from the JSON.
3. Set the transcriber, voice and model.
4. Create six **Function** tools using the names, descriptions and parameter schemas from `model.tools` in the JSON. Give each one server URL `<PUBLIC_BACKEND_URL>/api/vapi/webhook` and your credential.
5. Attach all six tools to the assistant.
6. Set the assistant's server URL and credential to the same values.
7. Enable the server messages `tool-calls`, `status-update` and `end-of-call-report`.

## Step 6 — Attach a phone number

Buy or import a number in Vapi and assign **the REDUTAX assistant** to it.

Don't route the number through a server URL instead of an assistant. Vapi would then send `assistant-request` events, which REDUTAX doesn't answer (it replies `{}`), and the call would end.

## Step 7 — Verify the webhook before calling

Run this in a bash shell (Git Bash on Windows, macOS or Linux) and replace the two placeholders.

The Kannada word ನಮಸ್ಕಾರ is written as `\u` escapes so the shell can't garble it. Indic text typed directly on the Windows command line arrives at the server as `?`.

```bash
curl -s -X POST <PUBLIC_BACKEND_URL>/api/vapi/webhook \
  -H "Authorization: Bearer <VAPI_WEBHOOK_SECRET>" -H "Content-Type: application/json" \
  -d '{"message":{"type":"tool-calls","call":{"id":"manual-test"},"toolCallList":[{"id":"t1","type":"function","function":{"name":"detect_language","arguments":"{\"text\":\"\\u0ca8\\u0cae\\u0cb8\\u0ccd\\u0c95\\u0cbe\\u0cb0\"}"}}]}}'
```

Alternative: save the JSON body as a UTF-8 file and send it with `--data-binary @vapi-test.json`.

Expected response (verified with this exact command against a local backend on 2026-11-21):

```json
{"results":[{"toolCallId":"t1","name":"detect_language","result":"{\"script\":\"Knda\",\"language\":\"kn\",\"note\":\"\"}"}]}
```

Also check:
- without the header: HTTP 401 `unauthorized`;
- with no secret on the server: HTTP 503 `vapi_not_configured`.

## Step 8 — Test calls

Call the number and try each language. Say these naturally:

| Language | Try saying | Expect the assistant to |
|---|---|---|
| Kannada | "ನನ್ನ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ, ಆದರೆ ₹೫೦೦ ಮೊತ್ತವನ್ನು ಬದಲಿಸಬೇಡಿ" | answer in Kannada; may call `detect_language`, `optimize_prompt` |
| Hindi | "इस संदेश को छोटा करो, लेकिन कल शाम 5 बजे वाली बात मत हटाना" | keep "5 बजे" and the negation |
| Tamil | "இந்த செய்தியைச் சுருக்கவும், தேதியை மாற்ற வேண்டாம்" | answer in Tamil |
| Telugu | "ఈ సందేశాన్ని చిన్నదిగా చేయండి, కానీ మొత్తాన్ని మార్చవద్దు" | answer in Telugu |

The developers wrote these sentences; ask native speakers to confirm them.

**Verify the tool calls on the backend.** The log shows one line per tool call, with no content, for example:

```
INFO redutax.vapi vapi tool call=<vapi-call-id> tool=optimize_prompt outcome=result ms=42
```

Match `<vapi-call-id>` with the call in the Vapi dashboard's call log, where the tool results also appear.

When a real call works end to end, record it in `docs/STATUS.md`: the date, languages tested, transcriber and voice used. Only then should the team change `liveCallVerified` in the JSON metadata and the hard-coded `live_call_verified=False` in `backend/app/api/phase2.py` (`vapi_status`). Until then the integration is **prepared, not live**.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tool calls fail and the backend log shows nothing | Vapi cannot reach the URL | Check that the tunnel or deployment URL uses HTTPS; run `curl <URL>/health` |
| HTTP 401 `unauthorized` | Secret mismatch, wrong header, Bearer prefix setting, or a transient assistant (no credential sent) | Make the credential match `VAPI_WEBHOOK_SECRET`. Prefix **on** for `Authorization`, **off** for `X-Vapi-Secret`. Use the saved assistant |
| HTTP 503 `vapi_not_configured` | No secret in the backend environment | Set `VAPI_WEBHOOK_SECRET` (or `VAPI_HMAC_SECRET`) and restart |
| HMAC requests get 401 | Timestamp header off, payload format, header names, encoding or clock skew | Enable `x-timestamp`; use `{timestamp}.{body}`, SHA256, Hex; keep the server clock in sync (±5 min) |
| `error: Tool '…' timed out after 8 s` | Slow first token count or cold start | Raise `VAPI_TOOL_TIMEOUT_SECONDS` (keep it below Vapi's 20 s server timeout); warm up with `/health` |
| `recommend_model` / `estimate_cost` say no models are configured | Empty registry | Add verified models to `config/models.yaml` |
| Replies in the wrong language | Transcriber language setting, or Latin-script input | Set the transcriber language. `detect_language` cannot tell English from Romanized Indic text |
| Call ends right after connecting | Number routed via server URL (`assistant-request`) instead of an assistant | Assign the assistant to the phone number |
| HTTP 413 | Body over 1 MB | Unexpected for Vapi tool calls; check what is calling the webhook |
