"""The REDUTAX pipeline shared by Voice (F8), Chat (F9) and Vapi (F10).

text → language/script → token count → optimizer (with the Feature 5 meaning gate, Feature 6
script suggestions in aggressive mode) → recommendation (F7) → cost (F4).

It only orchestrates existing services; no tokenization, optimization or meaning logic lives
here. Nothing is applied automatically beyond the optimizer's own `accepted` edits (meaning
check "preserved"); suggestions need the user's approval via `apply_edits`.
"""
from __future__ import annotations

from app.core import details as D
from app.core import text as T
from app.optimizer.rules import Edit
from app.schemas import (
    AnalyzeRequest, AnalyzeResponse, ApplyEditsRequest, ApplyEditsResponse, CostEstimateRequest,
    MeaningCheckRequest, OptimizeRequest, RecommendRequest, TokenizeRequest,
)
from app.services import counting, meaning, models, optimizer
from app.services.counting import tokenizer_ref
from app.tokenizers import get_tokenizer

METHOD_ID = "pipeline_v1"


def resolve_language(language: str, text: str) -> tuple[str | None, str | None]:
    script = T.detect_script(T.normalize(text))
    lang = language if language != "auto" else T.guess_language(script)
    return lang, script


def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    lang, script = resolve_language(req.language, req.text)
    tokens = counting.tokenize(TokenizeRequest(text=req.text, tokenizer=req.tokenizer,
                                               language=req.language))
    opt = optimizer.optimize(OptimizeRequest(
        text=req.text, language=req.language, mode=req.mode, tokenizers=[req.tokenizer],
        protected_terms=req.protected_terms))

    recommendation = cost = None
    registry, _ = models.load_registry()
    if registry or req.custom_models:
        if lang:
            recommendation = models.recommend(RecommendRequest(
                text=opt.optimized, language=lang, task_type=req.task_type,
                cost_preference=req.cost_preference, expected_output_tokens=req.expected_output_tokens,
                model_ids=req.model_ids, custom_models=req.custom_models,
                locked_model_id=req.locked_model_id))
        cost = models.estimate_cost(CostEstimateRequest(
            text=req.text, optimized_text=opt.optimized if opt.changed else None,
            model_ids=req.model_ids or [], custom_models=req.custom_models,
            expected_output_tokens=req.expected_output_tokens))

    if opt.requires_review:
        next_step = "Review the suggestions; approve the ones you want, then apply them."
    elif opt.changed:
        next_step = "Safe edits were applied automatically; check the comparison and use the optimized text."
    else:
        next_step = "No safe edit was found; the original text is kept."
    if recommendation is None and not registry and not req.custom_models:
        next_step += " Add models (registry or your own) to get a recommendation and cost estimate."
    elif recommendation is None and lang is None:
        next_step += " Choose a language to get a model recommendation."

    return AnalyzeResponse(method=METHOD_ID, language=lang, script=script, tokens=tokens,
                           optimization=opt, recommendation=recommendation, cost=cost,
                           requires_review=opt.requires_review, next_step=next_step)


class EditError(ValueError):
    pass


def apply_edits(req: ApplyEditsRequest) -> ApplyEditsResponse:
    """Apply the edits the user approved (offsets into the NFC original), then re-check meaning.
    The result is marked not allowed when the meaning check reports 'changed'."""
    src = D.nfc(req.original)
    edits = sorted(req.edits, key=lambda e: e.start)
    prev_end = 0
    for e in edits:
        if e.end < e.start or e.end > len(src):
            raise EditError(f"edit {e.start}-{e.end} is outside the text (length {len(src)})")
        if e.start < prev_end:
            raise EditError(f"edits overlap at position {e.start}")
        prev_end = e.end
    text = optimizer._apply(src, [Edit("approved", e.start, e.end, e.after) for e in edits]) if edits else req.original
    mc = meaning.check(MeaningCheckRequest(original=src, candidate=text, language=req.language,
                                           protected_terms=req.protected_terms))
    tok = get_tokenizer(req.tokenizer)
    before, after = tok.count(req.original), tok.count(text)
    warnings = []
    if mc.status == "changed":
        warnings.append("The meaning check reports a changed critical detail: do not use this text.")
    elif mc.status == "at_risk":
        warnings.append("The meaning check reports at_risk: you approved these edits; review the result.")
    if after > before:
        warnings.append(f"The edited text uses more tokens ({after} vs {before}).")
    return ApplyEditsResponse(text=text, applied_count=len(edits), allowed=mc.status != "changed",
                              meaning_check=mc, tokenizer=tokenizer_ref(tok), tokens_before=before,
                              tokens_after=after, warnings=warnings)
