"""Dataset validation and benchmark logic. All texts are unit-test fixtures, not dataset samples."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app.services.benchmark import count_rows, summarize_rows
from app.services.dataset_import import (
    RegisterError, check_register_entry, flores_rows, validate,
)

REPO = Path(__file__).resolve().parents[2]


def row(sid, lang, script, text, group="g1", split="test", vt="translation"):
    return {"sample_id": sid, "language_code": lang, "script": script, "text": text,
            "aligned_group_id": group, "variant_type": vt, "source_name": "unit-test", "split": split}


GOOD = [
    row("g1-en", "en", "Latn", "Good morning friend", vt="original"),
    row("g1-kn", "kn", "Knda", "ಶುಭೋದಯ ಗೆಳೆಯ"),
    row("g2-en", "en", "Latn", "Where is the bus stop", group="g2", vt="original"),
    row("g2-hi", "hi", "Deva", "बस स्टॉप कहाँ है", group="g2"),
]


# ---------- register ----------
def entry(**over):
    e = {"name": "D", "version": "1", "license": "CC-BY-4.0", "source_url": "http://x",
         "citation": "c", "accessed_at": "2026-11-20", "approved_for": ["evaluation"]}
    e.update(over)
    return e


def test_register_accepts_complete_entry():
    assert check_register_entry([entry()], "D", "evaluation")["name"] == "D"


@pytest.mark.parametrize("over,msg", [
    ({"license": "TO_VERIFY"}, "license not verified"),
    ({"accessed_at": None}, "accessed_at missing"),
    ({"approved_for": []}, "not approved"),
])
def test_register_blocks_incomplete(over, msg):
    with pytest.raises(RegisterError, match=msg):
        check_register_entry([entry(**over)], "D", "evaluation")


def test_register_blocks_unknown_and_wrong_use():
    with pytest.raises(RegisterError, match="not in the licence register"):
        check_register_entry([], "D", "evaluation")
    with pytest.raises(RegisterError, match="tokenizer_training"):
        check_register_entry([entry()], "D", "tokenizer_training")


def test_shipped_register_blocks_until_verified():
    reg = yaml.safe_load((REPO / "research/configs/datasets.yaml").read_text())["datasets"]
    for name in ("FLORES-200", "REDUTAX-team-pilot"):
        with pytest.raises(RegisterError):
            check_register_entry(reg, name, "evaluation")


# ---------- validation ----------
def test_validate_good_rows():
    out, rep = validate(GOOD, "D", "1")
    assert rep.ok and rep.rows_valid == 4
    assert out[0]["text_normalized"] == "Good morning friend"
    assert rep.counts["kn/Knda/test"] == 1


def test_validate_schema_errors():
    bad = [dict(GOOD[0], split="holdout"), dict(GOOD[1], language_code="ml")]
    _, rep = validate(bad, "D", "1")
    assert not rep.ok and len(rep.errors) == 2


def test_validate_duplicate_ids_and_texts():
    rows = GOOD + [dict(GOOD[1], sample_id="g1-kn")]
    _, rep = validate(rows, "D", "1")
    assert any("duplicate sample_id" in e for e in rep.errors)

    same_split = GOOD + [dict(GOOD[1], sample_id="copy", aligned_group_id="g9")]
    out, rep2 = validate(same_split, "D", "1")
    assert rep2.ok and len(out) == 4 and any("dropped: copy" in w for w in rep2.warnings)


def test_validate_split_leakage():
    leak_text = GOOD + [dict(GOOD[1], sample_id="x", aligned_group_id="g9", split="train")]
    _, rep = validate(leak_text, "D", "1")
    assert any("identical text" in e for e in rep.errors)

    leak_group = [dict(GOOD[0]), dict(GOOD[1], split="train")]
    _, rep2 = validate(leak_group, "D", "1")
    assert any("aligned group g1 spans" in e for e in rep2.errors)


def test_validate_script_mismatch_warns():
    _, rep = validate([dict(GOOD[1], script="Latn")], "D", "1")
    assert rep.ok and any("detected Knda" in w for w in rep.warnings)


# ---------- FLORES conversion ----------
def test_flores_rows(tmp_path):
    d = tmp_path / "devtest"
    d.mkdir()
    (d / "eng_Latn.devtest").write_text("one\ntwo\n", encoding="utf-8")
    (d / "kan_Knda.devtest").write_text("ಒಂದು\nಎರಡು\n", encoding="utf-8")
    rows = flores_rows(tmp_path, "devtest", {"en": "eng_Latn", "kn": "kan_Knda"}, "u", "L")
    assert len(rows) == 4
    kn2 = next(r for r in rows if r["sample_id"] == "flores-devtest-0002-kn")
    assert kn2["aligned_group_id"] == "flores-devtest-0002" and kn2["split"] == "test"
    assert kn2["script"] == "Knda" and kn2["variant_type"] == "translation"
    (d / "kan_Knda.devtest").write_text("ಒಂದು\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not line-aligned"):
        flores_rows(tmp_path, "devtest", {"en": "eng_Latn", "kn": "kan_Knda"}, "u", "L")


# ---------- benchmark ----------
def test_benchmark_summary(fake_tok):
    samples, _ = validate(GOOD, "D", "1")
    rows = count_rows(samples, [fake_tok])
    assert len(rows) == 4 and all(r.tokenizer == "fake_bytes" for r in rows)
    summary = {(s["language_code"], s["script"]): s for s in summarize_rows(rows)}
    assert summary[("en", "Latn")]["ratio_vs_reference"] == pytest.approx(1.0)
    kn = summary[("kn", "Knda")]
    en_g1 = next(r for r in rows if r.sample_id == "g1-en")
    kn_g1 = next(r for r in rows if r.sample_id == "g1-kn")
    expected = (kn_g1.token_count / kn_g1.word_count) / (en_g1.token_count / en_g1.word_count)
    assert kn["ratio_vs_reference"] == pytest.approx(expected)  # paired only with g1, not g2
    assert kn["paired_groups_with_reference"] == 1


def test_benchmark_no_reference_gives_none(fake_tok):
    samples, _ = validate([GOOD[1]], "D", "1")
    s = summarize_rows(count_rows(samples, [fake_tok]))
    assert s[0]["ratio_vs_reference"] is None


# ---------- CLI ----------
def test_import_cli_blocks_unverified_dataset(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in GOOD), encoding="utf-8")
    r = subprocess.run([sys.executable, str(REPO / "research/scripts/import_pilot.py"),
                        "--input", str(src), "--dataset", "FLORES-200",
                        "--out-root", str(tmp_path / "out")], capture_output=True, text=True)
    assert r.returncode == 2 and "BLOCKED" in r.stderr


def test_import_cli_writes_outputs(tmp_path):
    src = tmp_path / "in.jsonl"
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in GOOD), encoding="utf-8")
    reg = tmp_path / "reg.yaml"
    reg.write_text(yaml.safe_dump({"datasets": [entry()]}), encoding="utf-8")
    r = subprocess.run([sys.executable, str(REPO / "research/scripts/import_pilot.py"),
                        "--input", str(src), "--dataset", "D", "--register", str(reg),
                        "--out-root", str(tmp_path / "out")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    lines = (tmp_path / "out/D/1/samples.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 4
    assert json.loads((tmp_path / "out/D/1/import_report.json").read_text())["ok"] is True
