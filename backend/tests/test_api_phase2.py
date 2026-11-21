"""HTTP contract tests for the Phase 2 routes (error shape, status codes, no secret leakage)."""
import json

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import models  # noqa: E402

USER_MODEL = {"id": "test-user-model", "provider": "TestProvider", "encoding": "o200k_base",
              "pricing": {"currency": "USD", "input_per_1m": 1.0, "output_per_1m": 2.0}, "languages": {"kn": "claimed"}}


@pytest.fixture
def c(tmp_path, monkeypatch):
    p = tmp_path / "models.yaml"
    p.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(models, "registry_path", lambda: p)
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(llm_api_key="sk-secret-llm", vapi_webhook_secret="vs-secret")
    return TestClient(app)


def test_models_registry_endpoint(c):
    body = c.get("/api/models").json()
    assert body["count"] == 0 and body["models"] == [] and "empty" in body["warnings"][-1]


def test_cost_and_recommend_endpoints(c):
    r = c.post("/api/cost/estimate", json={"text": "ನಮಸ್ಕಾರ", "custom_models": [USER_MODEL], "expected_output_tokens": 10})
    assert r.status_code == 200 and r.json()["models"][0]["price_status"] == "user_entered"
    r = c.post("/api/models/recommend", json={"text": "ನಮಸ್ಕಾರ", "language": "kn", "custom_models": [USER_MODEL]})
    assert r.status_code == 200 and r.json()["recommended"]["model_id"] == "test-user-model"


@pytest.mark.parametrize("path,payload", [
    ("/api/cost/estimate", {"text": " "}),
    ("/api/cost/estimate", {"text": "x", "expected_output_tokens": -1}),
    ("/api/cost/estimate", {"text": "x", "custom_models": [{"id": "a", "provider": "p", "pricing": {"currency": "USD", "input_per_1m": -1, "output_per_1m": 0}}]}),
    ("/api/models/recommend", {"text": "x", "language": "fr"}),
    ("/api/models/recommend", {"text": "x", "language": "kn", "cost_preference": "free"}),
    ("/api/pipeline/analyze", {"text": "x" * 20_001}),
    ("/api/pipeline/apply", {"original": "abc", "edits": [{"start": -1, "end": 1, "after": ""}]}),
    ("/api/voice/transcribe", {"audio_base64": "short"}),
    ("/api/chat", {"text": ""}),
])
def test_validation_errors(c, path, payload):
    r = c.post(path, json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_pipeline_endpoints(c):
    a = c.post("/api/pipeline/analyze", json={"text": "Please   send it!!!", "language": "en"}).json()
    assert a["method"] == "pipeline_v1" and a["optimization"]["changed"]
    r = c.post("/api/pipeline/apply", json={"original": "abcdef", "edits": [{"start": 0, "end": 3, "after": ""},
                                                                             {"start": 2, "end": 4, "after": ""}]})
    assert r.status_code == 422 and "overlap" in r.json()["error"]["message"]
    assert c.post("/api/pipeline/analyze", json={"text": "hi", "tokenizer": "nope"}).status_code == 400


def test_provider_not_configured_responses(c):
    r = c.post("/api/voice/transcribe", json={"audio_base64": "AAECAwQFBgc="})
    assert r.status_code == 503 and r.json()["error"]["code"] == "stt_not_configured"
    s = c.post("/api/chat", json={"text": "hello", "language": "en"}).json()
    assert s["mode"] == "analysis" and s["llm_available"] is False
    r = c.post(f"/api/chat/{s['session_id']}/send", json={"text": "hello"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_not_configured"


def test_provider_rate_limit_and_failure_responses(c, monkeypatch):
    from app.integrations import providers

    s = c.post("/api/chat", json={"text": "hello", "language": "en"}).json()

    def limited(*a, **k):
        raise providers.ProviderRateLimited("LLM provider rate limit reached. Retry after 5 s.", 5)
    monkeypatch.setattr(providers, "chat_complete", limited)
    r = c.post(f"/api/chat/{s['session_id']}/send", json={"text": "hello"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "provider_rate_limited"

    def broken(*a, **k):
        raise providers.ProviderError("LLM provider timed out.")
    monkeypatch.setattr(providers, "chat_complete", broken)
    monkeypatch.setattr(providers, "transcribe", lambda *a, **k: (_ for _ in ()).throw(providers.ProviderRateLimited("x")))
    r = c.post(f"/api/chat/{s['session_id']}/send", json={"text": "hello"})
    assert r.status_code == 502 and r.json()["error"]["code"] == "provider_error"
    r = c.post("/api/voice/transcribe", json={"audio_base64": "AAECAwQFBgc="})
    assert r.status_code == 429 and r.json()["error"]["code"] == "provider_rate_limited"
    assert "sk-secret-llm" not in r.text


def test_chat_history_and_delete(c):
    s = c.post("/api/chat", json={"text": "hello", "language": "en"}).json()
    assert len(c.get(f"/api/chat/{s['session_id']}").json()["history"]) == 2
    assert c.delete(f"/api/chat/{s['session_id']}").status_code == 204
    r = c.get(f"/api/chat/{s['session_id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_integrations_status_has_no_secrets(c):
    r = c.get("/api/integrations/status")
    body = r.json()
    assert r.status_code == 200 and body["vapi_webhook"]["configured"] is True
    assert body["llm"]["configured"] is False             # key alone is not a full configuration
    text = json.dumps(body)
    assert "sk-secret-llm" not in text and "vs-secret" not in text


def test_openapi_lists_phase2_routes(c):
    paths = c.get("/openapi.json").json()["paths"]
    for p in ("/api/models", "/api/cost/estimate", "/api/models/recommend", "/api/pipeline/analyze",
              "/api/pipeline/apply", "/api/voice/transcribe", "/api/chat", "/api/chat/{session_id}/send",
              "/api/integrations/status", "/api/vapi/status", "/api/vapi/webhook"):
        assert p in paths, p
