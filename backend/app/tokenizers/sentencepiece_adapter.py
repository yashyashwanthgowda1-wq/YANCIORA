"""SentencePiece Unigram adapter (experimental, research only).

Registered only when BOTH the `sentencepiece` library is installed AND a trained model file
exists at REDUTAX_SPM_MODEL (a `.model` file). No model ships with the repository: training
needs licence-cleared data (FLORES-200 is approved for evaluation only, D36) and team approval.
Counts carry status 'research' and never change hosted-model billing.
"""
from __future__ import annotations

import os
from pathlib import Path

from app.tokenizers.base import TokenizerAdapter, TokenizerInfo, TokenizerUnavailable

NAME = "redutax_unigram"
ENV_VAR = "REDUTAX_SPM_MODEL"


def model_path() -> Path | None:
    p = os.environ.get(ENV_VAR, "").strip()
    return Path(p) if p and Path(p).is_file() else None


def status() -> dict:
    """Honest availability report (no paths or secrets beyond whether a model is set)."""
    try:
        import sentencepiece  # noqa: F401
        lib = True
    except ImportError:
        lib = False
    model = model_path() is not None
    return {"name": NAME, "library_installed": lib, "model_configured": model,
            "available": lib and model,
            "note": "Experimental SentencePiece Unigram; not trained in this repository yet."
            if not model else "Experimental SentencePiece Unigram model loaded from REDUTAX_SPM_MODEL."}


class SentencePieceAdapter(TokenizerAdapter):
    def __init__(self, path: Path | None = None):
        path = path or model_path()
        if path is None:
            raise TokenizerUnavailable(f"No SentencePiece model: set {ENV_VAR} to a trained .model file")
        try:
            import sentencepiece as spm
        except ImportError as e:
            raise TokenizerUnavailable("sentencepiece library not installed") from e
        self._sp = spm.SentencePieceProcessor(model_file=str(path))
        if self._sp.get_piece_size() <= 0:
            raise TokenizerUnavailable("SentencePiece model is empty")
        self._info = TokenizerInfo(name=NAME, library="sentencepiece",
                                   version=getattr(spm, "__version__", "unknown"), kind="experimental")

    @property
    def info(self) -> TokenizerInfo:
        return self._info

    def encode(self, text: str) -> list[int]:
        return list(self._sp.encode(text, out_type=int))

    def pieces(self, text: str) -> list[str]:
        return list(self._sp.encode(text, out_type=str))
