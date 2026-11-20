import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.schemas import ScriptVariantsResponse  # noqa: E402
from app.tokenizers import register  # noqa: E402
from tests.conftest import FakeTokenizer  # noqa: E402

register("fake_bytes", FakeTokenizer)
client = TestClient(create_app())

try:
    import indic_transliteration  # noqa: F401
    HAVE_ENGINE = True
except ImportError:
    HAVE_ENGINE = False
needs_engine = pytest.mark.skipif(not HAVE_ENGINE, reason="indic-transliteration not installed")


@needs_engine
def test_script_variants_endpoint():
    r = client.post("/api/script-variants", json={
        "text": "ಕನ್ನಡ ಸರಿ", "language": "kn", "target_schemes": ["iso", "baraha"],
        "tokenizers": ["fake_bytes"]})
    assert r.status_code == 200
    body = ScriptVariantsResponse.model_validate(r.json())
    assert body.status == "ok" and [v.scheme for v in body.variants] == ["iso", "baraha"]
    assert all(v.requires_review for v in body.variants)
    assert body.variants[0].text == "kannaḍa sari"


def test_casual_is_unsupported_without_engine_work():
    r = client.post("/api/script-variants", json={
        "text": "naanu baruvudilla", "language": "kn", "direction": "roman_to_native",
        "source_scheme": "casual", "tokenizers": ["fake_bytes"]})
    assert r.status_code == 200 and r.json()["status"] == "unsupported"
    assert r.json()["variants"] == []


@pytest.mark.parametrize("payload", [
    {"text": "hi", "language": "en", "tokenizers": ["fake_bytes"]},
    {"text": "x", "language": "kn", "direction": "roman_to_native", "tokenizers": ["fake_bytes"]},
    {"text": "x", "language": "kn", "target_schemes": ["iast"], "tokenizers": ["fake_bytes"]},
    {"text": "x", "language": "kn", "target_schemes": [], "tokenizers": ["fake_bytes"]},
    {"text": "x" * 20_001, "language": "kn", "tokenizers": ["fake_bytes"]},
    {"text": "x", "language": "kn", "direction": "sideways", "tokenizers": ["fake_bytes"]},
])
def test_validation_errors(payload):
    r = client.post("/api/script-variants", json=payload)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_unknown_tokenizer():
    r = client.post("/api/script-variants", json={"text": "ಕನ್ನಡ", "language": "kn",
                                                  "tokenizers": ["nope"]})
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_tokenizer"


def test_engine_unavailable_returns_503(monkeypatch):
    from app.services import transliteration as TL

    def boom():
        raise TL.TransliterationUnavailable("indic-transliteration is not installed")

    monkeypatch.setattr(TL, "_engine", boom)
    r = client.post("/api/script-variants", json={"text": "ಕನ್ನಡ", "language": "kn",
                                                  "tokenizers": ["fake_bytes"]})
    assert r.status_code == 503 and r.json()["error"]["code"] == "transliteration_unavailable"


def test_openapi_documents_script_variants():
    spec = client.get("/openapi.json").json()
    assert "/api/script-variants" in spec["paths"]
    assert "ScriptVariantsResponse" in spec["components"]["schemas"]
