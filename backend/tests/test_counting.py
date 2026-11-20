import pytest
from pydantic import ValidationError

from app.core.metrics import fertility, relative_ratio, summarize
from app.schemas import CompareRequest, TokenizeRequest
from app.services.counting import UNALIGNED_WARNING, compare, tokenize
from app.tokenizers import UnknownTokenizer, available_tokenizers, get_tokenizer


# ---- metrics ----
def test_fertility_and_ratio():
    assert fertility(10, 4) == 2.5
    assert fertility(3, 0) is None
    assert relative_ratio(5.0, 2.0) == 2.5
    assert relative_ratio(5.0, 0) is None
    assert relative_ratio(None, 2.0) is None


def test_summarize():
    s = summarize([1.0, 2.0, 3.0])
    assert (s.n, s.mean, s.median) == (3, 2.0, 2.0)
    assert s.ci95_low is None  # n < 30: no CI
    big = summarize([float(i % 5) for i in range(40)])
    assert big.ci95_low is not None and big.ci95_low < big.mean < big.ci95_high
    assert summarize([]).n == 0


# ---- tokenize ----
def test_tokenize_reports_identity_and_policy(fake_tok):
    r = tokenize(TokenizeRequest(text="  ನಮಸ್ಕಾರ   ಗೆಳೆಯ ", tokenizer="fake_bytes"), fake_tok)
    assert r.tokenizer.name == "fake_bytes" and r.tokenizer.version == "0"
    assert r.status == "exact"
    assert r.script == "Knda" and r.language == "kn"
    assert r.word_count == 2
    assert r.token_count == len("ನಮಸ್ಕಾರ ಗೆಳೆಯ".encode())  # counted on normalized text
    assert r.tokens_per_word == r.token_count / 2
    assert r.normalization == "nfc_ws_v1" and r.pieces is None


def test_tokenize_latin_language_not_guessed(fake_tok):
    r = tokenize(TokenizeRequest(text="namaskara", tokenizer="x"), fake_tok)
    assert r.script == "Latn" and r.language is None
    r2 = tokenize(TokenizeRequest(text="namaskara", tokenizer="x", language="kn"), fake_tok)
    assert r2.language == "kn"


def test_tokenize_pieces(fake_tok):
    r = tokenize(TokenizeRequest(text="hi", tokenizer="x", include_pieces=True), fake_tok)
    assert r.pieces == ["h", "i"]


def test_tokenize_rejects_blank_and_oversized():
    with pytest.raises(ValidationError):
        TokenizeRequest(text="   ", tokenizer="x")
    with pytest.raises(ValidationError):
        TokenizeRequest(text="a" * 20_001, tokenizer="x")


# ---- compare ----
def _variants():
    return [
        {"language": "en", "script": "Latn", "variant_type": "original", "text": "Good morning friend"},
        {"language": "kn", "script": "Knda", "variant_type": "translation", "text": "ಶುಭೋದಯ ಗೆಳೆಯ"},
    ]


def test_compare_ratios_against_reference(fake_tok):
    r = compare(CompareRequest(tokenizer="x", variants=_variants(), aligned_group_id="g1"), fake_tok)
    assert r.aligned and UNALIGNED_WARNING not in r.warnings
    en, kn = r.rows
    assert en.ratio_vs_reference == 1.0
    assert kn.ratio_vs_reference == pytest.approx(kn.tokens_per_word / en.tokens_per_word)
    assert any("not cost multipliers" in w for w in r.warnings)


def test_compare_unaligned_warns(fake_tok):
    r = compare(CompareRequest(tokenizer="x", variants=_variants()), fake_tok)
    assert not r.aligned and UNALIGNED_WARNING in r.warnings


def test_compare_flags_script_mismatch(fake_tok):
    v = _variants()
    v[1]["script"] = "Latn"
    r = compare(CompareRequest(tokenizer="x", variants=v, aligned_group_id="g"), fake_tok)
    assert any("declared script Latn" in w for w in r.warnings)


def test_compare_reference_out_of_range(fake_tok):
    with pytest.raises(ValueError):
        compare(CompareRequest(tokenizer="x", variants=_variants(), reference_index=5), fake_tok)


def test_compare_needs_two_variants():
    with pytest.raises(ValidationError):
        CompareRequest(tokenizer="x", variants=_variants()[:1])


# ---- registry ----
def test_registry():
    assert {"cl100k_base", "o200k_base"} <= set(available_tokenizers())
    with pytest.raises(UnknownTokenizer):
        get_tokenizer("gpt-unknown")
