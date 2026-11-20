"""Token counting and language comparison. Framework-free so the API, the benchmark
runner and tests all share one implementation."""
from __future__ import annotations

from app.core import text as T
from app.core.metrics import fertility, relative_ratio
from app.schemas import (
    CompareRequest, CompareResponse, CompareRow, TokenizeRequest, TokenizeResponse, TokenizerRef,
)
from app.tokenizers import TokenizerAdapter, get_tokenizer

RATIO_NOTE = "Ratios are tokenization ratios under {tok}. They are not cost multipliers."
UNALIGNED_WARNING = (
    "These texts are not verified as meaning-equivalent (no aligned_group_id). "
    "Ratios may not be comparable."
)


def tokenizer_ref(adapter: TokenizerAdapter) -> TokenizerRef:
    i = adapter.info
    return TokenizerRef(name=i.name, library=i.library, version=i.version, kind=i.kind)


def tokenize(req: TokenizeRequest, adapter: TokenizerAdapter | None = None) -> TokenizeResponse:
    adapter = adapter or get_tokenizer(req.tokenizer)
    norm = T.normalize(req.text)
    script = req.script or T.detect_script(norm)
    language = req.language if req.language != "auto" else T.guess_language(script)
    tokens = adapter.count(norm)
    words = T.word_count(norm)
    return TokenizeResponse(
        tokenizer=tokenizer_ref(adapter),
        status=adapter.count_status,
        language=language,
        script=script,
        token_count=tokens,
        word_count=words,
        char_count=len(norm),
        tokens_per_word=fertility(tokens, words),
        normalization=T.NORMALIZATION_ID,
        word_count_method=T.WORD_COUNT_METHOD,
        pieces=adapter.pieces(norm) if req.include_pieces else None,
    )


def compare(req: CompareRequest, adapter: TokenizerAdapter | None = None) -> CompareResponse:
    if req.reference_index >= len(req.variants):
        raise ValueError("reference_index is out of range")
    adapter = adapter or get_tokenizer(req.tokenizer)

    partial = []
    for v in req.variants:
        norm = T.normalize(v.text)
        tokens, words = adapter.count(norm), T.word_count(norm)
        partial.append((v, tokens, words, fertility(tokens, words)))

    ref_fert = partial[req.reference_index][3]
    rows = [
        CompareRow(
            **v.model_dump(), token_count=t, word_count=w, tokens_per_word=f,
            ratio_vs_reference=relative_ratio(f, ref_fert),
        )
        for v, t, w, f in partial
    ]

    aligned = req.aligned_group_id is not None
    warnings = [] if aligned else [UNALIGNED_WARNING]
    for v, *_ in partial:
        detected = T.detect_script(T.normalize(v.text))
        if detected and detected != v.script:
            warnings.append(f"{v.language}: declared script {v.script} but text looks like {detected}.")
    if ref_fert is None:
        warnings.append("Reference variant has no words; ratios are undefined.")
    warnings.append(RATIO_NOTE.format(tok=adapter.info.name))

    return CompareResponse(
        tokenizer=tokenizer_ref(adapter), status=adapter.count_status,
        aligned=aligned, rows=rows, warnings=warnings,
    )
