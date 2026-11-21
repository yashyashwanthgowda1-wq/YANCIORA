"""Every rule of the approved English phrase list (D64), run in balanced mode inside a sentence
that holds a negation, a number and a name: an applied rule must keep every critical detail; a rule
that would change a detail, politeness or an opposite word must never be applied automatically."""
from collections import Counter

import pytest

from app.core import details as D
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer as O
from tests.conftest import FakeTokenizer

EN = next(pl for pl in R.load_phrase_lists() if pl.id == "en")
# Rules expected to stay suggestions: they remove politeness or add an opposite-pair word.
SUGGESTION_ONLY = {"could you please", "can you please", "i would like you to", "i want you to",
                   "please note that", "prior to", "subsequent to", "in close proximity to"}


def _details(text):
    return Counter((d.category, d.value) for d in D.extract_details(text, "en"))


def _text(e):
    p = e.pattern
    return (f"{p[0].upper() + p[1:]} the data, do not share the 3 files with Priya." if e.at_sentence_start
            else f"Do not share the 3 files with Priya; {p} the data.")


def _run(text):
    return O.optimize(OptimizeRequest(text=text, language="en", mode="balanced", tokenizers=["fake_bytes"]),
                      adapters=[FakeTokenizer()])


@pytest.mark.parametrize("entry", EN.entries, ids=[e.pattern for e in EN.entries])
def test_rule_keeps_every_detail_or_is_not_applied(entry):
    text = _text(entry)
    r = _run(text)
    applied = [a for a in r.accepted if a.rule.startswith("phrase:")]
    if entry.pattern in SUGGESTION_ONLY:
        assert not applied and r.optimized == text
    else:
        assert applied, f"{entry.pattern} was not applied"
        assert entry.pattern not in r.optimized.lower()
    assert _details(r.optimized) == _details(text)
    assert r.meaning_check.status != "changed"


def test_wordy_english_prompt_is_really_shortened():
    text = ("It is important to note that you should conduct an analysis of the sales data on a monthly basis. "
            "In order to make a decision, provide a summary of the end result in a clear and concise manner. "
            "Do not include the 2 confidential accounts.")
    r = _run(text)
    assert r.optimized == ("You should analyze the sales data monthly. To decide, summarize the result "
                           "clearly and concisely. Do not include the 2 confidential accounts.")
    assert _details(r.optimized) == _details(text) and r.meaning_check.status == "preserved"
    assert r.token_counts[0].saved > 0


# ---- regressions found in the browser acceptance test (opt_rules_v4) ----
def test_politeness_frame_kept_even_when_repeated_copies_exist():
    block = "Hello! I would like you to help me with the report. Do not include the 2 names. "
    r = _run(block * 3)
    assert r.optimized.startswith("Hello! I would like you to help me")        # not silently dropped
    assert r.optimized.count("Do not include the 2 names.") == 1                 # repeats removed
    assert any(s.before.lower().startswith("i would like you to") and s.meaning_status == "at_risk"
               for s in r.suggestions)                                          # offered for approval


def test_short_repeat_removed_inside_text_but_list_lines_kept():
    r = _run("Hello! Summarise the report today. Hello! Summarise the report today.")
    assert r.optimized == "Hello! Summarise the report today."
    r2 = _run("Answers:\nYes\nNo\nYes\n")
    assert r2.optimized.split("\n")[:4] == ["Answers:", "Yes", "No", "Yes"]
