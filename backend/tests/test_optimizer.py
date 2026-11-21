"""Feature 3 — smart prompt optimizer (opt_rules_v1).
All texts are unit-test fixtures written for these tests (mechanics: whitespace, punctuation,
protection), not dataset samples or claims about any language."""
import re
import time
import unicodedata
from collections import Counter

import pytest

from app.core import details as D
from app.optimizer import rules as R
from app.schemas import OptimizeRequest
from app.services import optimizer as O
from app.tokenizers.base import TokenizerAdapter, TokenizerInfo
from tests.conftest import FakeTokenizer


class WordTokenizer(TokenizerAdapter):
    """One token per word or punctuation mark; whitespace is free."""

    @property
    def info(self):
        return TokenizerInfo("fake_words", "test", "0", "baseline")

    def encode(self, text):
        return list(range(len(re.findall(r"\w+|[^\w\s]", text))))

    def pieces(self, text):
        return re.findall(r"\w+|[^\w\s]", text)


class PenaltyTokenizer(FakeTokenizer):
    """Bytes, plus 10 tokens for every lone '!': collapsing '!!!' to '!' costs tokens here."""

    @property
    def info(self):
        return TokenizerInfo("fake_penalty", "test", "0", "baseline")

    def encode(self, text):
        return list(text.encode()) + [0] * 10 * len(re.findall(r"(?<!!)!(?!!)", text))


BYTES = [FakeTokenizer()]


def opt(text, language="en", mode="safe", tokenizers=None, terms=(), lists=None):
    toks = tokenizers or BYTES
    req = OptimizeRequest(text=text, language=language, mode=mode,
                          tokenizers=[t.info.name for t in toks], protected_terms=list(terms))
    return O.optimize(req, toks, phrase_lists=lists)


def make_list(*entries, status="reviewed", lang="en"):
    return (R.PhraseList("test-" + lang, lang, status, tuple(R.PhraseEntry(*e) for e in entries)),)


def detail_counts(text, language="en", terms=()):
    lexes = D.active_lexicons(None if language == "auto" else language, text)
    return Counter((d.category, d.value)
                   for d in D.extract_details(text, protected_terms=terms, lexicons=lexes))


# ---------- rules ----------
def test_ws_inline_keeps_indentation_and_newlines():
    src = "a   b\t\tc\n    indented  x"
    assert [(src[e.start:e.end], e.after) for e in R.ws_inline(src)] == [
        ("   ", " "), ("\t\t", " "), ("  ", " ")]


def test_ws_lines():
    src = "  a  \nb\n\n\n\nc  "
    got = [(src[e.start:e.end], e.after) for e in R.ws_lines(src)]
    assert ("  ", "") in got and ("\n\n\n\n", "\n\n") in got and got[-1] == ("  ", "")


def test_punct_repeat():
    src = "Wait!!! Why?? ok,, so... and..... really?!"
    # opt_rules_v2: the extra characters are deleted; the first one stays in place.
    edits = R.punct_repeat(src)
    assert [(src[e.start:e.end], e.after) for e in edits] == [("!!", ""), ("?", ""), (",", ""), ("..", "")]
    assert O._apply(src, edits) == "Wait! Why? ok, so... and... really?!"


def test_invisible_chars_keep_zwj_zwnj():
    assert [e.rule for e in R.invisible_chars("a​b­c")] == ["invisible_chars"] * 2
    assert R.invisible_chars("क्‍ष क्‌ष") == []


def test_duplicate_sentences_rule():
    src = "Send the full report to the team. Send the full report to the team. Thanks."
    assert len(R.duplicate_sentences(src)) == 1
    assert R.duplicate_sentences("Hurry. Hurry.") == []                      # too short
    assert R.duplicate_sentences("Hurry up now. Hurry up.") == []           # not identical
    # opt_rules_v2: repeats are found anywhere, not only back to back
    assert len(R.duplicate_sentences("Send the full report to the team. Wait. "
                                     "Send the full report to the team.")) == 1


def test_phrase_edits():
    lists = make_list(("could you please", "", True, True), ("in order to", "to", False, False))
    src = "Could you please write a poem in order to relax. I asked could you please wait."
    got = [(src[e.start:e.end], e.after) for e in R.phrase_edits(src, list(lists))]
    assert got == [("Could you please w", "W"), ("in order to", "to")]   # mid-sentence skipped
    assert [e.after for e in R.phrase_edits("In order to win.", list(lists))] == ["To"]


