"""English validation matrix (Phase 8). Every entry of the shipped English phrase list
(phrases/en.yaml, developer_curated and INACTIVE) is run as if a reviewer had approved it, in
seven contexts: negation, condition, constraint, name, question, number/date and tone.

Expected (and recorded in docs/review/english_phrase_validation.md):
- the 7 redundant-expression rules apply and every critical detail and politeness marker survives;
- the 4 request-frame rules (could/can you please, I would like/want you to) are never applied
  automatically: they change tone, so they are suggestions, and next to a negation they are rejected.
Passing this test does NOT activate the list: activation needs a team reviewer (D59, D63).
"""
from __future__ import annotations

import dataclasses
from collections import Counter

import pytest

from app.core import details as D
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer as O
from tests.conftest import FakeTokenizer


CONTEXTS = {  # pattern -> (context, text)
 "in order to": [("negation","Do not restart the server in order to clear the cache."),("condition","If the build fails, rerun it in order to get logs."),("constraint","You must log in in order to see the report."),("name","Ask Priya in order to get access."),("question","Should I wait in order to save money?"),("number/date","Send 3 copies by 12 Jan 2026 in order to meet the deadline."),("tone","Kindly wait in order to avoid errors.")],
 "due to the fact that": [("negation","It failed due to the fact that the key was not set."),("condition","Stop if it fails due to the fact that the disk is full."),("constraint","Only retry due to the fact that the API was down."),("name","Ravi left due to the fact that Meera arrived."),("question","Was it late due to the fact that it rained?"),("number/date","We paid ₹500 due to the fact that the fee rose on 1 March."),("tone","Please note it closed due to the fact that it was a holiday.")],
 "at this point in time": [("negation","We cannot ship at this point in time."),("condition","If it is safe at this point in time, deploy."),("constraint","You must not deploy at this point in time."),("name","Asha is busy at this point in time."),("question","Is it ready at this point in time?"),("number/date","We have 2 servers at this point in time."),("tone","Kindly hold off at this point in time.")],
 "in the event that": [("negation","Do not call in the event that it rains."),("condition","Call me in the event that the train is late."),("constraint","You must stop in the event that errors appear."),("name","Tell Kiran in the event that it fails."),("question","What happens in the event that it fails?"),("number/date","Pay ₹200 in the event that the bill exceeds 5 kg."),("tone","Please inform us in the event that you are late.")],
 "for the purpose of": [("negation","Do not use it for the purpose of testing."),("condition","If needed for the purpose of audit, keep logs."),("constraint","Use it only for the purpose of research."),("name","Ravi built it for the purpose of teaching."),("question","Is this data for the purpose of training?"),("number/date","Keep 10 copies for the purpose of the 2026 audit."),("tone","Kindly use it for the purpose of review.")],
 "with regard to": [("negation","We have no news with regard to the refund."),("condition","If you have doubts with regard to pricing, ask."),("constraint","You must be careful with regard to privacy."),("name","Email Priya with regard to the contract."),("question","Any update with regard to the order?"),("number/date","Call on 5 May with regard to the ₹900 invoice."),("tone","Please write with regard to the delay.")],
 "a large number of": [("negation","Do not send a large number of emails."),("condition","If a large number of users join, scale up."),("constraint","You must handle a large number of requests."),("name","Ravi got a large number of messages."),("question","Did a large number of people sign up?"),("number/date","By 2026 a large number of farmers used it."),("tone","Kindly review a large number of files.")],
 "could you please": [("negation","Could you please not share this file?"),("condition","Could you please call if it rains?"),("constraint","Could you please reply only in Kannada?"),("name","Could you please email Priya?"),("question","Could you please check the order?"),("number/date","Could you please send 3 files by 12 Jan 2026?"),("tone","Could you please write a short poem.")],
 "can you please": [("negation","Can you please not delete the logs?"),("condition","Can you please retry unless it fails twice?"),("constraint","Can you please list at most 5 items?"),("name","Can you please call Ravi?"),("question","Can you please explain this?"),("number/date","Can you please book 2 seats for Monday?"),("tone","Can you please list the steps.")],
 "i would like you to": [("negation","I would like you to never share passwords."),("condition","I would like you to stop if errors appear."),("constraint","I would like you to answer only in Hindi."),("name","I would like you to thank Meera."),("question","I would like you to tell me: is it safe?"),("number/date","I would like you to send 4 copies by 3 June."),("tone","I would like you to explain recursion.")],
 "i want you to": [("negation","I want you to not use slang."),("condition","I want you to wait until the build ends."),("constraint","I want you to use exactly 3 bullet points."),("name","I want you to meet Asha."),("question","I want you to check: does it compile?"),("number/date","I want you to finish 2 tasks by 9 pm."),("tone","I want you to explain recursion.")],
}

REQUEST_FRAMES = {"could you please", "can you please", "i would like you to", "i want you to"}


def _as_reviewed() -> tuple[R.PhraseList, ...]:
    en = next(pl for pl in R.load_phrase_lists() if pl.id == "en")
    return (dataclasses.replace(en, review_status="reviewed"),)


def _details(text: str) -> Counter:
    return Counter((d.category, d.value) for d in D.extract_details(
        text, lexicons=D.active_lexicons("en", text), markers=D.active_markers("en", text)))


def _run(text: str):
    req = OptimizeRequest(text=text, language="en", mode="balanced", tokenizers=["fake_bytes"])
    return O.optimize(req, adapters=[FakeTokenizer()], phrase_lists=_as_reviewed())


def test_matrix_covers_every_shipped_entry_and_all_contexts():
    en = next(pl for pl in R.load_phrase_lists() if pl.id == "en")
    assert {e.pattern for e in en.entries} == set(CONTEXTS)
    want = {"negation", "condition", "constraint", "name", "question", "number/date", "tone"}
    assert all({c for c, _ in v} == want for v in CONTEXTS.values())


CASES = [(p, c, t) for p, v in CONTEXTS.items() for c, t in v]


@pytest.mark.parametrize("pattern, context, text", [x for x in CASES if x[0] not in REQUEST_FRAMES])
def test_redundant_expression_rules_keep_every_detail(pattern, context, text):
    r = _run(text)
    applied = [a for a in r.accepted if a.rule.startswith("phrase:")]
    assert applied, f"{pattern} not applied in {context}"
    assert pattern not in r.optimized.lower()
    assert r.meaning_check.status == "preserved"
    assert _details(r.optimized) == _details(text)
    assert D.register_markers(r.optimized, "en") == D.register_markers(text, "en")


@pytest.mark.parametrize("pattern, context, text", [x for x in CASES if x[0] in REQUEST_FRAMES])
def test_request_frames_are_never_applied_automatically(pattern, context, text):
    r = _run(text)
    assert not any(a.rule.startswith("phrase:") for a in r.accepted)
    assert r.optimized == text
    if context == "negation":
        assert any(x.stage in ("protected", "meaning") for x in r.rejected)
    else:
        assert r.requires_review and r.suggestions


def test_shipped_english_list_still_inactive():
    en = next(pl for pl in R.load_phrase_lists() if pl.id == "en")
    assert en.review_status == "developer_curated"
