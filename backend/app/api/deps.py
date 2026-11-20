"""Shared API dependencies: database engine + safe error translation."""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator

from fastapi import Depends

from app.api.errors import ApiException
from app.core.config import Settings, get_settings
from app.db.session import get_engine
from app.services.dataset_store import NotFound

logger = logging.getLogger("redutax.api")


def get_db(settings: Settings = Depends(get_settings)) -> Any:
    """SQLAlchemy Engine for the configured DATABASE_URL, or a 503 if none is set."""
    if not settings.database_url:
        raise ApiException(503, "database_not_configured",
                           "The database is not configured on this server.")
    return get_engine(settings.database_url)


@contextmanager
def db_errors() -> Iterator[None]:
    """NotFound → 404. Any database failure → 503 with a generic message; details
    (which may include hosts or SQL) go to the server log only, never to the client."""
    from sqlalchemy.exc import SQLAlchemyError

    try:
        yield
    except NotFound as exc:
        raise ApiException(404, "not_found", str(exc))
    except SQLAlchemyError as exc:
        logger.error("database error: %s", type(exc).__name__)
        raise ApiException(503, "database_unavailable",
                           "The database is unavailable. Try again later.")
