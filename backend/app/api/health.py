from fastapi import APIRouter, Depends, Response

from app.core.config import APP_NAME, APP_VERSION, Settings, get_settings
from app.db.session import check_database

router = APIRouter(tags=["system"])


@router.get("/health")
def health(response: Response, settings: Settings = Depends(get_settings)) -> dict:
    """Liveness plus dependency status.

    Returns 200 when the app is up. If a database is configured but unreachable,
    returns 503 so deploy checks fail loudly instead of silently.
    """
    db = check_database(settings.database_url)
    if db["status"] == "error":
        response.status_code = 503
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "env": settings.env,
        "status": "ok" if db["status"] != "error" else "degraded",
        "database": db,
    }
