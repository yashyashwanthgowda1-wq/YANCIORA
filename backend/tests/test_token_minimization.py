"""Token minimization (opt_rules_v2 + meaning check rules_v3), milestone tests.

Logic tests use the byte-counting FakeTokenizer; a separate section uses the real tiktoken
encodings and is skipped when they are unavailable. Indic sample sentences are developer-written
test inputs (not reviewed by native speakers); they exercise formatting and duplicate handling,
not wording changes.
"""
from __future__ import annotations

import time
from collections import Counter

import pytest
from pydantic import ValidationError

from app.core import details as D
from app.optimizer import rules as R
from app.schemas import MeaningCheckRequest, OptimizeRequest
from app.services import meaning
from app.services import optimizer as O
from app.tokenizers.base import TokenizerAdapter, TokenizerInfo
from tests.conftest import FakeTokenizer

BYTES = [FakeTokenizer()]

# One developer-written sentence per language, with a negation, a number and a date/time where
# the script allows it. The noisy forms add only formatting noise and an exact repeat.
SENTENCES = {
    "en": "Do not send the report before 5 pm on 12 March.",
    "kn": "ವರದಿಯನ್ನು 5 ಗಂಟೆಗೆ ಮೊದಲು ಕಳುಹಿಸಬೇಡಿ.",
    "hi": "रिपोर्ट 5 बजे से पहले मत भेजो।",
    "ta": "அறிக்கையை 5 மணிக்கு முன் அனுப்ப வேண்டாம்.",
    "te": "నివేదికను 5 గంటలకు ముందు పంపవద్దు.",
}
INSTRUCTION = {   # a detail-free instruction to repeat
    "en": "Please answer in short points.",
    "kn": "ದಯವಿಟ್ಟು ಚಿಕ್ಕ ಅಂಶಗಳಲ್ಲಿ ಉತ್ತರಿಸಿ.",
    "hi": "कृपया छोटे बिंदुओं में उत्तर दें।",
    "ta": "தயவுசெய்து சுருக்கமான புள்ளிகளில் பதில் சொல்லுங்கள்.",
    "te": "దయచేసి చిన్న పాయింట్లలో సమాధానం ఇవ్వండి.",
}


def opt(text, language="en", mode="safe", tokenizers=None, terms=(), lists=None):
    toks = tokenizers or BYTES
    req = OptimizeRequest(text=text, language=language, mode=mode,
                          tokenizers=[t.info.name for t in toks], protected_terms=list(terms))
    return O.optimize(req, toks, phrase_lists=lists)


def make_list(*entries, status="reviewed", lang="en"):
    return (R.PhraseList("test-" + lang, lang, status, tuple(R.PhraseEntry(*e) for e in entries)),)


def details(text, language="en"):
    lexes = D.active_lexicons(None if language == "auto" else language, text)
    return Counter((d.category, d.value) for d in D.extract_details(text, lexicons=lexes))


def noisy(lang):
    s, i = SENTENCES[lang], INSTRUCTION[lang]
    return f"  {i}   {s}!!!\n\n\n\n----------\n{i}  \n"


# ---------- all five languages, native script ----------
@pytest.mark.parametrize("lang", list(SENTENCES))
def test_safe_mode_formatting_in_every_language(lang):
    r = opt(noisy(lang), language=lang)
    assert r.changed and r.mode == "safe"
    assert "   " not in r.optimized and "!!!" not in r.optimized and "----------" not in r.optimized
    assert "---" in r.optimized                                        # separator shortened, kept
    assert r.optimized.count(INSTRUCTION[lang]) == 2                   # safe never removes a repeat
    assert [s.kind for s in r.suggestions] == ["duplicate_sentence"]
    assert details(r.optimized, lang) == details(noisy(lang), lang)   # every detail kept
    assert r.meaning_check.status == "preserved"


@pytest.mark.parametrize("lang", list(SENTENCES))
def test_balanced_mode_removes_exact_repeat_in_every_language(lang):
    r = opt(noisy(lang), language=lang, mode="balanced")
    assert r.optimized.count(INSTRUCTION[lang]) == 1 and SENTENCES[lang] in r.optimized
    assert any(a.rule == "duplicate_sentence" for a in r.accepted)
    assert details(r.optimized, lang) == details(noisy(lang), lang)
    tc = r.token_counts[0]
    assert tc.after < tc.before and tc.saved == tc.before - tc.after
    assert r.meaning_check.status in ("preserved", "at_risk")
    assert r.meaning_check.status != "changed"