def test_shipped_phrase_lists():
    lists = {pl.id: pl for pl in R.load_phrase_lists()}
    assert lists["en"].review_status == "reviewed" and lists["en"].entries      # approved (D64)
    for lang in ("kn", "hi", "ta", "te"):
        assert lists[lang].review_status == "unreviewed" and lists[lang].entries == ()


@pytest.mark.parametrize("body,msg", [
    ("entries: [{pattern: 'kindly', replacement: ''}]", "empty replacement"),
    ("entries: [{pattern: 'so', replacement: 'therefore'}]", "must be shorter"),
    ("review_status: approved\nentries: []", "bad review_status"),
])
def test_phrase_list_loader_validation(tmp_path, body, msg):
    status = "" if "review_status" in body else "review_status: reviewed\n"
    (tmp_path / "x.yaml").write_text(f"id: x\nlanguage: en\n{status}{body}\n", encoding="utf-8")
    with pytest.raises(ValueError, match=msg):
        R.load_phrase_lists.__wrapped__(tmp_path)


# ---------- pipeline: acceptance policy ----------
def test_english_safe_optimization():
    text = "Please   summarise this report!!!   Do not include names.  Deadline: 12 Jan 2026."
    r = opt(text)
    assert r.changed and r.optimized == ("Please summarise this report! Do not include names. "
                                         "Deadline: 12 Jan 2026.")
    assert r.meaning_check.status == "preserved" and not r.requires_review
    tc = r.token_counts[0]
    assert tc.after < tc.before and tc.saved == tc.before - tc.after
    assert all(a.meaning_status == "preserved" and a.token_delta["fake_bytes"] < 0 for a in r.accepted)
    assert sum(a.token_delta["fake_bytes"] for a in r.accepted) == -tc.saved


def test_no_eligible_edit_returns_original_exactly():
    text = unicodedata.normalize("NFD", "Café menu, please.")       # NFD input, nothing to fix
    r = opt(text)
    assert not r.changed and r.optimized == text and r.optimized is r.original or r.optimized == text
    assert r.accepted == [] and any("unchanged" in w for w in r.warnings)
    assert r.token_counts[0].saved == 0


def test_zero_saving_edit_rejected():
    r = opt("a   b", tokenizers=[WordTokenizer()])
    assert not r.changed and r.optimized == "a   b"
    assert [(x.stage, x.reason) for x in r.rejected] == [("tokens", "no token saving")]


def test_edit_increasing_any_tokenizer_rejected():
    r = opt("Stop!!! now", tokenizers=[FakeTokenizer(), PenaltyTokenizer()])
    rej = [x for x in r.rejected if x.rule == "punct_repeat"]
    assert rej and rej[0].stage == "tokens" and "fake_penalty (+" in rej[0].reason
    assert "!!!" in r.optimized


def test_multi_tokenizer_accepts_when_one_saves_and_none_increase():
    r = opt("go   now!!!", tokenizers=[FakeTokenizer(), WordTokenizer()])
    assert r.optimized == "go now!"
    ws = next(a for a in r.accepted if a.rule == "ws_inline")
    assert ws.token_delta == {"fake_bytes": -2, "fake_words": 0}
    assert all(t.after <= t.before for t in r.token_counts)


# ---------- protection ----------
@pytest.mark.parametrize("text,terms,category", [
    ('Say "wow!!!" now', (), "quoted"),
    ("Run `a  b` now", (), "code"),
    ("Open https://x.test/a,,b now", (), "url"),
    ("Meet 12  Jan  2026 there", (), "datetime"),
    ("Ask Bengaluru   One now", ("Bengaluru   One",), "protected_term"),
])
def test_edits_inside_protected_details_rejected(text, terms, category):
    r = opt(text, terms=terms)
    assert any(x.stage == "protected" and category in x.reason for x in r.rejected)
    assert detail_counts(r.optimized, terms=terms) == detail_counts(text, terms=terms)


def test_all_categories_preserved_in_rich_prompt():
    text = ("Please   pay ₹1,00,000 to raj@example.test before 12 Jan 2026 at 5 pm!!!   "
            "Do not   use https://pay.example.test/a?id=7 ,, run `pip  install x` and reply "
            '"yes  sir".   Keep Bengaluru One informed....')
    terms = ("Bengaluru One",)
    r = opt(text, terms=terms)
    assert r.changed and r.meaning_check.status == "preserved"
    assert detail_counts(r.optimized, terms=terms) == detail_counts(text, terms=terms)
    assert "`pip  install x`" in r.optimized and '"yes  sir"' in r.optimized   # untouched inside


