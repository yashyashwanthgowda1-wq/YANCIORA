"""Feature 5 — critical-detail extraction and meaning check (rules_v1).
All texts are unit-test fixtures written for these tests, not dataset samples."""
import pytest
from pydantic import ValidationError

from app.core import details as D
from app.schemas import CriticalDetailsRequest, MeaningCheckRequest
from app.services.meaning import LIMITATIONS, check, critical_details


def values(text, category, language="en", terms=()):
    return [d.value for d in D.extract_details(text, language, terms) if d.category == category]


def run(original, candidate, language="en", terms=()):
    return check(MeaningCheckRequest(original=original, candidate=candidate, language=language,
                                     protected_terms=list(terms)))


def states(resp):
    return {(f.category, f.value): f.state for f in resp.findings if f.state != "kept"}


# ---------- extraction ----------
@pytest.mark.parametrize("text,expected", [
    ("Order 42 now", ["42"]),
    ("Pay 1,00,000 later", ["100000"]),
    ("೫೦೦ ಜನ", ["500"]),                          # Kannada digits
    ("५ लोग", ["5"]),                              # Devanagari digits
    ("Rate 2.75 and 50%", ["2.75", "50%"]),
    ("Change by -3 today", ["-3"]),
    ("Model A-5 ships", ["5"]),                    # hyphen after a letter is not a minus sign
    ("Budget 5 lakh for it", ["5lakh"]),
])
def test_numbers(text, expected):
    assert values(text, "number") == expected


@pytest.mark.parametrize("text,expected", [
    ("Send ₹500", ["INR 500"]),
    ("Send Rs. 500", ["INR 500"]),
    ("Send Rs500", ["INR 500"]),
    ("Send 500 rupees", ["INR 500"]),
    ("Send INR 2,500", ["INR 2500"]),
    ("Send $20 and €5 and £3", ["USD 20", "EUR 5", "GBP 3"]),
    ("Send ₹5 lakh", ["INR 5lakh"]),
])
def test_money(text, expected):
    assert values(text, "money") == expected
    assert values(text, "number") == []            # not double-counted


def test_rsvp_is_not_money():
    assert values("Please RSVP 3 days early", "money") == []


@pytest.mark.parametrize("text,expected", [
    ("on 12/01/2026", ["12/01/2026"]),
    ("on 2026-01-12", ["2026-01-12"]),
    ("on 12 Jan 2026", ["12 jan 2026"]),
    ("on 3rd March", ["3rd march"]),
    ("on January 12, 2026", ["january 12, 2026"]),
    ("at 17:30", ["17:30"]),
    ("at 5 p.m.", ["5pm"]),
    ("at 5pm", ["5pm"]),
    ("at 9:15 AM", ["9:15am"]),
])
def test_datetime(text, expected):
    assert values(text, "datetime") == expected


def test_may_alone_is_not_a_date():
    assert values("You may go", "datetime") == []


def test_url_email_code_quoted():
    t = ('See https://example.test/a?id=7, mail Ops@Example.test, run `rm -rf tmp` and '
         'reply "yes 100"')
    assert values(t, "url") == ["https://example.test/a?id=7"]   # trailing comma stripped
    assert values(t, "email") == ["ops@example.test"]
    assert values(t, "code") == ["rm -rf tmp"]
    assert values(t, "quoted") == ["yes 100"]
    assert values(t, "number") == []                             # 7 and 100 are inside details


def test_code_fence_keeps_whitespace():
    t = "Fix:\n```\ndef f():\n    return 1\n```"
    assert values(t, "code") == ["def f():\n    return 1"]


@pytest.mark.parametrize("text,language,expected", [
    ("Do not stop", "en", ["not"]),
    ("Don't stop", "en", ["not"]),
    ("Don’t stop", "en", ["not"]),                 # curly apostrophe
    ("I cannot come, never again", "en", ["not", "never"]),
    ("Notable notes", "en", []),                   # whole-word match only
    ("कल मत आना", "hi", ["hi:mat"]),
    ("मैं नहीं आऊँगा", "hi", ["hi:nahin"]),
    ("ನಾನು ಬರುವುದಿಲ್ಲ", "kn", ["kn:illa"]),       # negative verb ending
    ("ಅದು ಬೇಡ", "kn", ["kn:beda"]),
    ("அவன் வரவில்லை", "ta", ["ta:illai"]),
    ("అతను రాలేదు", "te", ["te:ledu"]),
    ("main kal nahi aaunga", "hi", ["hi:nahin"]),  # Romanized, language given
])
def test_negations(text, language, expected):
    assert values(text, "negation", language) == expected


