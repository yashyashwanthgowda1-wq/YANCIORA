"""Applies 0001_initial.sql to a throwaway database and checks the constraints.

Needs TEST_PSQL_URL, e.g. postgresql+psycopg://redutax:redutax@localhost:5432/postgres
(a server URL on a TEST server/branch; the test creates and drops its own database).
Skipped otherwise. Statements run through psycopg (no `psql` binary needed); the helper keeps
the psql-like result shape (returncode / stdout / stderr) so the assertions are unchanged.
"""
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.pg import with_database

SQL = Path(__file__).resolve().parents[1] / "migrations" / "sql" / "0001_initial.sql"
SERVER_URL = os.environ.get("TEST_PSQL_URL")

pytestmark = pytest.mark.skipif(not SERVER_URL, reason="TEST_PSQL_URL not set")


@dataclass
class Result:
    returncode: int
    stdout: str
    stderr: str


def _conninfo(url: str) -> str:
    """psycopg takes libpq URLs: drop SQLAlchemy's '+psycopg' driver suffix."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def psql(url: str, sql: str | None = None, file: Path | None = None) -> Result:
    """Run SQL (one string or a whole file) in autocommit mode; stop at the first error,
    like `psql -v ON_ERROR_STOP=1 -tA`."""
    import psycopg

    try:
        with psycopg.connect(_conninfo(url), autocommit=True) as conn:
            cur = conn.execute(file.read_text(encoding="utf-8") if file else sql)
            rows = cur.fetchall() if cur.description else []
        return Result(0, "\n".join("|".join(str(v) for v in r) for r in rows), "")
    except psycopg.Error as exc:
        return Result(1, "", str(exc))


@pytest.fixture(scope="module")
def db_url():
    name = f"redutax_test_{uuid.uuid4().hex[:8]}"
    assert psql(SERVER_URL, f"CREATE DATABASE {name}").returncode == 0
    url = with_database(SERVER_URL, name)
    r = psql(url, file=SQL)
    assert r.returncode == 0, r.stderr
    yield url
    psql(SERVER_URL, f"DROP DATABASE {name} WITH (FORCE)")


def test_five_languages_seeded(db_url):
    out = psql(db_url, "SELECT string_agg(code, ',' ORDER BY code) FROM languages").stdout.strip()
    assert out == "en,hi,kn,ta,te"


def test_dataset_requires_license_and_source(db_url):
    r = psql(db_url, "INSERT INTO datasets (name, version, source_url, accessed_at) "
                     "VALUES ('x','1','http://x','2026-11-20')")
    assert r.returncode != 0 and "license" in r.stderr


def test_sample_split_and_variant_are_checked(db_url):
    psql(db_url, "INSERT INTO datasets (name, version, license, source_url, accessed_at) "
                 "VALUES ('pilot','0','TBD-unverified','http://x','2026-11-20')")
    base = ("INSERT INTO dataset_samples (sample_id, dataset_id, language_code, script, text, "
            "variant_type, split) SELECT '{sid}', id, 'kn', 'Knda', 't', '{vt}', '{sp}' "
            "FROM datasets WHERE name='pilot'")
    assert psql(db_url, base.format(sid="s1", vt="original", sp="test")).returncode == 0
    assert psql(db_url, base.format(sid="s2", vt="original", sp="holdout")).returncode != 0
    assert psql(db_url, base.format(sid="s3", vt="summary", sp="test")).returncode != 0
    assert psql(db_url, base.format(sid="s1", vt="original", sp="test")).returncode != 0  # dup id


def test_unknown_language_rejected(db_url):
    r = psql(db_url, "INSERT INTO dataset_samples (sample_id, dataset_id, language_code, script, "
                     "text, variant_type, split) SELECT 'z1', id, 'xx', 'Latn', 't', 'original', "
                     "'test' FROM datasets WHERE name='pilot'")
    assert r.returncode != 0
