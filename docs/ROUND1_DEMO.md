# Round 1 demo — runbook

Five backend features connected to the existing frontend (branch `integration/round1`, built on
`frontend/ui-phase`; not merged or pushed until the team approves). **No database is needed.**

| Feature | Screen | Endpoints |
|---|---|---|
| Multilingual Token Counter | Token Counter (`/counter`) | `POST /api/tokenize` |
| Language Comparison Engine | Language Comparison (`/compare`) | `POST /api/compare-languages` |
| Script and Transliteration Optimizer | Language Comparison → *Script variants* panel | `POST /api/script-variants` |
| Smart Prompt Optimizer | Prompt Optimizer (`/optimize`) → *Automatic optimization* | `POST /api/optimize` |
| Meaning Preservation Checker | Prompt Optimizer → *Your rewrites* ledger, result panels, *Critical details* | `POST /api/meaning-check`, `POST /api/critical-details` |

## 1. Backend (terminal 1)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                       # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,research]"
pip install --no-deps --require-hashes -r requirements-translit.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Check: <http://127.0.0.1:8000/health> → `"status": "ok", "database": {"status": "not_configured"}` (fine for the demo).
API docs: <http://127.0.0.1:8000/docs>.

### tiktoken encoding files (one-time, needs internet)

tiktoken downloads `cl100k_base` / `o200k_base` on first use. On networks that intercept HTTPS
(antivirus / proxy), Python fails with `CERTIFICATE_VERIFY_FAILED` and the UI shows
`503 tokenizer_unavailable`. Fix without disabling verification — fetch with curl (Windows
certificate store) into tiktoken's cache; tiktoken checks each file's SHA-256 before use:

```bash
# Git Bash, from backend/ with the venv's python
CACHE=$(python -c "import tempfile,os;print(os.path.join(tempfile.gettempdir(),'data-gym-cache'))")
mkdir -p "$CACHE"
for enc in cl100k_base o200k_base; do
  URL="https://openaipublic.blob.core.windows.net/encodings/$enc.tiktoken"
  curl -sS --retry 5 -o "$CACHE/$(printf %s "$URL" | sha1sum | cut -d' ' -f1)" "$URL"
done
python -c "from app.tokenizers import get_tokenizer; print(get_tokenizer('cl100k_base').count('ನಮಸ್ಕಾರ'))"
```

Expected SHA-256 (built into tiktoken): cl100k `223921b7…`, o200k `446a9538…`. Before a live demo,
do this on the demo machine while online.

## 2. Frontend (terminal 2)

```bash
cd frontend
npm ci
npm run dev                                   # http://localhost:3000
```

Optional `frontend/.env.local` (public values only):
`NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` (default is `http://localhost:8000`).

## Environment variables

| Variable | Where | Needed for the demo? |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `frontend/.env.local` | No (default `http://localhost:8000`) |
| `REDUTAX_CORS_ORIGINS` | root `.env` | No — default allows `http://localhost:3000`. Add other origins (e.g. `http://127.0.0.1:3000`) comma-separated if you open the UI elsewhere |
| `DATABASE_URL` | root `.env` | **No.** Only the aligned-sample loader (Compare) and Research Dashboard need it; without it they show `database_not_configured` |
| `TIKTOKEN_CACHE_DIR` | shell | No — only if you keep the encoding files somewhere other than the default cache |

No secrets are needed for these five features.

## Suggested demo script (all verified through the UI)

1. **Token Counter** — paste Kannada text, count with `cl100k_base`, then `o200k_base` (e.g. 118 vs 32 tokens for the sample sentence).
2. **Language Comparison** — English / Kannada / Hindi variants → *Compare* (unaligned warning, tokens-per-word ratios labelled "not a cost multiplier").
3. **Script variants** — same page: Kannada variant → ISO 15919 + Baraha → token change, *Lossless*, *Needs your review*, warnings → *Add to comparison*. Tamil shows the Sanskrit-style warning; Romanized → native with *Everyday Romanized typing* returns *Not supported*.
4. **Prompt Optimizer** — English prompt with extra spaces → *Optimize*: accepted edits, token before/after, meaning check *Preserved*, critical-detail chips.
   Kannada prompt with `!!!!!!` and a zero-width space → those edits appear under *Suggestions — not applied* (*At risk · review*), because the Kannada negation list is not native-speaker-reviewed yet.
   `Pay Rs.   500 now.` → original kept; the space fix is rejected because it would turn the number into a money amount.
5. **Units (rules_v2)** — original "Add 5 kg of rice and wait 3 days.", rewrite "Add 5 g of rice and wait 3 days." → *Changed / Rejected*; "Add 5kg …" → *Preserved*.
6. **Meaning check** — add rewrites "Pay before 5 pm." (→ *Changed*, *Rejected · details changed*: ₹500 and "not" missing) and "Don't pay more than Rs. 500 before 5 pm." (→ *Preserved*).

Note for presenters: with real tokenizers, `!!!` → `!` usually saves **no** tokens (it is already
one token), so it is correctly rejected as "no token saving". Savings on clean Indic text are small;
the point of the demo is that every change is measured, gated and explained.

## Evidence

`docs/integration/round1-ui-check.mjs` drives the real UI in Microsoft Edge (playwright-core
1.64.1, installed outside the project). Last run (2026-11-21, after `rules_v2`): **27/27 passed**
(`docs/integration/round1-ui-run.log`, `docs/integration/round1-ui-results.json`).
Screenshots: `docs/screenshots/integration/`.
