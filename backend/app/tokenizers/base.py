"""Tokenizer adapter interface.

Every adapter reports its exact identity (name, library, library version, kind) so no
count is ever shown without its tokenizer (BRD §16 correctness). Counts from these
adapters are tokenizer counts, not provider-billed usage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

TokenizerKind = Literal["baseline", "experimental", "model_input"]
CountStatus = Literal["exact", "estimate", "provider_reported", "research", "mock", "unsupported"]


class TokenizerUnavailable(RuntimeError):
    """The tokenizer's library or vocabulary files are not available in this environment."""


@dataclass(frozen=True)
class TokenizerInfo:
    name: str
    library: str
    version: str
    kind: TokenizerKind


class TokenizerAdapter(ABC):
    @property
    @abstractmethod
    def info(self) -> TokenizerInfo: ...

    @property
    def count_status(self) -> CountStatus:
        """'exact' = the real tokenizer ran. Experimental tokenizers report 'research'."""
        return "research" if self.info.kind == "experimental" else "exact"

    @abstractmethod
    def encode(self, text: str) -> list[int]: ...

    @abstractmethod
    def pieces(self, text: str) -> list[str]:
        """Human-readable token pieces. Byte-level tokenizers may split a character
        across pieces; such fragments are shown with U+FFFD."""

    def count(self, text: str) -> int:
        return len(self.encode(text))
