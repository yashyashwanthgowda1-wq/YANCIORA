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
    # ---- Phase 2 providers (all optional; features degrade to their documented fallbacks) ----
    # Model registry (verified model metadata and prices; ships empty).
    models_registry_path: str | None = None
    # Speech-to-text: an OpenAI-compatible POST {base}/audio/transcriptions endpoint.
    stt_base_url: str | None = None
    stt_api_key: str | None = None
    stt_model: str | None = None
    # Chat LLM: an OpenAI-compatible POST {base}/chat/completions endpoint.
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_provider_name: str | None = None
    llm_timeout_seconds: float = 30.0
    # Vapi webhook authentication (at least one must be set or the webhook refuses requests).
    vapi_webhook_secret: str | None = None      # Bearer token / X-Vapi-Secret value
    vapi_hmac_secret: str | None = None         # HMAC credential secret
    vapi_hmac_signature_header: str = "x-signature"
    vapi_hmac_timestamp_header: str = "x-timestamp"
    vapi_tool_timeout_seconds: float = 8.0

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
        for env_key, field in ENV_FIELDS.items():
            if v := e.get(env_key):
                data[field] = v
        return cls(**data)

    def safe_dict(self) -> dict[str, object]:
        """Settings with credentials masked — safe to log."""
        d = self.model_dump()
        if self.database_url:
            d["database_url"] = redact_url(self.database_url)
        for field in SECRET_FIELDS:
            d[field] = "configured" if d.get(field) else None
        for field in ("stt_base_url", "llm_base_url"):
            if d.get(field):
                d[field] = redact_url(d[field])
        return d


# Environment variable → Settings field for the Phase 2 providers.
ENV_FIELDS = {
    "REDUTAX_MODELS_REGISTRY": "models_registry_path",
    "STT_BASE_URL": "stt_base_url", "STT_API_KEY": "stt_api_key", "STT_MODEL": "stt_model",
    "LLM_BASE_URL": "llm_base_url", "LLM_API_KEY": "llm_api_key", "LLM_MODEL": "llm_model",
    "LLM_PROVIDER_NAME": "llm_provider_name", "LLM_TIMEOUT_SECONDS": "llm_timeout_seconds",
    "VAPI_WEBHOOK_SECRET": "vapi_webhook_secret", "VAPI_HMAC_SECRET": "vapi_hmac_secret",
    "VAPI_HMAC_SIGNATURE_HEADER": "vapi_hmac_signature_header",
    "VAPI_HMAC_TIMESTAMP_HEADER": "vapi_hmac_timestamp_header",
    "VAPI_TOOL_TIMEOUT_SECONDS": "vapi_tool_timeout_seconds",
}
SECRET_FIELDS = ("stt_api_key", "llm_api_key", "vapi_webhook_secret", "vapi_hmac_secret")


def redact_url(url: str) -> str:
    """For logs: only whether a database is configured and which driver/scheme. No username,
    password, host, port, database name or query parameters."""
    scheme = url.split("://", 1)[0] if "://" in url else "unknown"
    return f"configured ({scheme})"


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
