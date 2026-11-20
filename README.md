# REDUTAX

**Indic-Aware Token Efficiency & Evaluation Framework** — Team YANCIORA (No. 46), AI Research Track, problem statement *The Token Tax*.

Specification: `REDUTAX_BRD_YANCIORA_Team46_v1.docx` (source of truth) and `REDUTAX_PRD_YANCIORA_Team46_Final.docx`.

## Status

See **[docs/STATUS.md](docs/STATUS.md)** for the full status. In short: Phase 0 and the Phase 1
code (including PostgreSQL persistence and the retrieval APIs) are done. Phase 1 finishes when:
- the PostgreSQL tests pass locally;
- the team verifies the FLORES-200 licence;
- the first baseline benchmark is run and stored.

No datasets, benchmark results, model prices or integrations exist yet.

AI assistants: read [CLAUDE.md](CLAUDE.md) first.

## Layout

```
backend/            FastAPI service (Python)
  app/core/         settings from environment variables
  app/api/          HTTP routes (/health so far)
  app/db/           database connectivity
  migrations/       Alembic; schema SQL in migrations/sql/
  tests/
research/           dataset import, normalization, tokenizer training, benchmarks (Phase 1+)
  data/raw|processed  local only, git-ignored
frontend/           web UI (stack decision pending — see frontend/README.md)
docs/               decisions and open questions
docker-compose.yml  local PostgreSQL 16
```

## Setup (local)

Requirements: Python 3.11+, Docker (or a local PostgreSQL 16).

```bash
cp .env.example .env                 # fill in values; never commit .env
docker compose up -d db              # PostgreSQL on localhost:5432

cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,research]"

alembic upgrade head                 # applies 0001 + 0002 (Phase 0/1 tables)
uvicorn app.main:app --reload        # http://localhost:8000/health
```

Interactive API docs: http://localhost:8000/docs. Try `POST /api/tokenize` with
`{"text": "ನಮಸ್ಕಾರ", "tokenizer": "cl100k_base", "include_pieces": true}`.

Expected `/health` response once the database is up:

```json
{"app": "REDUTAX", "version": "0.1.0", "env": "development", "status": "ok", "database": {"status": "ok"}}
```

If `DATABASE_URL` is unset, `database.status` is `not_configured` (HTTP 200). If it is set but unreachable, the endpoint returns HTTP 503.

## Dataset import and benchmark (PostgreSQL)

Blocked until the dataset's entry in `research/configs/datasets.yaml` is verified by the team.
Run from the repo root:

```bash
python research/scripts/flores_to_jsonl.py --flores-dir <path>/flores200_dataset --split devtest \
    --out research/data/raw/flores200_devtest.jsonl
python research/scripts/import_pilot.py --input research/data/raw/flores200_devtest.jsonl \
    --dataset FLORES-200 --load-db                 # validate + load (safe to re-run)
python research/scripts/run_benchmark.py \
    --input research/data/processed/FLORES-200/<version>/samples.jsonl --split test --store-db
```

Details and exit codes: [research/README.md](research/README.md).

## Retrieval API examples

```bash
curl "http://localhost:8000/api/samples/groups?dataset=FLORES-200&language=kn&language=en&split=test&page=1&page_size=20"
curl "http://localhost:8000/api/benchmarks?dataset=FLORES-200&tokenizer=cl100k_base"
curl "http://localhost:8000/api/benchmarks/<run_id>/results?language=kn&page_size=50"
```

All three are paginated (`page` ≥ 1, `page_size` 1–100) and return `{items, page, page_size, total}`.
Errors use `{"error": {"code", "message"}}`:
- `422 invalid_request`: a filter value is invalid.
- `404 not_found`: the dataset or run doesn't exist.
- `503 database_not_configured` / `database_unavailable`: no database, or it can't be reached.

Each sample in a group has `language`, `script`, `variant_type` and `text`, so a group can be
posted as-is to `POST /api/compare-languages`.

## Meaning preservation check (Feature 5)

`POST /api/meaning-check`

```json
{"original": "Do not pay ₹500 before 5 pm.", "candidate": "Pay $500 before 5 pm.", "language": "en"}
```

Response (abridged):

```json
{"status": "changed", "method": "rules_v1", "language": "en",
 "findings": [
   {"category": "money", "value": "INR 500", "example": "₹500", "original_count": 1, "candidate_count": 0, "state": "missing"},
   {"category": "money", "value": "USD 500", "example": "$500", "original_count": 0, "candidate_count": 1, "state": "added"},
   {"category": "datetime", "value": "5pm", "example": "5 pm", "original_count": 1, "candidate_count": 1, "state": "kept"},
   {"category": "negation", "value": "not", "example": "not", "original_count": 1, "candidate_count": 0, "state": "missing"}],
 "missing_count": 2, "added_count": 1, "risks": [], "warnings": [],
 "negation_lexicons": [{"id": "en", "language": "en", "script": "Latn", "review_status": "developer_curated"}],
 "limitations": ["Rule-based check (rules_v1): ...", "'preserved' means no rule found a problem. ..."]}
```

Statuses: `changed` (a critical detail is missing, added or altered), `at_risk` (details kept but
a heuristic warning applies), `preserved` (no rule found a problem — not a guarantee).
`POST /api/critical-details` with `{"text", "language", "protected_terms"}` lists the details with
offsets for highlighting. Rules: [research/configs/meaning_check.md](research/configs/meaning_check.md).

## Prompt optimizer (Feature 3)

`POST /api/optimize`

```json
{"text": "Please   send ₹500 today!!!", "language": "en", "mode": "safe",
 "tokenizers": ["cl100k_base", "o200k_base"], "protected_terms": []}
```

Response fields: `optimized`, `changed`, `token_counts` (before/after/saved per tokenizer, with
tokenizer identity and count status), `accepted` (applied; meaning check `preserved`),
`suggestions` (**not applied**, `requires_review: true`: at_risk edits, duplicate sentences,
script changes), `rejected` (with `stage`: protected / overlap / limit / tokens / meaning and a
reason), `requires_review`, `phrase_lists` (review status and whether applied), `meaning_check`
(Feature 5 result for original vs optimized), `warnings` (incl. "not provider billing") and
`limitations`. Modes: `safe` (whitespace, invisible characters, repeated punctuation),
`balanced` (+ reviewed phrase lists — none are reviewed yet), `aggressive` (+ script
suggestions, arriving with Feature 6). Rules: [research/configs/optimizer.md](research/configs/optimizer.md).

## Tests

```bash
cd backend
pytest                                               # everything that needs no database
TEST_PSQL_URL=postgresql://redutax:redutax@localhost:5432/postgres pytest   # + PostgreSQL tests
```

The PostgreSQL tests create a throwaway database, run the Alembic migrations on it, then drop it.
With Neon, point `TEST_PSQL_URL` at a **separate branch** (not the app database) and use the
`postgresql+psycopg://…?sslmode=require` form.
`test_schema.py` also needs `psql` on PATH. On Windows, if pytest reports `PermissionError` for its
temp folder, add `--basetemp .pytest_tmp`.

## Rules carried from the BRD

- Secrets live only in environment variables; `.env.example` holds placeholders.
- Every token count must name its tokenizer and version.
- A dataset row cannot be created without licence, source URL and access date.
- Research tokenizer counts are never presented as provider billing counts.