def test_gate_rejects_edit_that_changes_a_detail():
    r = opt("Pay Rs.   500 now.")          # collapsing spaces would turn number 500 into money
    assert not r.changed and r.optimized == "Pay Rs.   500 now."
    rej = next(x for x in r.rejected if x.rule == "ws_inline")
    assert rej.stage == "meaning" and "changed" in rej.reason


def test_gate_rejects_phrase_that_adds_a_detail():
    lists = make_list(("a couple of", "2", False, False))
    r = opt("Bring a couple of chairs.", mode="balanced", lists=lists)
    assert not r.changed
    assert any(x.stage == "meaning" and "added number '2'" in x.reason for x in r.rejected)


def test_every_proposed_edit_is_accounted_for():
    text = "Hi   there!!!  Send the full report to the team now. Send the full report to the team now."
    proposed = len(R.safe_edits(D.nfc(text))) + len(R.duplicate_sentences(D.nfc(text)))
    r = opt(text)
    assert len(r.accepted) + len(r.suggestions) + len(r.rejected) == proposed


# ---------- review-only outcomes ----------
def test_at_risk_edit_becomes_suggestion_not_applied():
    # A word-changing edit from a (test-fixture) APPROVED Kannada list: the Kannada negation and
    # marker lists are pending review, so the gate says at_risk and the edit is only suggested.
    lists = make_list(("ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಸಾರಾಂಶ", "ಸಾರಾಂಶ", False, False), lang="kn")
    r = opt("ವರದಿಯ   ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಸಾರಾಂಶ ಕಳುಹಿಸಿ!!!", language="kn", mode="balanced", lists=lists)
    assert r.optimized == "ವರದಿಯ ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಸಾರಾಂಶ ಕಳುಹಿಸಿ!"       # formatting applied, wording not
    s = r.suggestions[0]
    assert (s.kind, s.meaning_status, s.requires_review, s.before) == ("at_risk_edit", "at_risk", True, "ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಸಾರಾಂಶ")
    assert s.token_delta["fake_bytes"] < 0 and any("kn-Knda" in x for x in s.risks)
    assert s.approval_required and s.risk == "wording" and s.language == "kn"
    assert r.requires_review and r.meaning_check.status == "preserved"


def test_english_rules_never_apply_to_indic_text():
    # D59: an English phrase rule is not applied (or suggested) inside Kannada/Hindi/Tamil/Telugu text.
    lists = make_list(("in order to", "to", False, False))
    for lang in ("kn", "hi", "ta", "te", "auto"):
        r = opt("ವರದಿ in order to ಕಳುಹಿಸಿ.", language=lang, mode="aggressive", lists=lists)
        assert not any(x.rule.startswith("phrase:") for x in r.accepted + r.suggestions + r.rejected)
    r = opt("Read it in order to learn.", language="en", mode="balanced", lists=lists)
    assert r.optimized == "Read it to learn."


def test_formatting_only_edits_apply_in_indic_text():
    # rules_v3: when no letter, mark or digit changes, unreviewed negation lists are no risk.
    r = opt("ದಯವಿಟ್ಟು   ಈ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ!!!", language="kn")
    assert r.optimized == "ದಯವಿಟ್ಟು ಈ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ!" and not r.suggestions
    assert r.meaning_check.status == "preserved"


def test_shrink_risk_becomes_suggestion():
    lists = make_list(("could you please do me a favour and", "", True, True))
    r = opt("Could you please do me a favour and help?", mode="balanced", lists=lists)
    assert not r.changed and r.suggestions[0].kind == "at_risk_edit"
    assert any("less than 50%" in x for x in r.suggestions[0].risks)


def test_duplicate_sentence_is_suggestion_only():
    # rules_v5 treats "today" as a date, so this test uses a repeat without critical details.
    text = "Send the full report to the team by email. Send the full report to the team by email."
    r = opt(text)
    assert r.optimized == text and not r.changed
    s = r.suggestions[0]
    assert s.kind == "duplicate_sentence" and s.requires_review
    # Removing one of two sentences halves the text, so Feature 5 reports at_risk (shrink).
    assert s.meaning_status == "at_risk" and any("less than 50%" in x for x in s.risks)
    assert s.token_delta["fake_bytes"] < 0 and r.requires_review


def test_duplicate_sentence_suggestion_preserved_when_text_is_long():
    text = ("Send the full report to the team by email. Send the full report to the team by email. "
            "Include the summary, the charts and the open questions from Monday's review.")
    s = opt(text).suggestions[0]
    assert s.kind == "duplicate_sentence" and s.meaning_status == "preserved" and s.risks == []


