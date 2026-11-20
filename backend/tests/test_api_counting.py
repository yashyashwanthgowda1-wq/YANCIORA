import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.tokenizers import register  # noqa: E402
from tests.conftest import FakeTokenizer  # noqa: E402

register("fake_bytes", FakeTokenizer)
client = TestClient(create_app())


def test_tokenize_endpoint():
    r = client.post("/api/tokenize", json={"text": "ನಮಸ್ಕಾರ", "tokenizer": "fake_bytes"})
    assert r.status_code == 200
    body = r.json()
    assert body["tokenizer"]["name"] == "fake_bytes" and body["language"] == "kn"


def test_unknown_tokenizer_error_shape():
    r = client.post("/api/tokenize", json={"text": "hi", "tokenizer": "nope"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "unknown_tokenizer"


def test_validation_error_shape():
    r = client.post("/api/tokenize", json={"text": "", "tokenizer": "fake_bytes"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_compare_endpoint():
    r = client.post("/api/compare-languages", json={
        "tokenizer": "fake_bytes", "aligned_group_id": "g1",
        "variants": [
            {"language": "en", "script": "Latn", "variant_type": "original", "text": "hello there"},
            {"language": "hi", "script": "Deva", "variant_type": "translation", "text": "नमस्ते"},
        ],
    })
    assert r.status_code == 200
    assert r.json()["rows"][0]["ratio_vs_reference"] == 1.0


def test_list_tokenizers():
    assert "cl100k_base" in client.get("/api/tokenizers").json()["tokenizers"]
