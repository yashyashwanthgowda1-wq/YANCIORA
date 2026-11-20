"""Applies 0001_initial.sql to a throwaway database and checks the constraints.

Needs `psql` and TEST_PSQL_URL, e.g. postgresql://redutax:redutax@localhost:5432/postgres
(a server URL; the test creates and drops its own database). Skipped otherwise.
"""
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

SQL = Path(__file__).resolve().parents[1] / "migrations" / "sql" / "0001_initial.sql"
SERVER_URL = os.environ.get("TEST_PSQL_URL")

pytestmark = pytest.mark.skipif(
    not SERVER_URL or not shutil.which("psql"), reason="TEST_PSQL_URL/psql not available"
)


def psql(url: str, sql: str | None = None, file: Path | None = None) -> subprocess.CompletedProcess:
    cmd = ["psql", url, "-v", "ON_ERROR_STOP=1", "-tA", "-q"]
    cmd += ["-f", str(file)] if file else ["-c", sql]
    return subprocess.run(cmd, capture_output=True, text=True)


@pytest.fixture(scope="module")
def db_url():
    name = f"redutax_test_{uuid.uuid4().hex[:8]}"
    assert psql(SERVER_URL, f"CREATE DATABASE {name}").returncode == 0
    url = SERVER_URL.rsplit("/", 1)[0] + "/" + name
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
