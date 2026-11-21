"""Registry of tokenizers the API and benchmarks may use.

Phase 2 registers the team's SentencePiece Unigram models here (kind='experimental').
"""
from __future__ import annotations

from typing import Callable

from app.tokenizers.base import TokenizerAdapter
from app.tokenizers.tiktoken_adapter import TiktokenAdapter


class UnknownTokenizer(KeyError):
    pass


_FACTORIES: dict[str, Callable[[], TokenizerAdapter]] = {
    "cl100k_base": lambda: TiktokenAdapter("cl100k_base"),
    "o200k_base": lambda: TiktokenAdapter("o200k_base"),
}
_CACHE: dict[str, TokenizerAdapter] = {}

# Experimental Unigram: listed only when the library AND a trained model are present.
from app.tokenizers import sentencepiece_adapter as _spm  # noqa: E402

if _spm.status()["available"]:
    _FACTORIES[_spm.NAME] = _spm.SentencePieceAdapter


def available_tokenizers() -> list[str]:
    return sorted(_FACTORIES)


def register(name: str, factory: Callable[[], TokenizerAdapter]) -> None:
    _FACTORIES[name] = factory
    _CACHE.pop(name, None)


def get_tokenizer(name: str) -> TokenizerAdapter:
    if name not in _FACTORIES:
        raise UnknownTokenizer(name)
    if name not in _CACHE:
        _CACHE[name] = _FACTORIES[name]()
    return _CACHE[name]
