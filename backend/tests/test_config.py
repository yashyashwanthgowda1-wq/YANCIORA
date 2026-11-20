import pytest
from pydantic import ValidationError

from app.core.config import Settings, mask_url


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


def test_password_masked_in_safe_dict():
    s = Settings.from_env({"DATABASE_URL": "postgresql://user:s3cret@db:5432/x"})
    dumped = str(s.safe_dict())
    assert "s3cret" not in dumped
    assert "user:***@db:5432/x" in dumped


def test_mask_url_leaves_urls_without_credentials():
    assert mask_url("sqlite:///local.db") == "sqlite:///local.db"
    assert mask_url("postgresql://u:p@a@host/db") == "postgresql://u:***@host/db"
