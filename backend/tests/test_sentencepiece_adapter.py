"""Unigram adapter: never listed without a trained model; honest status."""
import pytest

from app.tokenizers import registry, sentencepiece_adapter as S
from app.tokenizers.base import TokenizerUnavailable


def test_not_listed_without_model(monkeypatch):
    monkeypatch.delenv(S.ENV_VAR, raising=False)
    assert S.status()["model_configured"] is False and S.status()["available"] is False
    assert S.NAME not in registry.available_tokenizers()


def test_adapter_refuses_without_model(monkeypatch, tmp_path):
    monkeypatch.setenv(S.ENV_VAR, str(tmp_path / "missing.model"))
    with pytest.raises(TokenizerUnavailable):
        S.SentencePieceAdapter()