@pytest.mark.parametrize("lang", list(SENTENCES))
def test_repeat_holding_a_detail_is_only_suggested(lang):
    text = f"{SENTENCES[lang]} {SENTENCES[lang]}"                     # repeat holds number + negation
    r = opt(text, language=lang, mode="balanced")
    assert not r.changed and r.optimized == text
    assert [s.kind for s in r.suggestions] == ["duplicate_sentence"]


# ---------- Romanized and code-mixed (needs the language for Romanized negations) ----------
@pytest.mark.parametrize("lang,text,neg", [
    ("kn", "dayavittu   report kalisabedi!!!   naanu baruvudilla", ("negation", "kn:illa")),
    ("hi", "kripya   report mat bhejo!!!   abhi nahi", ("negation", "hi:mat")),
    ("kn", "Meeting   ನಾಳೆ 10 am ಗೆ!!!   ಮರೆಯಬೇಡಿ", ("negation", "kn:beda")),
    ("hi", "Kal   meeting hai,,   please time pe aana!!!", ("number", "")),
])
def test_romanized_and_code_mixed(lang, text, neg):
    r = opt(text, language=lang)
    assert r.changed and "   " not in r.optimized and "!!!" not in r.optimized
    assert details(r.optimized, lang) == details(text, lang)
    if neg[1]:
        assert neg in details(r.optimized, lang)


def test_romanized_without_language_is_flagged():
    r = opt("report mat bhejo!!!", language="auto")
    assert any("Romanized" in w for w in r.warnings)


# ---------- negation, numbers, dates, conditions, constraints, questions, names ----------
@pytest.mark.parametrize("original,candidate,category", [
    ("Do not pay the bill.", "Do pay the bill.", "negation"),
    ("Pay ₹500 by 5 pm.", "Pay ₹50 by 5 pm.", "money"),
    ("Meet on 12 March.", "Meet on 13 March.", "datetime"),
    ("Send it if the client agrees.", "Send it, the client agrees.", "condition"),
    ("Send it unless the client objects.", "Send it if the client objects.", "condition"),
    ("You must reply within a day.", "You reply within a day.", "constraint"),
    ("Use only English words.", "Use English words.", "constraint"),
    ("Write at least three points.", "Write three points.", "constraint"),
    ("Can you summarise this?", "Can you summarise this.", "question"),
    ("Email the file to Priya today.", "Email the file today.", "entity"),
    ("Upload it to AWS tonight.", "Upload it tonight.", "entity"),
])
def test_meaning_check_catches_critical_changes(original, candidate, category):
    r = meaning.check(MeaningCheckRequest(original=original, candidate=candidate, language="en"))
    assert r.status == "changed"
    assert any(f.category == category and f.state != "kept" for f in r.findings)


@pytest.mark.parametrize("original,candidate", [
    ("Send it in the event that the client agrees.", "Send it if the client agrees."),   # same condition
    ("Write a minimum of three points.", "Write at least three points."),               # same constraint
    ("Why???  Tell me.", "Why? Tell me."),                                                # one question
    ("Email Priya.", "Email   Priya."),
])
def test_meaning_check_accepts_equivalent_wording(original, candidate):
    r = meaning.check(MeaningCheckRequest(original=original, candidate=candidate, language="en"))
    assert r.status == "preserved", r.findings


def test_entity_heuristic_skips_sentence_starts_and_lists():
    found = details("Please email Priya. Then call Ravi.\n1. Write notes\n- Read it", "en")
    assert ("entity", "Priya") in found and ("entity", "Ravi") in found
    assert not any(c == "entity" and v in ("Please", "Then", "Write", "Read") for c, v in found)


def test_conditions_and_constraints_protect_against_phrase_edits():
    lists = make_list(("only if", "if", False, False), ("you must", "", True, True))
    r = opt("Reply only if asked. You must cite sources.", mode="balanced", lists=lists)
    assert not r.changed                                     # both rejected by the meaning gate
    assert {x.stage for x in r.rejected} == {"meaning"}


def test_phrase_may_reword_condition_with_same_meaning():
    lists = make_list(("in the event that", "if", False, False))
    r = opt("Call me in the event that the train is late.", mode="balanced", lists=lists)
    assert r.optimized == "Call me if the train is late." and r.meaning_check.status == "preserved"


def test_question_mark_kept_when_shortening_runs():
    r = opt("Is it ready???  Tell me!!!")
    assert r.optimized == "Is it ready? Tell me!"
    assert details(r.optimized)[("question", "?")] == 1


