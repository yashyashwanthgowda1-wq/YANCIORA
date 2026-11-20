"""Database connectivity. SQLAlchemy is imported lazily so the app can start
(and report `not_configured`) before a database is set up."""
from __future__ import annotations

from functools import lru_cache
from typing import Any


@lru_cache
def get_engine(database_url: str) -> Any:
    from sqlalchemy import create_engine

    # Fail fast when the server is unreachable instead of waiting for the OS TCP timeout
    # (minutes on some machines), so /health and the API return 503 promptly.
    connect_args = {"connect_timeout": 5} if database_url.startswith("postgresql") else {}
    return create_engine(database_url, pool_pre_ping=True, pool_size=5, connect_args=connect_args)


def check_database(database_url: str | None) -> dict[str, str]:
    """Return a status dict for the health check. Never raises; never leaks credentials."""
    if not database_url:
        return {"status": "not_configured"}
    try:
        from sqlalchemy import text

        with get_engine(database_url).connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 — health check must not crash
        return {"status": "error", "error": type(exc).__name__}
