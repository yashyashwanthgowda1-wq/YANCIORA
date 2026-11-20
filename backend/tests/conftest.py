import pytest

from app.tokenizers.base import TokenizerAdapter, TokenizerInfo


class FakeTokenizer(TokenizerAdapter):
    """Deterministic stand-in: one token per UTF-8 byte. For testing logic only;
    its numbers say nothing about real tokenizers."""

    @property
    def info(self) -> TokenizerInfo:
        return TokenizerInfo("fake_bytes", "test", "0", "baseline")

    def encode(self, text: str) -> list[int]:
        return list(text.encode("utf-8"))

    def pieces(self, text: str) -> list[str]:
        return [bytes([b]).decode("utf-8", errors="replace") for b in self.encode(text)]


@pytest.fixture
def fake_tok() -> FakeTokenizer:
    return FakeTokenizer()
