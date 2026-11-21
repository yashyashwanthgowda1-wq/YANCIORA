"""rules_v5 regression tests: gaps found by a 2026-11-21 adversarial probe, where a meaning
change returned 'preserved'. Each fixed case must now be 'changed' or 'at_risk'; equivalent
rewrites must stay 'preserved'."""
import pytest

from app.core.details import extract_details, number_word_value
from app.schemas import MeaningCheckRequest
from app.services.meaning import ROMANIZED_MARKER_RISK, check


def _status(original: str, candidate: str, language: str = "en") -> str:
    return check(MeaningCheckRequest(original=original, candidate=candidate, language=language)).status


@pytest.mark.parametrize("original, candidate", [
    ("Use five servers.", "Use six servers."),                 # B5-2, English number words
    ("Add twenty-one rows.", "Add twelve rows."),
    ("Keep two hundred and five records.", "Keep two hundred records."),
    ("Call me tomorrow.", "Call me today."),                   # relative-day words
    ("Finish it by tonight.", "Finish it by tomorrow."),
    ("Leave the day after tomorrow.", "Leave tomorrow."),
])
def test_english_number_and_day_word_changes_are_changed(original, candidate):
    assert _status(original, candidate) == "changed"


@pytest.mark.parametrize("original, candidate", [
    ("Send the report before Friday.", "Send the report after Friday."),   # B5-4 opposites
    ("Increase the limit.", "Decrease the limit."),
    ("Include the tests.", "Exclude the tests."),
    ("Enable logging for the job.", "Disable logging for the job."),
    ("Keep the repository private.", "Keep the repository public."),
])
def test_english_opposite_swaps_require_review(original, candidate):
    r = check(MeaningCheckRequest(original=original, candidate=candidate, language="en"))
    assert r.status == "at_risk"
    assert any("opposite pairs" in x for x in r.risks)


@pytest.mark.parametrize("original, candidate", [
    ("Use five servers.", "Use 5 servers."),
    ("Add twenty-one rows.", "Add 21 rows."),
    ("Budget is five lakh.", "Budget is 5 lakh."),
    ("Send it  today.", "Send it today."),
    ("In order to win, send it before Friday.", "To win, send it before Friday."),
])
def test_equivalent_english_rewrites_stay_preserved(original, candidate):
    assert _status(original, candidate) == "preserved"


@pytest.mark.parametrize("phrase, value", [
    ("five", "5"), ("twenty-one", "21"), ("two hundred and five", "205"),
    ("one thousand two hundred", "1200"), ("five lakh", "5lakh"), ("two million", "2million"),
])
def test_number_word_values(phrase, value):
    assert number_word_value(phrase) == value
    assert [(d.category, d.value) for d in extract_details(phrase)] == [("number", value)]


@pytest.mark.parametrize("original, candidate", [
    # A single Romanized Indic negation in otherwise English text, language not given:
    # rules_v4 returned 'preserved' because the warning needed 2+ Romanized words.
    ("Please share the file, password beda.", "Please share the file, password."),   # kn beda = don't
    ("Send the report, mat bhejo email.", "Send the report, bhejo email."),          # hi mat = don't
    ("Reply in English, Tamil illai.", "Reply in English, Tamil."),                  # ta illai = no/not
])
def test_single_romanized_negation_change_without_language_requires_review(original, candidate):
    r = check(MeaningCheckRequest(original=original, candidate=candidate, language="auto"))
    assert r.status != "preserved"
    assert any(x.startswith(ROMANIZED_MARKER_RISK.split("(")[0]) for x in r.risks)


def test_romanized_marker_untouched_without_language_stays_preserved():
    r = check(MeaningCheckRequest(original="Please  share the file, password beda.",
                                  candidate="Please share the file, password beda.", language="auto"))
    assert r.status == "preserved"


def test_english_words_without_romanized_markers_not_flagged():
    r = check(MeaningCheckRequest(original="Write a short poem about the sea.",
                                  candidate="Write a poem about the sea.", language="auto"))
    assert r.status == "preserved"
