# REDUTAX — instructions for AI coding assistants

Read this file and `docs/STATUS.md` before changing anything.

## What this project is

REDUTAX (Team YANCIORA, No. 46, AI Research Track, problem *The Token Tax*) measures and reduces
unnecessary token use in Indian-language prompts while preserving meaning. Languages: Kannada
(primary), Hindi, Tamil, Telugu, English (reference); native script, Romanized and code-mixed.

Source of truth: the BRD (`REDUTAX_BRD_YANCIORA_Team46_v1.docx`), then the PRD. The UI/UX brief
for the frontend is a separate document given to Grok; its API types must match `backend/app/schemas.py`.

## Hard rules

- Do not invent research results, dataset contents, dataset licences, model prices, language
  support or completed integrations. Unknown = `TO_VERIFY` or an open question in `docs/decisions.md`.
- Every token count must carry its tokenizer name + version and a status
  (`exact | estimate | provider_reported | research | mock | unsupported`).
- A fertility ratio is a tokenization ratio, never a cost multiplier.
- The experimental SentencePiece tokenizer is research only; it cannot change hosted-model billing.
- Never train an LLM. Phase 2 trains only SentencePiece Unigram tokenizers.
- Secrets only in `.env` (git-ignored). `.env.example` holds placeholders.
- Ask the team before: major architecture changes, paid API usage, deployment, deleting work,
  anything exposing user data.
- Work one phase at a time. After each phase: run tests, update `docs/STATUS.md`, list files
  changed, commands run, results and limitations.

## Layout

- `backend/app/core/` — settings, text normalization (`text.py`), metrics, critical-detail
  extraction (`details.py`, negation lists in `lexicons/`)
- `backend/app/tokenizers/` — adapter interface, tiktoken adapter, registry
- `backend/app/optimizer/` — optimizer rules (`rules.py`) and phrase lists (`phrases/*.yaml`)
- `backend/app/services/` — counting/compare, dataset validation, benchmark logic, meaning
  check, optimizer, models/cost/recommendation, pipeline, chat (framework-free)
- `backend/app/integrations/` — external adapters: `providers.py` (OpenAI-compatible STT/LLM), `vapi.py` (webhook auth + tools). Inactive until env vars are set; tested with mocks only
- `backend/app/api/` — FastAPI routes; `errors.py` gives `{"error": {"code", "message"}}`
- `backend/app/schemas.py` — request/response models (mirror of the frontend's `lib/api/types.ts`)
- `backend/migrations/` — Alembic; schema SQL in `migrations/sql/`
- `config/models.yaml` — model/price registry (ships empty; verified entries only, D42); `config/vapi/redutax-assistant.json` — Vapi assistant with placeholders (`docs/VAPI_FINAL_CONNECTION_GUIDE.md`)
- `research/configs/` — licence register `datasets.yaml`, `normalization.md`, `meaning_check.md`, `optimizer.md`, `transliteration.md`
- `research/scripts/` — `flores_to_jsonl.py`, `import_pilot.py`, `run_benchmark.py`
- `frontend/` — to be filled with the Grok-generated Next.js app

## Commands

```bash
docker compose up -d db
cd backend && pip install -e ".[dev,research]"
pip install --no-deps --require-hashes -r requirements-translit.txt
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000/docs
pytest                                   # add TEST_PSQL_URL=... for schema tests
```

## Conventions

- Business logic lives in `services/` and stays importable without FastAPI; routes stay thin.
- New behaviour in `core/text.py` → bump `NORMALIZATION_ID` / `WORD_COUNT_METHOD`.
- Tests use `tests/conftest.py::FakeTokenizer` for logic; real-tokenizer tests skip when the
  library or its files are missing.
