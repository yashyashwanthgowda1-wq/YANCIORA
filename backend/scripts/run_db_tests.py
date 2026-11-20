"""Run pytest with TEST_PSQL_URL from the repo .env, isolated from production.
- Refuses to run if the test host equals the production host.
- Sets DATABASE_URL in THIS process to the test branch too, so the production URL is never
  loaded by any test (the app's .env loader only fills variables that are not already set).
Prints no secrets.
Usage (from the repo root): python backend/scripts/run_db_tests.py . [pytest args...]
  e.g. python backend/scripts/run_db_tests.py . tests -q --basetemp .pytest_tmp"""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

root = Path(sys.argv[1])
vals = {}
for raw in (root / ".env").read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].strip()
    if "=" in line:
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
test, prod = vals.get("TEST_PSQL_URL"), vals.get("DATABASE_URL")
if not test or not prod:
    sys.exit("TEST_PSQL_URL and DATABASE_URL must both be set in .env")
if urlsplit(test).hostname == urlsplit(prod).hostname:
    sys.exit("REFUSING: TEST_PSQL_URL and DATABASE_URL point to the same host")
os.environ["TEST_PSQL_URL"] = test
os.environ["DATABASE_URL"] = test          # production URL never enters the test process
print("safety: test host != production host; DATABASE_URL in test process = test branch")
os.chdir(root / "backend")
sys.path.insert(0, str(root / "backend"))
import pytest  # noqa: E402

sys.exit(pytest.main(sys.argv[2:]))
