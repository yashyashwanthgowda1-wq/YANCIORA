"""Native-speaker review system: dataset validity, honesty rules, merge workflow, and how review
decisions change optimizer behaviour. Approvals in these tests are TEST FIXTURES in a temporary
copy of the data, never written to the shipped files."""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from app.core import details as D
from app.linguistics import review as RV
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer as O
from tests.conftest import FakeTokenizer

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "research" / "scripts"
BYTES = [FakeTokenizer()]


# ---------- the shipped datasets ----------
def test_all_five_languages_load_and_validate():
    data = RV.load_all()
    assert set(data) == {"kn", "hi", "ta", "te", "en"}
    for lang, entries in data.items():
        assert len(entries) >= 13
        for e in entries:
            assert e.provenance and e.gloss and e.decision in RV.DECISIONS
            if e.decision != "pending_review":                 # loader enforces this too
                assert e.reviewer and e.reviewed_at


def test_every_category_is_covered_for_each_indic_language():
    for lang in ("kn", "hi", "ta", "te"):
        cats = {e.category for e in RV.load_all()[lang]}
        assert cats == set(RV.CATEGORIES), (lang, set(RV.CATEGORIES) - cats)


def test_nothing_is_marked_approved_without_a_named_reviewer():
    for f in RV.REVIEW_DIR.glob("*.yaml"):
        for raw in yaml.safe_load(f.read_text(encoding="utf-8"))["entries"]:
            dec = raw["review"]["decision"]
            assert dec == "pending_review" or (raw["review"].get("reviewer") and raw["review"].get("reviewed_at")), raw["id"]


def test_drafted_entries_are_labelled_as_unverified():
    for lang in ("kn", "hi", "ta", "te"):
        for e in RV.load_all()[lang]:
            if e.decision == "pending_review":
                assert "not verified" in e.provenance


def test_negation_yaml_and_review_data_agree():
    """Every Indic form in core/lexicons/negation.yaml has a matching review entry (no
    contradictory duplicates between the two files)."""
    review = {(e.language, e.script, e.expression.lower(), e.canonical, e.lexicon_ref)
              for es in RV.load_all().values() for e in es if e.lexicon_ref}
    for lx in D.load_lexicons():
        if lx.language == "en":
            continue
        for e in lx.entries:
            assert (lx.language, lx.script, e.form, e.canonical, lx.id) in review, (lx.id, e.form)


def test_english_phrase_list_is_approved_and_original_entries_mirrored():
    # D64: the English phrase list is approved (active); its 11 original entries stay mirrored in
    # the review dataset, whose entries remain pending_review.
    en_list = next(pl for pl in R.load_phrase_lists() if pl.id == "en")
    assert en_list.review_status == "reviewed"
    mirrored = {e.expression for e in RV.load_all()["en"] if e.phrase_ref}
    assert len(mirrored) == 11 and mirrored <= {entry.pattern for entry in en_list.entries}
    assert all(e.decision == "pending_review" for e in RV.load_all()["en"])
    politeness = [e for e in RV.load_all()["en"] if e.phrase_ref and e.changes_register == "yes"]
    assert len(politeness) == 4 and not any(e.safe_for_auto for e in politeness)


def test_register_changing_entry_is_never_auto_even_if_approved():
    raw = {"id": "x", "category": "shortening", "script": "Knda", "expression": "ಎ ಬಿ", "gloss": "g",
           "original": "ಎ ಬಿ", "proposed": "ಎ", "preserves_meaning": "yes", "changes_register": "yes",
           "safe_for_auto": True, "review": {"decision": "approved", "reviewer": "T", "reviewed_at": "2026-11-21"}}
    assert not RV.parse_entry(raw, "kn", "p", "t").auto_eligible
    raw["changes_register"] = "no"
    assert RV.parse_entry(raw, "kn", "p", "t").auto_eligible


@pytest.mark.parametrize("bad,msg", [
    ({"review": {"decision": "approved"}}, "needs review.reviewer"),
    ({"review": {"decision": "maybe"}}, "review.decision"),
    ({"review": {"decision": "corrected", "reviewer": "T", "reviewed_at": "d"}}, "needs review.correction"),
    ({"proposed": "ಎ ಬಿ ಸಿ"}, "must be shorter"),
])
def test_loader_rejects_invalid_entries(bad, msg):
    raw = {"id": "x", "category": "shortening", "script": "Knda", "expression": "ಎ ಬಿ", "gloss": "g",
           "original": "ಎ ಬಿ", "proposed": "ಎ", "review": {"decision": "pending_review"}}
    raw.update(bad)
    with pytest.raises(RV.ReviewDataError, match=msg):
        RV.parse_entry(raw, "kn", "p", "t")


