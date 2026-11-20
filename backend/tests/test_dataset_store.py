"""Dataset persistence: licence gate, idempotency, duplicates, leakage, rollback."""
import pytest

pytest.importorskip("sqlalchemy")

from sqlalchemy import text  # noqa: E402

from app.services.dataset_import import RegisterError  # noqa: E402
from app.services.dataset_store import (  # noqa: E402
    DatasetImportError, NotFound, list_groups, load_samples,
)
from tests import sample_data as D  # noqa: E402
from tests.pg import pg_engine, pg_url, truncate_all  # noqa: E402,F401


class NoDB:
    """Engine stand-in that fails if touched: proves checks run before any DB access."""

    def begin(self):
        raise AssertionError("database must not be touched")

    connect = begin


# ---------- no database needed ----------
@pytest.mark.parametrize("over,msg", [
    ({"license": "TO_VERIFY"}, "license not verified"),
    ({"version": "TO_VERIFY"}, "version not verified"),
    ({"accessed_at": None}, "accessed_at missing"),
    ({"approved_for": []}, "not approved for 'evaluation'"),
])
def test_unverified_licence_blocks_before_db(over, msg):
    with pytest.raises(RegisterError, match=msg):
        load_samples(NoDB(), D.register(**over), "TESTSET", D.rows())


def test_unknown_dataset_blocked():
    with pytest.raises(RegisterError, match="not in the licence register"):
        load_samples(NoDB(), D.register(), "OTHER", D.rows())


def test_shipped_register_blocks_db_load():
    from pathlib import Path

    from app.services.dataset_import import load_register

    reg = load_register(Path(__file__).resolve().parents[2] / "research/configs/datasets.yaml")
    with pytest.raises(RegisterError):
        load_samples(NoDB(), reg, "REDUTAX-team-pilot", D.rows())
    # FLORES-200 is approved for evaluation only (team decision 2026-11-21).
    with pytest.raises(RegisterError, match="tokenizer_training"):
        load_samples(NoDB(), reg, "FLORES-200", D.rows(), use="tokenizer_training")


def test_validation_errors_block_before_db():
    bad = D.rows() + [D.row("g1-ta", "ta", "Taml", "x", "g1", split="train")]  # group leak
    with pytest.raises(DatasetImportError) as e:
        load_samples(NoDB(), D.register(), "TESTSET", bad)
    assert any("aligned group g1 spans" in m for m in e.value.errors)


def test_row_licence_mismatch_blocked():
    rs = D.rows()
    rs[0]["license"] = "SOMETHING-ELSE"
    with pytest.raises(DatasetImportError) as e:
        load_samples(NoDB(), D.register(), "TESTSET", rs)
    assert any("differs from the register licence" in m for m in e.value.errors)


def test_language_outside_register_blocked():
    with pytest.raises(DatasetImportError) as e:
        load_samples(NoDB(), D.register(languages=["en", "kn"]), "TESTSET", D.rows())
    assert any("language hi is not listed" in m for m in e.value.errors)


# ---------- PostgreSQL ----------
@pytest.fixture
def eng(pg_engine):  # noqa: F811
    truncate_all(pg_engine)
    return pg_engine


def count(eng, table):
    with eng.connect() as c:
        return c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()


def test_load_persists_all_fields(eng):
    res = load_samples(eng, D.register(), "TESTSET", D.rows(), input_sha256="abc")
    assert (res.rows_inserted, res.rows_unchanged) == (7, 0)
    with eng.connect() as c:
        r = c.execute(text("""
            SELECT s.*, d.name, d.version, d.license AS dlicense, d.accessed_at::text AS acc
            FROM dataset_samples s JOIN datasets d ON d.id = s.dataset_id
            WHERE sample_id = 'g1-kn'""")).mappings().one()
        imp = c.execute(text("SELECT * FROM dataset_imports")).mappings().one()
    assert (r["name"], r["version"], r["dlicense"], r["acc"]) == ("TESTSET", "1", D.LICENSE, "2026-11-20")
    assert (r["aligned_group_id"], r["language_code"], r["script"]) == ("g1", "kn", "Knda")
    assert (r["text"], r["variant_type"], r["domain"], r["split"]) == ("ಶುಭೋದಯ ಗೆಳೆಯ", "translation", "general", "test")
    assert (r["source_name"], r["license"], r["normalization"]) == ("unit-test", D.LICENSE, "nfc_ws_v1")
    assert len(r["content_sha256"]) == 64
    assert (imp["rows_inserted"], imp["input_sha256"]) == (7, "abc")