def test_duplicate_sentence_with_relative_day_names_the_date():
    # rules_v5: "today" is a critical date; removing a repeat that holds it stays a reviewed
    # suggestion that names the date, like a repeated number (opt_rules_v2).
    text = "Send the full report to the team today. Send the full report to the team today."
    r = opt(text)
    assert r.optimized == text and not r.changed
    s = r.suggestions[0]
    assert s.kind == "duplicate_sentence" and s.requires_review and s.meaning_status == "at_risk"
    assert any("datetime 'today'" in x for x in s.risks)


def test_duplicate_sentence_with_number_is_reviewed_suggestion():
    # Safe mode: removing one copy lowers the number's count but the value stays in the first
    # copy, so the repeat is offered for review (at_risk, detail named), never applied.
    text = "Pay 5 people now please today. Pay 5 people now please today."
    r = opt(text, mode="safe")
    assert not r.changed and r.optimized == text
    s = r.suggestions[0]
    assert (s.kind, s.meaning_status) == ("duplicate_sentence", "at_risk")
    assert any("number '5'" in x for x in s.risks)


def test_balanced_removes_repeat_with_details_when_every_value_survives():
    # opt_rules_v4 (D64): balanced removes the repeat; every value stays in the first copy; the
    # result is at_risk (never 'preserved') and names what was repeated.
    text = "Pay 5 people now please today. Pay 5 people now please today."
    r = opt(text, mode="balanced")
    assert r.changed and r.optimized == "Pay 5 people now please today."
    assert r.meaning_check.status == "at_risk"
    assert any("Repeated copies removed" in x and "number '5'" in x for x in r.meaning_check.risks)
    assert all(f.candidate_count >= 1 for f in r.meaning_check.findings)


def test_balanced_never_removes_a_near_repeat_that_differs_in_a_detail():
    text = "Pay 5 people now please today. Pay 6 people now please today."
    r = opt(text, mode="balanced")
    assert "Pay 5" in r.optimized and "Pay 6" in r.optimized


# ---------- modes ----------
def test_balanced_applies_approved_english_list():
    # D64: the shipped English list is approved, so balanced mode rewrites wording.
    text = "In order to   win, practise."
    r = opt(text, mode="balanced")
    assert r.optimized == "To win, practise."
    en = next(p for p in r.phrase_lists if p.id == "en")
    assert en.review_status == "reviewed" and en.applied
    assert not any("No approved wording rule" in w for w in r.warnings)
    assert opt(text, mode="safe").optimized == "In order to win, practise."   # safe: formatting only


def test_balanced_indic_text_gets_no_english_wording_rules():
    r = opt("ಸಭೆ in order to ನಾಳೆ ಇದೆ.", language="kn", mode="balanced")
    assert "in order to" in r.optimized


def test_balanced_applies_reviewed_list_but_safe_does_not():
    lists = make_list(("in order to", "to", False, False))
    assert opt("Practise in order to win.", mode="balanced", lists=lists).optimized == "Practise to win."
    assert opt("Practise in order to win.", mode="safe", lists=lists).optimized == "Practise in order to win."


def test_unreviewed_list_never_applied():
    lists = make_list(("in order to", "to", False, False), status="unreviewed")
    r = opt("Practise in order to win.", mode="balanced", lists=lists)
    assert not r.changed and not r.phrase_lists[0].applied


def test_aggressive_mode_english_has_no_script_suggestions():
    # Feature 6 now provides script variants; English text has none (see test_transliteration.py).
    r = opt("go   now", mode="aggressive")
    assert any("need Kannada, Hindi, Tamil or Telugu" in w for w in r.warnings)
    assert not any(s.kind == "script_variant" for s in r.suggestions)


# ---------- determinism ----------
def test_deterministic_and_idempotent():
    text = "Hi   there!!!\n\n\n\nSend 3 files.  Thanks...."
    a, b = opt(text), opt(text)
    assert a.model_dump() == b.model_dump()
    again = opt(a.optimized)
    assert not again.changed and again.optimized == a.optimized