def test_shipped_data_has_no_automatic_indic_rule():
    sets = RV.phrase_rule_sets()
    for lang in ("kn", "hi", "ta", "te"):
        assert sets[lang]["auto"] == [] or all(e.is_approved for e in sets[lang]["auto"])


# ---------- merge workflow (JSON from the review screen, CSV from the spreadsheet) ----------
def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=REPO)


@pytest.fixture
def review_copy(tmp_path):
    d = tmp_path / "review"
    shutil.copytree(RV.REVIEW_DIR, d)
    return d


def test_json_decisions_merge_and_validate(review_copy, tmp_path):
    decisions = {"schema": "redutax-review-decisions/v1", "language": "kn", "reviewer": "ignored-here",
                 "decisions": [
                     {"id": "kn-red-002", "decision": "approved", "notes": "fine",
                      "preserves_meaning": "yes", "changes_register": "no", "safe_for_auto": True},
                     {"id": "kn-q-006", "decision": "rejected", "notes": "test rejection"},
                     {"id": "kn-red-003", "decision": "corrected", "correction": {"proposed": "ಕೆಳಗಿನ"},
                      "preserves_meaning": "yes", "changes_register": "no", "safe_for_auto": False}]}
    f = tmp_path / "d.json"
    f.write_text(json.dumps(decisions, ensure_ascii=False), encoding="utf-8")
    before = (review_copy / "kn.yaml").read_text(encoding="utf-8")
    r = run_script("apply_review_decisions.py", "--decisions", str(f), "--reviewer", "Test Reviewer",
                   "--date", "2026-11-21", "--review-dir", str(review_copy))
    assert r.returncode == 0, r.stderr + r.stdout
    after = (review_copy / "kn.yaml").read_text(encoding="utf-8")
    assert sum(1 for a, b in zip(before.splitlines(), after.splitlines()) if a != b) == 3   # only 3 lines changed
    entries = {e.id: e for e in RV.load_file(review_copy / "kn.yaml")}
    assert entries["kn-red-002"].auto_eligible and entries["kn-red-002"].reviewer == "Test Reviewer"
    assert entries["kn-q-006"].decision == "rejected"
    assert entries["kn-red-003"].decision == "corrected" and not entries["kn-red-003"].auto_eligible
    assert all(e.decision == "pending_review" for e in RV.load_all()["kn"])               # shipped file untouched


def test_csv_round_trip(review_copy, tmp_path):
    sheet = tmp_path / "sheet.csv"
    r = run_script("export_review_sheet.py", "--language", "hi", "--out", str(sheet))
    assert r.returncode == 0, r.stderr
    rows = list(csv.DictReader(sheet.open(encoding="utf-8-sig")))
    assert len(rows) == len(RV.load_all()["hi"]) and rows[0]["current_decision"] == "pending_review"
    for row in rows:
        if row["id"] == "hi-red-001":
            row.update(YOUR_DECISION="approve", PRESERVES_MEANING="yes", CHANGES_TONE="no",
                       SAFE_FOR_AUTOMATIC_USE="yes", NOTES="ok")
    with sheet.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    r = run_script("apply_review_decisions.py", "--decisions", str(sheet), "--language", "hi",
                   "--reviewer", "Sheet Reviewer", "--review-dir", str(review_copy))
    assert r.returncode == 0, r.stderr + r.stdout
    e = {x.id: x for x in RV.load_file(review_copy / "hi.yaml")}["hi-red-001"]
    assert e.auto_eligible and e.review_notes == "ok"


@pytest.mark.parametrize("decision,extra,err", [
    ({"id": "kn-nope", "decision": "approved"}, [], "unknown id"),
    ({"id": "kn-red-002", "decision": "corrected"}, [], "needs a corrected"),
    ({"id": "kn-red-002", "decision": "approved"}, ["--reviewer", " "], "reviewer"),
])
def test_merge_refuses_bad_input(review_copy, tmp_path, decision, extra, err):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"schema": "redutax-review-decisions/v1", "language": "kn", "decisions": [decision]}),
                 encoding="utf-8")
    args = ["--decisions", str(f), "--review-dir", str(review_copy)] + (extra or ["--reviewer", "T"])
    r = run_script("apply_review_decisions.py", *args)
    assert r.returncode != 0 and err in (r.stderr + r.stdout)
    assert (review_copy / "kn.yaml").read_text(encoding="utf-8") == (RV.REVIEW_DIR / "kn.yaml").read_text(encoding="utf-8")


