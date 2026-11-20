"""tiktoken encodings (cl100k_base, o200k_base).

These are encoding baselines. Which hosted models use which encoding must be verified
separately before any billing claim (BRD §10); this adapter makes no model association.

Note: tiktoken downloads encoding files on first use and caches them
(set TIKTOKEN_CACHE_DIR to control where). Offline machines need that cache pre-filled.
"""
from __future__ import annotations

from functools import cached_property

from app.tokenizers.base import TokenizerAdapter, TokenizerInfo, TokenizerUnavailable


class TiktokenAdapter(TokenizerAdapter):
    def __init__(self, encoding_name: str):
        self.encoding_name = encoding_name

    @cached_property
    def _enc(self):
        try:
            import tiktoken
        except ImportError as exc:
            raise TokenizerUnavailable("tiktoken is not installed") from exc
        try:
            return tiktoken.get_encoding(self.encoding_name)
        except Exception as exc:  # download failure, unknown name
            raise TokenizerUnavailable(
                f"could not load encoding {self.encoding_name}: {type(exc).__name__}"
            ) from exc

    @cached_property
    def info(self) -> TokenizerInfo:
        try:
            from importlib.metadata import version

            lib_version = version("tiktoken")
        except Exception:
            lib_version = "unknown"
        return TokenizerInfo(self.encoding_name, "tiktoken", lib_version, "baseline")

    def encode(self, text: str) -> list[int]:
        # disallowed_special=() so user text containing "<|endoftext|>" is counted as text.
        return self._enc.encode(text, disallowed_special=())

    def pieces(self, text: str) -> list[str]:
        enc = self._enc
        return [
            enc.decode_single_token_bytes(t).decode("utf-8", errors="replace")
            for t in self.encode(text)
        ]