def test_romanized_negation_needs_language():
    assert values("main kal nahi aaunga", "negation", language=None) == []


def test_auto_language_uses_native_script_lexicon():
    assert values("ನಾನು ಬರುವುದಿಲ್ಲ", "negation", language=None) == ["kn:illa"]


def test_protected_terms_and_offsets():
    text = "Book  Bengaluru One for ₹200 at 4pm."
    found = D.extract_details(text, "en", ["Bengaluru One"])
    src = D.nfc(text)
    assert all(src[d.start:d.end] == d.text for d in found)
    assert [d.category for d in found] == ["protected_term", "money", "datetime"]


def test_lexicon_file_is_valid_and_indic_lists_unreviewed():
    lexes = D.load_lexicons()
    assert {lx.language for lx in lexes} == {"en", "hi", "kn", "ta", "te"}
    assert all(lx.review_status in D.REVIEW_STATUSES for lx in lexes)
    # Until native speakers approve them (team decision, 2026-11-20):
    assert all(lx.review_status == "unreviewed" for lx in lexes if lx.language != "en")


# ---------- meaning check ----------
def test_identical_and_whitespace_only_preserved():
    for cand in ("Pay ₹500 by 5 pm, not later.", "Pay  ₹500 by 5 pm,\nnot later. "):
        r = run("Pay ₹500 by 5 pm, not later.", cand)
        assert r.status == "preserved" and r.risks == []


@pytest.mark.parametrize("original,candidate", [
    ("Don't pay ₹500.", "Do not pay Rs. 500."),
    ("Please kindly send 3 files.", "Send 3 files."),
    ("Meet on 12 Jan 2026 at 5 p.m.", "Meet 12 Jan 2026, 5 PM."),
])
def test_equivalent_rewrites_preserved(original, candidate):
    assert run(original, candidate).status == "preserved"


@pytest.mark.parametrize("original,candidate,expected", [
    ("Pay ₹500.", "Pay $500.", {("money", "INR 500"): "missing", ("money", "USD 500"): "added"}),
    ("Send 3 files.", "Send 4 files.", {("number", "3"): "missing", ("number", "4"): "added"}),
    ("Send 3 files by Friday.", "Send files by Friday.", {("number", "3"): "missing"}),
    ("Send the files.", "Send 10 files.", {("number", "10"): "added"}),
    ("Do not delete the logs.", "Delete the logs.", {("negation", "not"): "missing"}),
    ("Open https://a.test/x now", "Open https://a.test/y now",
     {("url", "https://a.test/x"): "missing", ("url", "https://a.test/y"): "added"}),
    ("Email a@b.test", "Email c@b.test", {("email", "a@b.test"): "missing", ("email", "c@b.test"): "added"}),
    ("Run `ls -la` first", "Run `ls` first", {("code", "ls -la"): "missing", ("code", "ls"): "added"}),
    ('Reply "approved"', 'Reply "ok"', {("quoted", "approved"): "missing", ("quoted", "ok"): "added"}),
    ("Meet at 5 pm", "Meet at 6 pm", {("datetime", "5pm"): "missing", ("datetime", "6pm"): "added"}),
])
def test_detail_changes_are_changed(original, candidate, expected):
    r = run(original, candidate)
    assert r.status == "changed"
    assert states(r) == expected
    assert r.missing_count == sum(1 for s in expected.values() if s == "missing")


def test_code_whitespace_change_detected():
    o = "```\nif x:\n    y()\n```"
    assert run(o, "```\nif x:\ny()\n```").status == "changed"


def test_protected_term_removed_is_changed():
    r = run("Ask Bengaluru One about it.", "Ask about it.", terms=["Bengaluru One"])
    assert r.status == "changed" and states(r) == {("protected_term", "Bengaluru One"): "missing"}


