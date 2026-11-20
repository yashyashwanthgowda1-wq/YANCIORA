"""Application settings, read from environment variables only.

Secrets never live in code or the database (BRD §14, PRD §17). Values come from
the process environment; a local `.env` file is loaded if present.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

APP_NAME = "REDUTAX"
APP_VERSION = "0.1.0"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments. Existing env wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Settings(BaseModel):
    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    database_url: str | None = None

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        v = v.upper()
        if v not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log level: {v}")
        return v

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "Settings":
        e = os.environ if environ is None else environ
        data: dict[str, object] = {}
        if v := e.get("REDUTAX_ENV"):
            data["env"] = v
        if v := e.get("REDUTAX_LOG_LEVEL"):
            data["log_level"] = v
        if v := e.get("REDUTAX_CORS_ORIGINS"):
            data["cors_origins"] = [o.strip() for o in v.split(",") if o.strip()]
        if v := e.get("DATABASE_URL"):
            data["database_url"] = v
        return cls(**data)

    def safe_dict(self) -> dict[str, object]:
        """Settings with credentials masked — safe to log."""
        d = self.model_dump()
        if self.database_url:
            d["database_url"] = mask_url(self.database_url)
        return d


def mask_url(url: str) -> str:
    """Hide the password in a URL like scheme://user:pass@host/db."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


@lru_cache
def get_settings() -> Settings:
    _load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    return Settings.from_env()
