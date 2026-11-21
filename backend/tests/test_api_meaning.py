import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402
from app.schemas import CriticalDetailsResponse, MeaningCheckResponse  # noqa: E402

client = TestClient(create_app())


def test_meaning_check_endpoint_changed():
    r = client.post("/api/meaning-check", json={
        "original": "Don't pay ₹500 before 5 pm.", "candidate": "Pay $500 before 5 pm.",
        "language": "en"})
    assert r.status_code == 200
    body = MeaningCheckResponse.model_validate(r.json())
    assert body.status == "changed" and body.missing_count == 2 and body.added_count == 1
    assert body.method == "rules_v5" and body.limitations


def test_meaning_check_endpoint_preserved():
    r = client.post("/api/meaning-check", json={
        "original": "Please do not share the code `X1`.", "candidate": "Please don't share the code `X1`."})
    assert r.status_code == 200 and r.json()["status"] == "preserved"
    # rules_v4: dropping the politeness marker makes the check ask for review (register), not 'changed'
    r2 = client.post("/api/meaning-check", json={
        "original": "Please do not share the code `X1`.", "candidate": "Don't share the code `X1`."})
    assert r2.json()["status"] == "at_risk" and any("Politeness" in x for x in r2.json()["risks"])


def test_critical_details_endpoint():
    text = "Call +91 98450 12345 or mail help@example.test on 12/01/2026."
    r = client.post("/api/critical-details", json={"text": text, "protected_terms": ["help"]})
    assert r.status_code == 200
    body = CriticalDetailsResponse.model_validate(r.json())
    assert all(body.text[d.start:d.end] == d.text for d in body.details)
    cats = [d.category for d in body.details]
    assert cats.count("number") == 3 and "email" in cats and "datetime" in cats
    assert "protected_term" in cats


@pytest.mark.parametrize("path,payload", [
    ("/api/meaning-check", {"original": "", "candidate": "x"}),
    ("/api/meaning-check", {"original": "x"}),
    ("/api/meaning-check", {"original": "x", "candidate": "x", "language": "fr"}),
    ("/api/critical-details", {"text": "   "}),
    ("/api/critical-details", {"text": "x", "protected_terms": ["ok", ""]}),
])
def test_validation_errors_use_standard_shape(path, payload):
    r = client.post(path, json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_request"


def test_openapi_documents_meaning_endpoints():
    spec = client.get("/openapi.json").json()
    assert "/api/meaning-check" in spec["paths"] and "/api/critical-details" in spec["paths"]
    assert "MeaningCheckResponse" in spec["components"]["schemas"]