def test_numbers_dates_and_names_untouched():
    text = "Book  Ravi a seat for ₹1,200 on 2026-12-01 at 10:30 am!!!"
    r = opt(text)
    assert r.optimized == "Book Ravi a seat for ₹1,200 on 2026-12-01 at 10:30 am!"
    assert details(r.optimized) == details(text)


# ---------- duplicate instructions ----------
def test_repeated_instruction_non_adjacent_and_case_insensitive():
    text = "Answer in Kannada only please. Summarise the article. answer in kannada only please."
    r = opt(text, mode="balanced")
    # the repeat contains the constraint word "only", a critical detail → suggestion only
    assert not r.changed and r.suggestions[0].kind == "duplicate_sentence"
    text2 = "Keep the tone friendly. Summarise the article. keep the tone friendly."
    r2 = opt(text2, mode="balanced")
    assert r2.optimized == "Keep the tone friendly. Summarise the article."


def test_repeated_unpunctuated_lines():
    text = "Use simple words\nList three ideas\nUse simple words\n"
    r = opt(text, mode="balanced")
    assert r.optimized.count("Use simple words") == 1 and "List three ideas" in r.optimized


def test_intentional_repetition_is_disclosed_in_balanced_policy():
    r = opt("Say hello to them. Say hello to them.", mode="balanced")
    assert "exact repeats" in r.mode_policy and r.changed


# ---------- separators ----------
@pytest.mark.parametrize("text,changed", [
    ("Title\n==========\nBody", True), ("a\n──────────\nb", True), ("|------|-----|", True),
    ("#### Heading", False), ("Rating: *****", False), ("Name: __________", False), ("~~~~", False),
])
def test_separator_runs(text, changed):
    import re

    r = opt(text)
    assert r.changed is changed
    if changed:
        runs = [m.group(0) for m in re.finditer(r"([-=─])\1*", r.optimized)]
        assert runs and all(len(x) == 3 for x in runs if len(x) >= 3)   # shortened to exactly 3
        assert re.sub(r"[-=─]", "", r.optimized) == re.sub(r"[-=─]", "", text)   # nothing else changed
    else:
        assert r.optimized == text


# ---------- edge cases ----------
def test_empty_and_blank_prompts_rejected():
    for t in ("", "   ", "\n\t"):
        with pytest.raises(ValidationError):
            OptimizeRequest(text=t)


@pytest.mark.parametrize("text", ["Hi", "?", "ನಮಸ್ಕಾರ", "नमस्ते", "5"])
def test_very_short_prompts_unchanged(text):
    r = opt(text, language="auto")
    assert r.optimized == text and not r.changed and r.chars_saved == 0


@pytest.mark.parametrize("lang", list(SENTENCES))
def test_clean_text_is_returned_exactly(lang):
    text = f"{INSTRUCTION[lang]} {SENTENCES[lang]}"
    for mode in ("safe", "balanced"):
        r = opt(text, language=lang, mode=mode)
        assert r.optimized == text and not r.changed and not r.accepted


def test_long_prompt():
    block = "Summarise   the section below!!!\n\n\n\nThe report covers sales.  "
    text = block * 400                                                    # ~25k characters
    text = text[:19_000]
    t0 = time.perf_counter()
    r = opt(text, mode="balanced")
    assert time.perf_counter() - t0 < 60
    assert r.changed and r.token_counts[0].after < r.token_counts[0].before
    assert r.meaning_check.status != "changed"


class CostlyBang(TokenizerAdapter):
    """Charges extra for a single '!' so shortening '!!!' would INCREASE tokens."""

    @property
    def info(self) -> TokenizerInfo:
        return TokenizerInfo("costly_bang", "test", "0", "baseline")

    def encode(self, text: str) -> list[int]:
        out = list(text.encode("utf-8"))
        return out + [0] * (10 * len(__import__("re").findall(r"(?<!!)!(?!!)", text)))

    def pieces(self, text: str) -> list[str]:
        return ["x"] * len(self.encode(text))


def test_edit_that_increases_tokens_is_rejected():
    r = opt("Stop!!!", tokenizers=[CostlyBang()])
    assert not r.changed and r.optimized == "Stop!!!"
    assert any(x.stage == "tokens" and "increases tokens" in x.reason for x in r.rejected)


def test_edit_must_not_increase_under_any_selected_tokenizer():
    r = opt("Stop!!!", tokenizers=[FakeTokenizer(), CostlyBang()])
    assert not r.changed and r.token_counts[0].saved == 0 and r.token_counts[1].saved == 0


