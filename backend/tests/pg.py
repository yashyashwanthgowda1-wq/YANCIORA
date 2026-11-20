"""PostgreSQL test fixtures.

Set TEST_PSQL_URL to a *server* URL, e.g. postgresql://redutax:redutax@localhost:5432/postgres.
Each test module gets its own throwaway database, migrated with the real Alembic chain
(upgrade head), and dropped afterwards. Tests are skipped when TEST_PSQL_URL is unset or
the server is unreachable. Needs no `psql` binary.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

SERVER_URL = os.environ.get("TEST_PSQL_URL")
BACKEND = Path(__file__).resolve().parents[1]

requires_pg = pytest.mark.skipif(not SERVER_URL, reason="TEST_PSQL_URL not set")


def sa_url(url: str) -> str:
    """postgresql://... → postgresql+psycopg://... (SQLAlchemy psycopg3 driver)."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def with_database(url: str, name: str) -> str:
    """Same server URL pointing at another database, keeping query options such as
    Neon's ?sslmode=require."""
    base, sep, query = url.partition("?")
    return base.rsplit("/", 1)[0] + "/" + name + (sep + query if sep else "")


def alembic(db_url: str, action: str, target: str) -> None:
    from alembic import command
    from alembic.config import Config

    from app.core.config import get_settings

    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    try:
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND / "migrations"))
        getattr(command, action)(cfg, target)
    finally:
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def pg_url():
    if not SERVER_URL:
        pytest.skip("TEST_PSQL_URL not set")
    from sqlalchemy import create_engine, text

    server = create_engine(sa_url(SERVER_URL), isolation_level="AUTOCOMMIT")
    name = f"redutax_test_{uuid.uuid4().hex[:8]}"
    try:
        with server.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    except Exception as exc:  # noqa: BLE001
        server.dispose()
        pytest.skip(f"PostgreSQL unreachable: {type(exc).__name__}")
    url = with_database(sa_url(SERVER_URL), name)
    alembic(url, "upgrade", "head")
    yield url
    from app.db.session import get_engine

    get_engine(url).dispose()
    get_engine.cache_clear()
    with server.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    server.dispose()


@pytest.fixture(scope="module")
def pg_engine(pg_url):
    from sqlalchemy import create_engine

    eng = create_engine(pg_url)
    yield eng
    eng.dispose()


def truncate_all(engine) -> None:
    from sqlalchemy import text

    with engine.begin() as c:
        c.execute(text("TRUNCATE benchmark_summaries, token_benchmarks, benchmark_runs, "
                       "tokenizers, dataset_imports, dataset_samples, datasets RESTART IDENTITY CASCADE"))