# ---------- languages ----------
LANG_CASES = [
    ("en", "Please   summarise this report!!!   Do not include names.", "not"),
    ("kn", "ದಯವಿಟ್ಟು   ಈ ವರದಿಯನ್ನು ಸಂಕ್ಷೇಪಿಸಿ!!!   ಹೆಸರುಗಳನ್ನು ಸೇರಿಸಬೇಡಿ.", "kn:beda"),
    ("hi", "कृपया   इस रिपोर्ट का सारांश दें!!!   नाम शामिल न करें।", "hi:na"),
    ("ta", "தயவுசெய்து   இந்த அறிக்கையைச் சுருக்கவும்!!!   பெயர்களைச் சேர்க்க வேண்டாம்.", "ta:vendam"),
    ("te", "దయచేసి   ఈ నివేదికను సంగ్రహించండి!!!   పేర్లు చేర్చవద్దు.", "te:vaddu"),
    ("kn", "dayavittu   ee report summary kodi!!!   naanu baruvudilla", "kn:illa"),   # Romanized
    ("hi", "kripya   is report ka summary do!!!   naam mat daalo.", "hi:mat"),           # Romanized
    ("kn", "Meeting   ನಾಳೆ 10 am ಗೆ!!!   ಮರೆಯಬೇಡಿ", "kn:beda"),                         # code-mixed
]


@pytest.mark.parametrize("language,text,negation", LANG_CASES)
def test_languages(language, text, negation):
    r = opt(text, language=language)
    assert r.changed and "   " not in r.optimized                       # whitespace applied
    assert detail_counts(r.optimized, language) == detail_counts(text, language)
    assert ("negation", negation) in detail_counts(r.optimized, language)
    assert r.meaning_check.status == "preserved"
    # opt_rules_v2 / rules_v3: repeated punctuation is formatting only (no word changes), so it
    # is applied in every language, also where the negation lists are unreviewed.
    assert "!!!" not in r.optimized and not r.suggestions


# ---------- limits ----------
def test_edit_limit(monkeypatch):
    monkeypatch.setattr(O, "MAX_EVALUATED_EDITS", 3)
    r = opt("a  b  c  d  e  f")
    assert len(r.accepted) == 3 and sum(x.stage == "limit" for x in r.rejected) == 2


def test_max_length_input_is_fast_enough():
    text = ("Word  word, more   text here!!! " * 700)[:20_000]
    start = time.perf_counter()
    r = opt(text)
    elapsed = time.perf_counter() - start
    assert r.changed and len(r.accepted) <= O.MAX_EVALUATED_EDITS
    assert elapsed < 30, f"took {elapsed:.1f}s"


# ---------- real tokenizers (skip when tiktoken encodings are unavailable) ----------
def test_real_tiktoken_tokenizers():
    pytest.importorskip("tiktoken")
    from app.tokenizers import TokenizerUnavailable, get_tokenizer

    try:
        toks = [get_tokenizer("cl100k_base"), get_tokenizer("o200k_base")]
        for t in toks:
            t.encode("warm-up")
    except TokenizerUnavailable as exc:
        pytest.skip(f"encoding files unavailable: {exc}")
    r = opt("Please   summarise this report!!!   Do not include names.", tokenizers=toks)
    assert all(t.after <= t.before for t in r.token_counts)
    assert all(t.status == "exact" for t in r.token_counts)


# ---------- 200-edit boundary (team decision 2026-11-20) ----------
def _runs(n):
    """Text with exactly n double-space runs → n ws_inline edits, each saving 1 byte-token."""
    return "  ".join(["a"] * (n + 1))


def test_limit_is_200():
    assert O.MAX_EVALUATED_EDITS == 200


@pytest.mark.parametrize("n", [199, 200])
def test_at_or_below_limit_all_evaluated_no_warning(n):
    r = opt(_runs(n))
    assert len(r.accepted) == n and not any(x.stage == "limit" for x in r.rejected)
    assert not any("Edit limit reached" in w for w in r.warnings)
    assert r.optimized == " ".join(["a"] * (n + 1))


def test_over_limit_reports_every_unevaluated_edit_and_warns():
    r = opt(_runs(205))
    limited = [x for x in r.rejected if x.stage == "limit"]
    assert len(r.accepted) == 200 and len(limited) == 5
    assert all(x.token_delta is None and "limit of 200" in x.reason for x in limited)
    # Never silently omitted: every proposed edit is accounted for.
    assert len(r.accepted) + len(r.suggestions) + len(r.rejected) == 205
    warning = next(w for w in r.warnings if "Edit limit reached" in w)
    assert "200 edits were evaluated and 5 were not" in warning
    # The first 200 (left to right) are the ones applied.
    assert max(a.start for a in r.accepted) < min(x.start for x in limited)


def test_limit_behaviour_is_deterministic():
    a, b = opt(_runs(230)), opt(_runs(230))
    assert a.model_dump() == b.model_dump()
    again = opt(a.optimized)            # a second pass continues with the remaining edits
    assert len(again.accepted) == 30 and not any(x.stage == "limit" for x in again.rejected)
