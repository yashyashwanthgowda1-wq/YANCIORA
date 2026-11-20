import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.schemas import OptimizeResponse  # noqa: E402
from app.tokenizers import register  # noqa: E402
from tests.conftest import FakeTokenizer  # noqa: E402

register("fake_bytes", FakeTokenizer)
client = TestClient(create_app())


def test_optimize_endpoint():
    r = client.post("/api/optimize", json={
        "text": "Please   send ₹500 today!!!", "language": "en", "tokenizers": ["fake_bytes"]})
    assert r.status_code == 200
    body = OptimizeResponse.model_validate(r.json())
    assert body.changed and body.optimized == "Please send ₹500 today!"
    assert body.method == "opt_rules_v1" and body.mode == "safe"
    assert body.token_counts[0].tokenizer.name == "fake_bytes"
    assert any("not provider billing" in w for w in body.warnings)
    assert body.limitations and body.meaning_check.status == "preserved"


def test_optimize_endpoint_suggestion_shape():
    r = client.post("/api/optimize", json={
        "text": "ದಯವಿಟ್ಟು ಕಳುಹಿಸಿ!!!", "language": "kn", "tokenizers": ["fake_bytes"]})
    body = r.json()
    assert r.status_code == 200 and body["requires_review"] is True and body["changed"] is False
    s = body["suggestions"][0]
    assert s["kind"] == "at_risk_edit" and s["requires_review"] is True and s["risks"]


@pytest.mark.parametrize("payload", [
    {"text": "   ", "tokenizers": ["fake_bytes"]},
    {"text": "x" * 20_001, "tokenizers": ["fake_bytes"]},
    {"text": "x", "tokenizers": []},
    {"text": "x", "tokenizers": ["fake_bytes", "fake_bytes"]},
    {"text": "x", "tokenizers": ["a", "b", "c", "d", "e"]},
    {"text": "x", "mode": "extreme", "tokenizers": ["fake_bytes"]},
    {"text": "x", "language": "ml", "tokenizers": ["fake_bytes"]},
    {"text": "x", "protected_terms": [""], "tokenizers": ["fake_bytes"]},
])
def test_validation_errors(payload):
    r = client.post("/api/optimize", json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_max_length_accepted():
    r = client.post("/api/optimize", json={"text": "a" * 20_000, "tokenizers": ["fake_bytes"]})
    assert r.status_code == 200 and r.json()["changed"] is False


def test_unknown_tokenizer():
    r = client.post("/api/optimize", json={"text": "hi  there", "tokenizers": ["nope"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_tokenizer"


def test_openapi_documents_optimizer():
    spec = client.get("/openapi.json").json()
    assert "/api/optimize" in spec["paths"]
    for name in ("OptimizeResponse", "AcceptedEdit", "RejectedEdit", "OptimizeSuggestion"):
        assert name in spec["components"]["schemas"]
