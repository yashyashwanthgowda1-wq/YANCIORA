"""Model registry, cost estimation (Feature 4) and model recommendation (Feature 7).

Nothing here invents facts: prices, context windows, language support, tasks and quality tiers
come only from config/models.yaml (team-verified) or from user-entered models in the request
(labelled `source: user`). Unknown values are reported as limitations, never guessed.

Token counts reuse the existing tokenizer registry. They are encoding counts, so costs are
always estimates — never provider billing.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.schemas import (
    Candidate, CostEstimateRequest, CostEstimateResponse, ModelCost, ModelRegistryResponse, ModelSpec,
    RecommendRequest, RecommendResponse,
)
from app.tokenizers import get_tokenizer

COST_METHOD = "cost_v1"
RECOMMEND_METHOD = "rec_rules_v1"
DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "config" / "models.yaml"
BILLING_NOTE = ("Costs are estimates from encoding token counts and the listed prices. Actual "
                "provider billing (cached input, tools, audio, minimums, taxes) takes precedence.")
SUPPORT_RANK = {"verified": 3, "claimed": 2, "unknown": 1, "unsupported": 0}


class RegistryError(ValueError):
    pass


# ---------- registry ----------
def registry_path() -> Path:
    custom = get_settings().models_registry_path
    return Path(custom) if custom else DEFAULT_REGISTRY


@lru_cache(maxsize=4)
def _load(path_str: str, mtime: float) -> tuple[tuple[ModelSpec, ...], tuple[str, ...]]:
    import yaml

    path = Path(path_str)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models, seen, warnings = [], set(), []
    for i, raw in enumerate(data.get("models") or []):
        try:
            spec = ModelSpec(**{**raw, "source": "registry"})
        except Exception as exc:  # noqa: BLE001
            raise RegistryError(f"config/models.yaml entry {i + 1}: {exc}") from exc
        if spec.id in seen:
            raise RegistryError(f"config/models.yaml: duplicate model id '{spec.id}'")
        seen.add(spec.id)
        if spec.pricing and spec.pricing.verified_at is None:
            warnings.append(f"{spec.id}: price not verified (verified_at missing)")
        models.append(spec)
    return tuple(models), tuple(warnings)


def load_registry() -> tuple[list[ModelSpec], list[str]]:
    path = registry_path()
    if not path.is_file():
        return [], [f"Model registry file not found: {path.name}"]
    models, warnings = _load(str(path), path.stat().st_mtime)
    return list(models), list(warnings)


def registry_response() -> ModelRegistryResponse:
    models, warnings = load_registry()
    if not models:
        warnings = warnings + ["The model registry is empty. Add verified models to config/models.yaml, "
                               "or enter models yourself (labelled user-entered)."]
    return ModelRegistryResponse(models=models, count=len(models), registry_file="config/models.yaml",
                                 warnings=warnings)


def resolve_models(model_ids: list[str] | None, custom: list[ModelSpec]) -> tuple[list[ModelSpec], list[str]]:
    """Registry models (all, or only `model_ids`) plus user-entered ones. Returns (models, unknown ids)."""
    registry, _ = load_registry()
    by_id = {m.id: m for m in registry}
    unknown: list[str] = []
    if model_ids is None:
        chosen = list(registry)
    else:
        chosen = []
        for mid in dict.fromkeys(model_ids):
            if mid in by_id:
                chosen.append(by_id[mid])
            elif not any(c.id == mid for c in custom):
                unknown.append(mid)
    users = [c.model_copy(update={"source": "user"}) for c in custom]
    taken = {m.id for m in chosen}
    return chosen + [u for u in users if u.id not in taken], unknown


# ---------- Feature 4: cost ----------
def _price_status(m: ModelSpec) -> str:
    if not m.pricing:
        return "missing"
    if m.source == "user":
        return "user_entered"
    return "verified" if m.pricing.verified_at else "unverified"


def _cost(tokens_in: int, tokens_out: int, m: ModelSpec) -> tuple[float, float, float] | None:
    if not m.pricing:
        return None
    i = tokens_in / 1_000_000 * m.pricing.input_per_1m
    o = tokens_out / 1_000_000 * m.pricing.output_per_1m
    return i, o, i + o


def model_cost(m: ModelSpec, text: str, optimized: str | None, output_tokens: int,
               fallback_encoding: str, counts: dict) -> ModelCost:
    encoding = m.encoding or fallback_encoding
    status = "model_encoding" if m.encoding else "fallback_encoding"

    def count(t: str) -> int:
        key = (encoding, t)
        if key not in counts:
            counts[key] = get_tokenizer(encoding).count(t)
        return counts[key]

    tin = count(text)
    topt = count(optimized) if optimized is not None else None
    warnings: list[str] = []
    if status == "fallback_encoding":
        warnings.append(f"Encoding for this model is not configured; counted with {encoding} as an estimate.")
    elif not m.encoding_source:
        warnings.append("No source recorded for this model's encoding; treat the count as an estimate.")
    ps = _price_status(m)
    if ps == "missing":
        warnings.append("No price configured: cost not calculated.")
    elif ps == "unverified":
        warnings.append("Registry price has no verification date.")
    elif ps == "user_entered":
        warnings.append("User-entered price: not verified by REDUTAX.")
    if output_tokens == 0:
        warnings.append("Expected output tokens is 0: output cost is excluded.")
    if m.context_window_tokens and tin + output_tokens > m.context_window_tokens:
        warnings.append(f"Input + expected output ({tin + output_tokens} tokens) exceeds the configured "
                        f"context window ({m.context_window_tokens}).")

    base = _cost(tin, output_tokens, m)
    opt = _cost(topt, output_tokens, m) if topt is not None else None
    savings = (base[2] - opt[2]) if base and opt else None
    savings_pct = (100 * savings / base[2]) if savings is not None and base and base[2] else None
    return ModelCost(
        model_id=m.id, provider=m.provider, display_name=m.display_name, source=m.source,
        encoding_used=encoding, encoding_status=status, count_status="estimate",
        input_tokens=tin, optimized_input_tokens=topt, output_tokens=output_tokens,
        currency=m.pricing.currency if m.pricing else None,
        input_cost=base[0] if base else None, output_cost=base[1] if base else None,
        total_cost=base[2] if base else None, optimized_total_cost=opt[2] if opt else None,
        savings=savings, savings_pct=round(savings_pct, 2) if savings_pct is not None else None,
        price_status=ps, price_source_url=m.pricing.source_url if m.pricing else None,
        price_verified_at=m.pricing.verified_at if m.pricing else None, warnings=warnings,
    )


def estimate_cost(req: CostEstimateRequest) -> CostEstimateResponse:
    # model_ids given → those (+ user-entered); only user-entered → just those; neither → whole registry.
    if req.model_ids:
        models, unknown = resolve_models(req.model_ids, req.custom_models)
    elif req.custom_models:
        models, unknown = resolve_models([], req.custom_models)
    else:
        models, unknown = resolve_models(None, [])
    counts: dict = {}
    rows = [model_cost(m, req.text, req.optimized_text, req.expected_output_tokens, req.fallback_encoding, counts)
            for m in models]
    warnings = [BILLING_NOTE]
    if not rows:
        warnings.append("No models to price: the registry is empty and no models were entered.")
    if unknown:
        warnings.append("Unknown model ids ignored: " + ", ".join(unknown))
    currencies = {r.currency for r in rows if r.currency}
    if len(currencies) > 1:
        warnings.append("Models use different currencies (" + ", ".join(sorted(currencies)) +
                        "); totals are not directly comparable.")
    return CostEstimateResponse(method=COST_METHOD, models=rows, expected_output_tokens=req.expected_output_tokens,
                                unknown_model_ids=unknown, warnings=warnings)


# ---------- Feature 7: recommendation ----------
def _evaluate(m: ModelSpec, req: RecommendRequest, counts: dict) -> Candidate:
    cost = model_cost(m, req.text, None, req.expected_output_tokens, "o200k_base", counts)
    required = cost.input_tokens + req.expected_output_tokens
    support = m.languages.get(req.language, "unknown")
    reasons, exclusions, limitations = [], [], []

    if support == "unsupported":
        exclusions.append(f"{req.language} is marked unsupported for this model.")
    elif req.require_language_support == "verified" and support != "verified":
        exclusions.append(f"Language support for {req.language} is '{support}', not verified.")
    elif req.require_language_support == "claimed" and support not in ("verified", "claimed"):
        exclusions.append(f"Language support for {req.language} is '{support}' (needs claimed or verified).")
    else:
        reasons.append(f"Language support for {req.language}: {support}"
                       + (" (team-measured)" if support == "verified" else
                          " (provider documentation)" if support == "claimed" else ""))
        if support == "unknown":
            limitations.append(f"Support for {req.language} is not documented in the registry.")

    if m.context_window_tokens is None:
        if req.min_context_tokens:
            exclusions.append("Context window not configured, so the minimum context cannot be confirmed.")
        else:
            limitations.append("Context window not configured.")
    else:
        if required > m.context_window_tokens:
            exclusions.append(f"Needs {required} tokens; context window is {m.context_window_tokens}.")
        if req.min_context_tokens and m.context_window_tokens < req.min_context_tokens:
            exclusions.append(f"Context window {m.context_window_tokens} is below the required "
                              f"{req.min_context_tokens}.")
        if not exclusions:
            reasons.append(f"Fits the context window ({required} of {m.context_window_tokens} tokens).")

    if m.tasks:
        if req.task_type in m.tasks:
            reasons.append(f"Task '{req.task_type}' is listed for this model.")
        else:
            exclusions.append(f"Task '{req.task_type}' is not among the documented tasks.")
    else:
        limitations.append("Supported tasks are not documented in the registry.")

    if req.min_quality_tier:
        if m.quality_tier is None:
            exclusions.append("No team quality tier recorded, so the minimum quality cannot be confirmed.")
        elif m.quality_tier < req.min_quality_tier:
            exclusions.append(f"Quality tier {m.quality_tier} is below the required {req.min_quality_tier}.")
    if m.quality_tier is not None:
        reasons.append(f"Team quality tier {m.quality_tier}/5" + (f" ({m.quality_source})" if m.quality_source else ""))

    if cost.total_cost is None:
        limitations.append("No price configured: cost cannot be compared.")
    else:
        reasons.append(f"Estimated cost {cost.total_cost:.6f} {cost.currency} ({cost.price_status.replace('_', ' ')} price).")
    if cost.encoding_status == "fallback_encoding":
        limitations.append("Token count uses a fallback encoding (estimate).")
    if m.source == "user":
        limitations.append("User-entered model: metadata not verified by REDUTAX.")

    return Candidate(
        model_id=m.id, provider=m.provider, display_name=m.display_name, source=m.source,
        eligible=not exclusions, rank=None, language_support=support,
        context_window_tokens=m.context_window_tokens, required_tokens=required,
        quality_tier=m.quality_tier, cost=cost, reasons=reasons, exclusions=exclusions,
        limitations=limitations,
    )


def _sort_key(c: Candidate, pref: str):
    cost = c.cost.total_cost if c.cost.total_cost is not None else float("inf")
    quality = -(c.quality_tier or 0)
    support = -SUPPORT_RANK[c.language_support]
    if pref == "lowest":
        return (cost, support, quality, c.model_id)
    if pref == "quality":
        return (quality, support, cost, c.model_id)
    return (support, cost, quality, c.model_id)        # balanced


def recommend(req: RecommendRequest) -> RecommendResponse:
    models, unknown = resolve_models(req.model_ids, req.custom_models)
    counts: dict = {}
    cands = [_evaluate(m, req, counts) for m in models]
    eligible = sorted((c for c in cands if c.eligible), key=lambda c: _sort_key(c, req.cost_preference))
    excluded = [c for c in cands if not c.eligible]
    for i, c in enumerate(eligible, start=1):
        c.rank = i
    warnings = [BILLING_NOTE]
    if unknown:
        warnings.append("Unknown model ids ignored: " + ", ".join(unknown))
    locked = False
    recommended = eligible[0] if eligible else None

    if req.locked_model_id:
        lock = next((c for c in cands if c.model_id == req.locked_model_id), None)
        if lock is None:
            warnings.append(f"Locked model '{req.locked_model_id}' is not in the registry or request.")
        else:
            locked, recommended = True, lock
            if not lock.eligible:
                warnings.append("The locked model does not meet: " + "; ".join(lock.exclusions)
                                + " It stays selected because it is locked.")

    alternatives = [c for c in eligible if recommended is None or c.model_id != recommended.model_id]
    if not models:
        explanation = ("No models are configured. Add verified models to config/models.yaml or enter "
                       "models yourself; REDUTAX does not invent model data.")
    elif recommended is None:
        explanation = ("No model meets every requirement. See the exclusions for each model and relax a "
                       "requirement or add model data.")
    elif locked:
        explanation = f"{recommended.model_id} is locked by you, so it is kept without switching."
    else:
        basis = {"lowest": "the lowest estimated cost", "quality": "the highest team quality tier",
                 "balanced": "the strongest documented language support, then cost"}[req.cost_preference]
        explanation = (f"{recommended.model_id} meets every requirement and ranks first by {basis} "
                       f"among {len(eligible)} eligible model(s).")
    return RecommendResponse(method=RECOMMEND_METHOD, language=req.language, task_type=req.task_type,
                             cost_preference=req.cost_preference, recommended=recommended,
                             alternatives=alternatives, excluded=excluded, locked=locked,
                             explanation=explanation, warnings=warnings)