# ---------- review decisions drive the optimizer ----------
KN_TEXT = "ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ಮತ್ತೆ ವರದಿ ಕಳುಹಿಸಿ."


def opt(text, lang, mode, lists):
    return O.optimize(OptimizeRequest(text=text, language=lang, mode=mode, tokenizers=["fake_bytes"]), BYTES,
                      phrase_lists=lists)


def test_pending_rule_is_only_an_aggressive_suggestion():
    lists = R.review_phrase_lists()
    bal = opt(KN_TEXT, "kn", "balanced", lists)
    assert bal.optimized == KN_TEXT and not any(s.rule.startswith("phrase:") for s in bal.suggestions)
    agg = opt(KN_TEXT, "kn", "aggressive", lists)
    s = [x for x in agg.suggestions if x.source == "kn-red-002"]
    assert s and s[0].kind == "unreviewed_phrase" and s[0].approval_required and s[0].risk == "meaning_change"
    assert "pending native-speaker review" in s[0].reason and agg.optimized == KN_TEXT


def _approve(review_copy, tmp_path, ids, safe=True):
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"schema": "redutax-review-decisions/v1", "language": "kn", "decisions": [
        {"id": i, "decision": "approved", "preserves_meaning": "yes", "changes_register": "no", "safe_for_auto": safe}
        for i in ids]}, ensure_ascii=False), encoding="utf-8")
    r = run_script("apply_review_decisions.py", "--decisions", str(f), "--reviewer", "Fixture",
                   "--review-dir", str(review_copy))
    assert r.returncode == 0, r.stderr


def test_approved_rule_waits_for_reviewed_detection_lists(review_copy, tmp_path):
    """An approved Kannada rewrite is still only a suggestion while the Kannada negation and marker
    lists are pending: the meaning check cannot vouch for Kannada words yet."""
    _approve(review_copy, tmp_path, ["kn-red-002"])
    RV.load_all.cache_clear()
    lists = R.review_phrase_lists(review_copy)
    r = opt(KN_TEXT, "kn", "balanced", lists)
    assert r.optimized == KN_TEXT
    s = [x for x in r.suggestions if x.source == "kn-red-002"]
    assert s and s[0].kind == "at_risk_edit" and s[0].meaning_status == "at_risk"
    RV.load_all.cache_clear()


def test_fully_reviewed_language_applies_approved_rule(review_copy, tmp_path, monkeypatch):
    """Fixture: every Kannada detection entry and the negation lists approved → the approved
    rewrite is applied automatically, with its source, risk and token counts recorded."""
    kn_ids = [e.id for e in RV.load_file(review_copy / "kn.yaml") if not e.is_rewrite]
    _approve(review_copy, tmp_path, ["kn-red-002"] + kn_ids)
    RV.load_all.cache_clear()
    RV.marker_lexicons.cache_clear()
    reviewed_markers = RV.marker_lexicons(review_copy)
    monkeypatch.setattr(RV, "marker_lexicons", lambda directory=None: reviewed_markers)
    reviewed_lex = tuple(D.Lexicon(lx.id, lx.language, lx.script, "reviewed", lx.entries) for lx in D.load_lexicons())
    monkeypatch.setattr(D, "load_lexicons", lambda path=None: reviewed_lex)
    lists = R.review_phrase_lists(review_copy)
    r = opt(KN_TEXT, "kn", "balanced", lists)
    assert r.optimized == "ದಯವಿಟ್ಟು ಮತ್ತೊಮ್ಮೆ ವರದಿ ಕಳುಹಿಸಿ."
    a = next(x for x in r.accepted if x.source == "kn-red-002")
    assert a.risk == "wording" and a.language == "kn" and not a.approval_required and a.validation == "preserved"
    assert a.tokens_after["fake_bytes"] < a.tokens_before["fake_bytes"]
    safe = opt(KN_TEXT, "kn", "safe", lists)
    assert safe.optimized == KN_TEXT                                   # safe mode stays lossless
    RV.load_all.cache_clear()


def test_api_review_endpoints():
    from fastapi.testclient import TestClient

    from app.main import create_app

    c = TestClient(create_app())
    s = c.get("/api/linguistics/summary").json()
    assert set(s["languages"]) == {"kn", "hi", "ta", "te", "en"} and "merge" in s["note"]
    r = c.get("/api/linguistics/review/kn").json()
    assert r["counts"]["pending_review"] == len(r["entries"]) - sum(v for k, v in r["counts"].items() if k != "pending_review")
    assert all(e["use"] for e in r["entries"]) and r["schema_id"] == "redutax-review/v1"
    assert c.get("/api/linguistics/review/fr").status_code == 404