def test_protected_term_absent_warns():
    r = run("Ask about it.", "Ask about it!", terms=["Bengaluru One"])
    assert any("not found in the original" in w for w in r.warnings)


def test_number_order_change_is_at_risk():
    r = run("Send 5 to A and 7 to B", "Send 7 to A and 5 to B")
    assert r.status == "at_risk" and "order" in r.risks[0]


def test_large_shrink_is_at_risk():
    o = "Write a short polite email to the team explaining the meeting has moved online."
    r = run(o, "Write an email.")
    assert r.status == "at_risk" and any("less than 50%" in x for x in r.risks)


def test_kannada_negation_removed_is_changed():
    r = run("ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ", "ನಾನು ನಾಳೆ ಬರುತ್ತೇನೆ", language="kn")
    assert r.status == "changed" and states(r) == {("negation", "kn:illa"): "missing"}


def test_unreviewed_lexicon_makes_edits_at_risk():
    r = run("ನನಗೆ ೫೦೦ ಪುಸ್ತಕ ಬೇಕು ದಯವಿಟ್ಟು", "ನನಗೆ 500 ಪುಸ್ತಕ ಬೇಕು", language="kn")
    assert r.status == "at_risk"                    # digits preserved across scripts
    assert any("kn-Knda" in x for x in r.risks)
    assert {lx.id: lx.review_status for lx in r.negation_lexicons}["kn-Knda"] == "unreviewed"


def test_unreviewed_lexicon_no_risk_when_unchanged():
    assert run("ನಾನು ಬರುವುದಿಲ್ಲ", "ನಾನು  ಬರುವುದಿಲ್ಲ", language="kn").status == "preserved"


def test_response_always_carries_limitations_and_method():
    r = run("a 1", "a 1")
    assert r.method == "rules_v1" and r.limitations == LIMITATIONS
    assert any("not a guarantee" in x for x in r.limitations)


def test_auto_latin_warns_about_romanized():
    r = check(MeaningCheckRequest(original="kal nahi", candidate="kal nahi"))
    assert any("Romanized" in w for w in r.warnings) and r.language is None


def test_critical_details_service_offsets():
    req = CriticalDetailsRequest(text="ನನಗೆ ₹500 ಬೇಡ", language="kn")
    r = critical_details(req)
    assert r.language == "kn"
    assert all(r.text[d.start:d.end] == d.text for d in r.details)
    assert [(d.category, d.value) for d in r.details] == [("money", "INR 500"), ("negation", "kn:beda")]


@pytest.mark.parametrize("kwargs", [
    {"original": "   ", "candidate": "x"},
    {"original": "x", "candidate": ""},
    {"original": "x" * 20_001, "candidate": "x"},
    {"original": "x", "candidate": "x", "language": "ml"},
    {"original": "x", "candidate": "x", "protected_terms": [" "]},
    {"original": "x", "candidate": "x", "protected_terms": ["t"] * 51},
    {"original": "x", "candidate": "x", "protected_terms": ["t" * 201]},
])
def test_request_validation(kwargs):
    with pytest.raises(ValidationError):
        MeaningCheckRequest(**kwargs)


# ---------- performance regression (found while building Feature 3) ----------
@pytest.mark.parametrize("text", ["1" * 20_000, "1," * 10_000, "a." * 10_000, "a" * 20_000,
                                  "word " * 4_000])
def test_extraction_is_linear_on_adversarial_input(text):
    """MONEY_SUFFIX took ~80 s and EMAIL ~3 s on 20,000-character runs before the fix."""
    import time

    start = time.perf_counter()
    D.extract_details(text, "en")
    assert time.perf_counter() - start < 2.0


def test_money_and_email_matches_unchanged_by_performance_fix():
    found = [(d.category, d.value) for d in
             D.extract_details("x,5 rupees and 1,234.50 rupees, Rs 7, mail a.b+c@x.test", "en")]
    assert found == [("money", "INR 5"), ("money", "INR 1234.50"), ("money", "INR 7"),
                     ("email", "a.b+c@x.test")]
