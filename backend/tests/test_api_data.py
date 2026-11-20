"""GET /api/samples/groups and GET /api/benchmarks: validation, errors, schemas."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.schemas import BenchmarksResponse, SampleGroupsResponse  # noqa: E402
from tests import sample_data as D  # noqa: E402
from tests.conftest import FakeTokenizer  # noqa: E402
from tests.pg import pg_engine, pg_url, truncate_all  # noqa: E402,F401

ENDPOINTS = ["/api/samples/groups", "/api/benchmarks", "/api/benchmarks/RUN1/results"]


def client_with(settings: Settings) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


# ---------- no database needed ----------
@pytest.mark.parametrize("path", ENDPOINTS)
def test_database_not_configured_is_503(path):
    r = client_with(Settings(env="test")).get(path)
    assert r.status_code == 503
    assert r.json() == {"error": {"code": "database_not_configured",
                                  "message": "The database is not configured on this server."}}


@pytest.mark.parametrize("path", ENDPOINTS)
def test_unreachable_database_hides_details(path):
    c = client_with(Settings(env="test", database_url="postgresql+psycopg://u:s3cret@127.0.0.1:1/x"))
    r = c.get(path)
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
    assert "s3cret" not in r.text and "127.0.0.1" not in r.text


@pytest.mark.parametrize("query", [
    "page=0", "page_size=0", "page_size=101", "page=abc", "language=ml", "split=holdout",
    "dataset=",
])
def test_invalid_group_filters(query):
    c = client_with(Settings(env="test", database_url="postgresql+psycopg://u:p@127.0.0.1:1/x"))
    r = c.get(f"/api/samples/groups?{query}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


@pytest.mark.parametrize("path", [
    "/api/benchmarks?page=0", "/api/benchmarks?page_size=500", "/api/benchmarks?language=xx",
    "/api/benchmarks/RUN1/results?script=Arab", "/api/benchmarks/bad%20id!/results",
])
def test_invalid_benchmark_filters(path):
    c = client_with(Settings(env="test", database_url="postgresql+psycopg://u:p@127.0.0.1:1/x"))
    r = c.get(path)
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


# ---------- PostgreSQL ----------
@pytest.fixture
def client(pg_engine, tmp_path):  # noqa: F811
    from app.services.benchmark_store import store_run
    from app.services.dataset_store import load_samples
    from tests.test_benchmark_store import make_run

    truncate_all(pg_engine)
    load_samples(pg_engine, D.register(), "TESTSET", D.rows())
    toks = [FakeTokenizer()]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks, run_id="RUN1")
    store_run(pg_engine, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: pg_engine
    return TestClient(app)


def test_groups_endpoint(client):
    r = client.get("/api/samples/groups", params={"dataset": "TESTSET", "language": ["en", "kn"]})
    assert r.status_code == 200
    body = SampleGroupsResponse.model_validate(r.json())
    assert body.total == 1 and body.page == 1 and body.page_size == 20
    g = body.items[0]
    assert g.aligned_group_id == "g1" and g.split == "test" and g.languages == ["en", "hi", "kn"]
    assert g.dataset.name == "TESTSET" and g.dataset.license == D.LICENSE
    kn = next(s for s in g.samples if s.language == "kn")
    assert kn.script == "Knda" and kn.text == "ಶುಭೋದಯ ಗೆಳೆಯ" and kn.license == D.LICENSE


def test_groups_pagination_and_split(client):
    body = client.get("/api/samples/groups?page_size=2&page=2").json()
    assert body["total"] == 3 and [g["aligned_group_id"] for g in body["items"]] == ["g3"]
    body = client.get("/api/samples/groups?split=train").json()
    assert body["total"] == 1 and body["items"][0]["split"] == "train"


def test_groups_unknown_dataset_404(client):
    r = client.get("/api/samples/groups?dataset=NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_group_can_feed_compare(client):
    """A returned group is directly usable as POST /api/compare-languages variants."""
    from app.tokenizers import register

    register("fake_bytes", FakeTokenizer)
    g = client.get("/api/samples/groups?aligned_group_id=g1").json()["items"][0]
    variants = [{k: s[k] for k in ("language", "script", "variant_type", "text")} for s in g["samples"]]
    r = client.post("/api/compare-languages", json={
        "tokenizer": "fake_bytes", "aligned_group_id": g["aligned_group_id"], "variants": variants})
    assert r.status_code == 200 and r.json()["aligned"] is True


def test_benchmarks_endpoint(client):
    r = client.get("/api/benchmarks", params={"dataset": "TESTSET", "tokenizer": "fake_bytes"})
    assert r.status_code == 200
    body = BenchmarksResponse.model_validate(r.json())
    run = body.items[0]
    assert body.total == 1 and run.run_id == "RUN1" and run.split == "test"
    assert run.dataset.version == "1" and run.tokenizers[0].name == "fake_bytes"
    assert run.normalization == "nfc_ws_v1" and "not cost multipliers" in run.note
    en = next(s for s in run.summaries if s.language == "en")
    assert en.status == "exact" and en.ratio_vs_reference == pytest.approx(1.0)


def test_benchmarks_filters(client):
    assert client.get("/api/benchmarks?tokenizer=cl100k_base").json()["total"] == 0
    body = client.get("/api/benchmarks?run_id=RUN1&language=hi").json()
    assert [s["language"] for s in body["items"][0]["summaries"]] == ["hi"]
    r = client.get("/api/benchmarks?run_id=NOPE")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_benchmark_results_endpoint(client):
    r = client.get("/api/benchmarks/RUN1/results?language=kn")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1 and body["items"][0]["sample_id"] == "g1-kn"
    assert body["items"][0]["tokenizer"]["version"] == "0" and body["items"][0]["status"] == "exact"
    assert client.get("/api/benchmarks/NOPE/results").status_code == 404
