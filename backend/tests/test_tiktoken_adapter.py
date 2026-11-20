"""Runs only where tiktoken is installed and its encoding files can be loaded."""
import pytest

pytest.importorskip("tiktoken")

from app.tokenizers import TokenizerUnavailable, get_tokenizer  # noqa: E402


@pytest.fixture(params=["cl100k_base", "o200k_base"])
def tok(request):
    t = get_tokenizer(request.param)
    try:
        t.encode("warm-up")
    except TokenizerUnavailable as exc:
        pytest.skip(f"encoding files unavailable: {exc}")
    return t


def test_identity(tok):
    assert tok.info.library == "tiktoken"
    assert tok.info.version not in ("", None)
    assert tok.count_status == "exact"


def test_round_trip_and_pieces(tok):
    text = "ನಮಸ್ಕಾರ hello"
    ids = tok.encode(text)
    assert tok._enc.decode(ids) == text
    assert len(tok.pieces(text)) == len(ids)


def test_special_token_text_is_counted_not_rejected(tok):
    assert tok.count("<|endoftext|>") > 1
