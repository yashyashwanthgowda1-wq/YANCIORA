import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def test_health_ok_without_database():
    r = client_with(Settings(env="test")).get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "REDUTAX"
    assert body["status"] == "ok"
    assert body["database"] == {"status": "not_configured"}


def test_health_reports_unreachable_database_as_503():
    bad = Settings(env="test", database_url="postgresql+psycopg://u:p@127.0.0.1:1/none")
    r = client_with(bad).get("/health")
    assert r.status_code == 503
    assert r.json()["database"]["status"] == "error"
    assert "p@" not in r.text  # credentials never echoed


def test_request_id_is_echoed_or_generated():
    c = client_with(Settings(env="test"))
    assert c.get("/health", headers={"x-request-id": "abc123"}).headers["x-request-id"] == "abc123"
    assert len(c.get("/health").headers["x-request-id"]) == 32