# ---------- measurement ----------
def test_measurements_are_consistent():
    text = "Please   send  ₹500 today!!!"
    r = opt(text)
    assert r.original_chars == len(text) and r.optimized_chars == len(r.optimized)
    assert r.chars_saved == len(text) - len(r.optimized) > 0
    tc = r.token_counts[0]
    tok = BYTES[0]
    assert tc.before == tok.count(text) and tc.after == tok.count(r.optimized)   # same encoding
    assert tc.saved_pct == round(100 * (tc.before - tc.after) / tc.before, 2)
    assert r.script == "Latn" and r.language == "en" and r.mode == "safe"
    assert any("not provider billing" in w for w in r.warnings)


def test_mode_policies_differ():
    pol = {m: opt("Hi there.", mode=m).mode_policy for m in ("safe", "balanced", "aggressive")}
    assert pol["safe"].startswith("Safe") and pol["balanced"].startswith("Balanced")
    assert "approval" in pol["aggressive"]


# ---------- aggressive: unreviewed wording is suggested, never applied ----------
def test_aggressive_suggests_unreviewed_phrases_only():
    lists = make_list(("in order to", "to", False, False), status="developer_curated")
    text = "Read it in order to learn."
    bal = opt(text, mode="balanced", lists=lists)
    assert not bal.changed and not bal.suggestions                    # unreviewed: not even suggested
    agg = opt(text, mode="aggressive", lists=lists)
    assert not agg.changed and agg.optimized == text
    s = [x for x in agg.suggestions if x.kind == "unreviewed_phrase"]
    assert s and s[0].before == "in order to" and s[0].after == "to"


def test_shipped_english_list_is_not_active_until_reviewed():
    lists = R.load_phrase_lists()
    en = next(pl for pl in lists if pl.id == "en")
    assert en.review_status != "reviewed"
    r = opt("Could you please summarise this in order to save time.", mode="balanced")
    assert not any(a.rule.startswith("phrase:") for a in r.accepted)


# ---------- real tokenizers (skipped when tiktoken encodings are unavailable) ----------
def _real():
    try:
        from app.tokenizers import get_tokenizer
        toks = [get_tokenizer("cl100k_base"), get_tokenizer("o200k_base")]
        toks[0].count("x")
        return toks
    except Exception:  # noqa: BLE001
        pytest.skip("tiktoken encodings unavailable")


@pytest.mark.parametrize("lang", list(SENTENCES))
def test_real_tokenizers_same_encoding_before_after(lang):
    toks = _real()
    r = opt(noisy(lang), language=lang, mode="balanced", tokenizers=toks)
    assert [t.tokenizer.name for t in r.token_counts] == ["cl100k_base", "o200k_base"]
    for t, tok in zip(r.token_counts, toks):
        assert t.before == tok.count(noisy(lang)) and t.after == tok.count(r.optimized)
        assert t.after <= t.before
    assert sum(t.saved for t in r.token_counts) > 0


@pytest.mark.parametrize("text,lang,expected", [
    ("कम  से  कम तीन उदाहरण दो।", "hi", "कम से कम तीन उदाहरण दो।"),          # multi-word constraint
    ("ಶ್ರೀ   ರಮೇಶ್ ಅವರಿಗೆ ಕರೆ ಮಾಡಿ.", "kn", "ಶ್ರೀ ರಮೇಶ್ ಅವರಿಗೆ ಕರೆ ಮಾಡಿ."),  # title + name
    ("Write at   least three points.", "en", "Write at least three points."),   # English constraint
])
def test_spacing_fixed_inside_flexible_spans(text, lang, expected):
    r = opt(text, language=lang)
    assert r.optimized == expected and r.meaning_check.status == "preserved"


def test_spacing_inside_money_stays_protected():
    r = opt("Pay Rs.   500 now.")
    assert r.optimized == "Pay Rs.   500 now."


@pytest.mark.parametrize("text,lang,expected", [
    ("ಒಂದು​ ಮನೆ ಕೊಡಿ.", "kn", "ಒಂದು ಮನೆ ಕೊಡಿ."),          # number word
    ("Use the AI​ tool.", "en", "Use the AI tool."),         # acronym (entity)
])
def test_invisible_char_inside_detected_word_is_removed(text, lang, expected):
    r = opt(text, language=lang)
    assert r.optimized == expected and r.meaning_check.status == "preserved"


def test_invisible_char_inside_quote_stays():
    r = opt('Say "hel​lo" now.')
    assert "​" in r.optimized
