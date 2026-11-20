"""Benchmark persistence and retrieval (PostgreSQL)."""
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import text  # noqa: E402

from app.services.benchmark import count_rows, run_metadata, summarize_rows  # noqa: E402
from app.services.benchmark_store import (  # noqa: E402
    BenchmarkStoreError, list_results, list_runs, store_run,
)
from app.services.dataset_store import NotFound, load_samples  # noqa: E402
from tests import sample_data as D  # noqa: E402
from app.tokenizers.base import TokenizerInfo  # noqa: E402
from tests.conftest import FakeTokenizer  # noqa: E402
from tests.pg import pg_engine, pg_url, truncate_all  # noqa: E402,F401


class FakeExperimental(FakeTokenizer):
    @property
    def info(self) -> TokenizerInfo:
        return TokenizerInfo("fake_research", "test", "0", "experimental")


def make_run(tmp_path: Path, samples, toks, run_id="RUN1", split="test"):
    f = tmp_path / f"{run_id}.jsonl"
    f.write_text("x", encoding="utf-8")
    samples = [s for s in samples if s["split"] == split]
    meta = run_metadata(input_file=f, samples=samples, tokenizers=toks, split=split,
                        reference_language="en", repo=tmp_path)
    meta["run_id"] = run_id
    rows = count_rows(samples, toks)
    return meta, samples, rows, summarize_rows(rows, "en")


@pytest.fixture
def eng(pg_engine):  # noqa: F811
    truncate_all(pg_engine)
    load_samples(pg_engine, D.register(), "TESTSET", D.rows())
    return pg_engine


def count(eng, table):
    with eng.connect() as c:
        return c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_store_run_persists_everything(eng, tmp_path):
    toks = [FakeTokenizer(), FakeExperimental()]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks)
    res = store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)
    assert res["rows"] == 10 and res["summaries"] == len(summary)  # 5 test samples x 2 toks
    with eng.connect() as c:
        r = c.execute(text("""
            SELECT b.*, s.sample_id AS sid, s.aligned_group_id, s.language_code, s.script,
                   t.name, t.library, t.library_version, d.name AS dname, d.version AS dver,
                   br.split, br.config->>'normalization' AS cfg_norm
            FROM token_benchmarks b JOIN dataset_samples s ON s.id = b.sample_id
            JOIN tokenizers t ON t.id = b.tokenizer_id JOIN benchmark_runs br ON br.run_id = b.run_id
            JOIN datasets d ON d.id = br.dataset_id
            WHERE s.sample_id = 'g1-kn' AND t.name = 'fake_bytes'""")).mappings().one()
        status = dict(c.execute(text("""SELECT t.name, b.count_status FROM token_benchmarks b
            JOIN tokenizers t ON t.id = b.tokenizer_id GROUP BY 1, 2""")).all())
    expected = next(x for x in rows if x.sample_id == "g1-kn" and x.tokenizer == "fake_bytes")
    assert (r["token_count"], r["word_count"], r["char_count"]) == (
        expected.token_count, expected.word_count, expected.char_count)
    assert r["fertility"] == pytest.approx(expected.fertility)
    assert (r["aligned_group_id"], r["language_code"], r["script"]) == ("g1", "kn", "Knda")
    assert (r["name"], r["library"], r["library_version"]) == ("fake_bytes", "test", "0")
    assert (r["dname"], r["dver"], r["split"], r["run_id"]) == ("TESTSET", "1", "test", "RUN1")
    assert r["normalization"] == "nfc_ws_v1" and r["word_count_method"] == "unicode_whitespace_v1"
    assert r["cfg_norm"] == "nfc_ws_v1"
    assert status == {"fake_bytes": "exact", "fake_research": "research"}


def test_duplicate_run_refused(eng, tmp_path):
    toks = [FakeTokenizer()]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks)
    store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)
    with pytest.raises(BenchmarkStoreError, match="already stored"):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)


def test_dataset_not_loaded(eng, tmp_path):
    toks = [FakeTokenizer()]
    meta, samples, rows, summary = make_run(
        tmp_path, D.processed(D.rows(), name="TESTSET", version="9"), toks)
    with pytest.raises(BenchmarkStoreError, match="not in the database"):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)


def test_changed_or_missing_samples_refused(eng, tmp_path):
    toks = [FakeTokenizer()]
    changed = D.rows()
    changed[1]["text"] = "ಬೇರೆ ಪಠ್ಯ"
    meta, samples, rows, summary = make_run(tmp_path, D.processed(changed), toks)
    with pytest.raises(BenchmarkStoreError, match="differ from the stored copy"):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)

    extra = D.rows() + [D.row("new-en", "en", "Latn", "Not loaded yet", "g8", vt="original")]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(extra), toks, run_id="RUN2")
    with pytest.raises(BenchmarkStoreError, match="not stored"):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)


def test_mixed_datasets_refused(eng, tmp_path):
    toks = [FakeTokenizer()]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks)
    samples[0] = dict(samples[0], dataset="OTHER")
    with pytest.raises(BenchmarkStoreError, match="exactly one dataset"):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)


def test_failure_rolls_back_whole_run(eng, tmp_path):
    toks = [FakeTokenizer()]
    meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks)
    summary[-1]["n_samples"] = -1  # violates CHECK after run + rows were inserted
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)
    assert count(eng, "benchmark_runs") == 0 and count(eng, "token_benchmarks") == 0


def test_list_runs_filters_and_pagination(eng, tmp_path):
    t1, t2 = FakeTokenizer(), FakeExperimental()
    for rid, toks in (("RUN_A", [t1]), ("RUN_B", [t1, t2])):
        meta, samples, rows, summary = make_run(tmp_path, D.processed(D.rows()), toks, run_id=rid)
        store_run(eng, meta=meta, samples=samples, rows=rows, summary=summary, tokenizers=toks)

    runs, total = list_runs(eng)
    assert total == 2
    # Regression: the run's dataset licence comes from the datasets row.
    assert all(r["dataset_license"] == D.LICENSE for r in runs)
    runs, total = list_runs(eng, tokenizer="fake_research")
    assert total == 1 and runs[0]["run_id"] == "RUN_B"
    assert {s["tokenizer"]["name"] for s in runs[0]["summaries"]} == {"fake_research"}
    runs, _ = list_runs(eng, run_id="RUN_A", language="kn")
    assert [s["language"] for s in runs[0]["summaries"]] == ["kn"]
    assert runs[0]["summaries"][0]["ratio_vs_reference"] is not None
    page, total = list_runs(eng, page=2, page_size=1)
    assert total == 2 and len(page) == 1
    assert list_runs(eng, dataset="TESTSET", dataset_version="1")[1] == 2
    with pytest.raises(NotFound):
        list_runs(eng, run_id="NOPE")
    with pytest.raises(NotFound):
        list_runs(eng, dataset="NOPE")

    res, total = list_results(eng, "RUN_B", tokenizer="fake_bytes")
    assert total == 5 and all(r["tokenizer"]["name"] == "fake_bytes" for r in res)
    res, total = list_results(eng, "RUN_B", language="hi", page_size=1, page=2)
    assert total == 4 and len(res) == 1  # 2 hi samples x 2 tokenizers
    with pytest.raises(NotFound):
        list_results(eng, "NOPE")
