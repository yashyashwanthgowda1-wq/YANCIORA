import pytest
from pydantic import ValidationError

from app.core.config import Settings, mask_url, redact_url


def test_defaults_without_env():
    s = Settings.from_env({})
    assert s.env == "development"
    assert s.log_level == "INFO"
    assert s.database_url is None
    assert s.cors_origins == ["http://localhost:3000"]


def test_reads_env_values():
    s = Settings.from_env({
        "REDUTAX_ENV": "test",
        "REDUTAX_LOG_LEVEL": "debug",
        "REDUTAX_CORS_ORIGINS": "http://a.test, http://b.test",
        "DATABASE_URL": "postgresql+psycopg://u:p@h:5432/d",
    })
    assert s.env == "test"
    assert s.log_level == "DEBUG"
    assert s.cors_origins == ["http://a.test", "http://b.test"]
    assert s.database_url.endswith("/d")


def test_rejects_invalid_env_and_log_level():
    with pytest.raises(ValidationError):
        Settings.from_env({"REDUTAX_ENV": "staging"})
    with pytest.raises(ValidationError):
        Settings.from_env({"REDUTAX_LOG_LEVEL": "loud"})


def test_safe_dict_hides_password_user_and_host():
    """The startup log uses safe_dict(): no password, user, host, port or database name."""
    s = Settings.from_env({"DATABASE_URL": "postgresql+psycopg://dbuser:s3cret@ep-x.neon.tech:5432/maindb?sslmode=require"})
    dumped = str(s.safe_dict())
    for secret in ("s3cret", "dbuser", "ep-x", "neon.tech", "5432", "maindb", "sslmode"):
        assert secret not in dumped, secret
    assert s.safe_dict()["database_url"] == "configured (postgresql+psycopg)"


def test_redact_url():
    assert redact_url("postgresql://u:p@h/d") == "configured (postgresql)"
    assert redact_url("not a url") == "configured (unknown)"


def test_mask_url_leaves_urls_without_credentials():
    assert mask_url("sqlite:///local.db") == "sqlite:///local.db"
    assert mask_url("postgresql://u:p@a@host/db") == "postgresql://u:***@host/db"