def test_reimport_is_idempotent(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    res = load_samples(eng, D.register(), "TESTSET", D.rows())
    assert (res.rows_inserted, res.rows_unchanged) == (0, 7)
    assert count(eng, "dataset_samples") == 7 and count(eng, "datasets") == 1


def test_processed_file_reimport_is_idempotent(eng):
    """Loading the raw file then the processed samples.jsonl gives the same rows."""
    load_samples(eng, D.register(), "TESTSET", D.rows())
    res = load_samples(eng, D.register(), "TESTSET", D.processed(D.rows()))
    assert (res.rows_inserted, res.rows_unchanged) == (0, 7)


def test_append_new_rows(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows()[:3])
    res = load_samples(eng, D.register(), "TESTSET", D.rows())
    assert (res.rows_inserted, res.rows_unchanged) == (4, 3)


def test_changed_content_refused_and_nothing_written(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    changed = D.rows() + [D.row("g4-en", "en", "Latn", "A brand new row", "g4", vt="original")]
    changed[1]["text"] = "ಬೇರೆ ಪಠ್ಯ"
    with pytest.raises(DatasetImportError) as e:
        load_samples(eng, D.register(), "TESTSET", changed)
    assert any("g1-kn: already imported with different content" in m for m in e.value.errors)
    assert count(eng, "dataset_samples") == 7  # g4-en was rolled back too
    assert count(eng, "dataset_imports") == 1


def test_group_leakage_against_stored_rows(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    leak = [D.row("g1-ta", "ta", "Taml", "காலை வணக்கம் நண்பா", "g1", split="train")]
    with pytest.raises(DatasetImportError) as e:
        load_samples(eng, D.register(), "TESTSET", leak)
    assert any("aligned group g1 is stored in 'test'" in m for m in e.value.errors)


def test_text_leakage_against_stored_rows(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    leak = [D.row("x-en", "en", "Latn", "Good  morning friend", "g9", split="train", vt="original")]
    with pytest.raises(DatasetImportError, match="conflict"):
        load_samples(eng, D.register(), "TESTSET", leak)


def test_duplicate_text_same_split_skipped(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    dup = [D.row("dup-en", "en", "Latn", "Good morning friend", "g9", vt="original")]
    res = load_samples(eng, D.register(), "TESTSET", dup)
    assert (res.rows_inserted, res.rows_skipped) == (0, 1)
    assert any("duplicate text" in w for w in res.warnings)


def test_db_trigger_blocks_group_leakage(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError, match="split leakage"):
        with eng.begin() as c:
            c.execute(text("""INSERT INTO dataset_samples (sample_id, dataset_id, language_code,
                script, text, aligned_group_id, variant_type, split)
                SELECT 'raw', id, 'te', 'Telu', 't', 'g1', 'translation', 'train' FROM datasets"""))


def test_register_change_requires_new_version(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    with pytest.raises(DatasetImportError, match="changed since it was first imported"):
        load_samples(eng, D.register(license="OTHER-LICENCE"), "TESTSET",
                     [dict(r, license=None) for r in D.rows()])
    # A new version is a separate dataset row and may reuse sample IDs.
    res = load_samples(eng, D.register(version="2"), "TESTSET", D.rows())
    assert res.rows_inserted == 7 and count(eng, "datasets") == 2


def test_failure_mid_transaction_rolls_back(eng, monkeypatch):
    """Samples are inserted, then the import-log insert fails: everything is rolled back."""
    from sqlalchemy.exc import IntegrityError

    import app.core.text as T

    monkeypatch.setattr(T, "NORMALIZATION_ID", None)  # dataset_imports.normalization is NOT NULL
    with pytest.raises(IntegrityError):
        load_samples(eng, D.register(), "TESTSET", D.rows())
    assert count(eng, "dataset_samples") == 0 and count(eng, "datasets") == 0


def test_list_groups_filters_and_pagination(eng):
    load_samples(eng, D.register(), "TESTSET", D.rows())
    groups, total = list_groups(eng)
    assert total == 3 and [g["aligned_group_id"] for g in groups] == ["g1", "g2", "g3"]
    assert [m["language_code"] for m in groups[0]["samples"]] == ["en", "hi", "kn"]

    groups, total = list_groups(eng, languages=["kn"])
    assert total == 1 and groups[0]["aligned_group_id"] == "g1"
    groups, total = list_groups(eng, languages=["en", "hi"])
    assert total == 2
    assert list_groups(eng, split="train")[1] == 1
    page2, total = list_groups(eng, page=2, page_size=2)
    assert total == 3 and [g["aligned_group_id"] for g in page2] == ["g3"]
    assert list_groups(eng, page=5, page_size=2) == ([], 3)
    with pytest.raises(NotFound):
        list_groups(eng, dataset="NOPE")
