"""Phase 2 routes: models/cost (F4, F7), pipeline (F8 text workflow), voice transcription (F8),
chat (F9), integration status, and the Vapi webhook (F10). Routes stay thin."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.api.errors import ApiException
from app.core.config import Settings, get_settings
from app.db.session import check_database
from app.integrations import providers, vapi
from app.schemas import (
    AnalyzeRequest, AnalyzeResponse, ApplyEditsRequest, ApplyEditsResponse, ChatAnalyzeRequest,
    ChatAnalyzeResponse, ChatHistoryResponse, ChatSendRequest, ChatSendResponse, CostEstimateRequest,
    CostEstimateResponse, IntegrationsResponse, IntegrationStatus, ModelRegistryResponse,
    RecommendRequest, RecommendResponse, TranscribeRequest, TranscribeResponse, VapiStatusResponse,
)
from app.services import chat, models, pipeline
from app.tokenizers import TokenizerUnavailable, UnknownTokenizer, available_tokenizers

router = APIRouter(prefix="/api", tags=["phase2"])


def _run(fn, *args):
    try:
        return fn(*args)
    except models.RegistryError as exc:
        raise ApiException(503, "registry_invalid", str(exc))
    except UnknownTokenizer as exc:
        raise ApiException(400, "unknown_tokenizer",
                           f"Unknown tokenizer '{exc.args[0]}'. Available: {', '.join(available_tokenizers())}.")
    except TokenizerUnavailable as exc:
        raise ApiException(503, "tokenizer_unavailable", str(exc))
    except pipeline.EditError as exc:
        raise ApiException(422, "invalid_request", str(exc))
    except chat.SessionNotFound:
        raise ApiException(404, "not_found", "Chat session not found or expired. Start a new chat.")


# ---------- Feature 4 + 7 ----------
@router.get("/models", response_model=ModelRegistryResponse)
def list_models() -> ModelRegistryResponse:
    """Configured model registry (config/models.yaml). Ships empty; never contains invented data."""
    return _run(models.registry_response)


@router.post("/cost/estimate", response_model=CostEstimateResponse)
def cost_estimate(req: CostEstimateRequest) -> CostEstimateResponse:
    """Input/output/total cost estimates per model, original vs optimized. Encoding counts and
    configured prices only — not provider billing."""
    return _run(models.estimate_cost, req)


@router.post("/models/recommend", response_model=RecommendResponse)
def models_recommend(req: RecommendRequest) -> RecommendResponse:
    """Explainable, rule-based recommendation from configured model metadata (no paid LLM)."""
    return _run(models.recommend, req)


# ---------- pipeline (Feature 8 text workflow; shared with chat and Vapi) ----------
@router.post("/pipeline/analyze", response_model=AnalyzeResponse)
def pipeline_analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Tokens → optimizer (meaning-gated) → recommendation → cost. Suggestions are not applied."""
    return _run(pipeline.analyze, req)


@router.post("/pipeline/apply", response_model=ApplyEditsResponse)
def pipeline_apply(req: ApplyEditsRequest) -> ApplyEditsResponse:
    """Apply user-approved edits and re-run the meaning check (allowed=false if changed)."""
    return _run(pipeline.apply_edits, req)


# ---------- Feature 8: server-side transcription ----------
@router.post("/voice/transcribe", response_model=TranscribeResponse)
def voice_transcribe(req: TranscribeRequest, settings: Settings = Depends(get_settings)) -> TranscribeResponse:
    """Transcribe audio with the configured speech-to-text provider. 503 when not configured."""
    lang = None if req.language == "auto" else req.language
    try:
        t = providers.transcribe(settings, req.audio_base64, req.mime_type, lang)
    except providers.ProviderNotConfigured as exc:
        raise ApiException(503, "stt_not_configured", str(exc))
    except providers.ProviderRateLimited as exc:
        raise ApiException(429, "provider_rate_limited", str(exc))
    except providers.ProviderError as exc:
        raise ApiException(502, "provider_error", str(exc))
    except ValueError as exc:
        raise ApiException(422, "invalid_request", str(exc))
    return TranscribeResponse(text=t.text, language=lang, provider="configured STT provider", model=t.model,
                              status="provider_transcript")


# ---------- Feature 9: chat ----------
@router.post("/chat", response_model=ChatAnalyzeResponse)
def chat_analyze(req: ChatAnalyzeRequest, settings: Settings = Depends(get_settings)) -> ChatAnalyzeResponse:
    """Analyse a chat message with REDUTAX (deterministic analysis mode, no AI answer)."""
    return _run(chat.analyze_turn, req, settings)


@router.post("/chat/{session_id}/send", response_model=ChatSendResponse)
def chat_send(session_id: str, req: ChatSendRequest, settings: Settings = Depends(get_settings)) -> ChatSendResponse:
    """Send the user-approved prompt to the configured LLM. 503 when no LLM is configured."""
    try:
        return _run(chat.send_turn, session_id, req, settings)
    except providers.ProviderNotConfigured as exc:
        raise ApiException(503, "llm_not_configured", str(exc))
    except providers.ProviderRateLimited as exc:
        raise ApiException(429, "provider_rate_limited", str(exc))
    except providers.ProviderError as exc:
        raise ApiException(502, "provider_error", str(exc))


@router.get("/chat/{session_id}", response_model=ChatHistoryResponse)
def chat_history(session_id: str) -> ChatHistoryResponse:
    return _run(chat.history, session_id)


@router.delete("/chat/{session_id}", status_code=204)
def chat_delete(session_id: str) -> None:
    chat.store.delete(session_id)


# ---------- status ----------
@router.get("/integrations/status", response_model=IntegrationsResponse)
def integrations_status(settings: Settings = Depends(get_settings)) -> IntegrationsResponse:
    """Which providers are configured. Never returns credentials, hosts or keys."""
    db = check_database(settings.database_url)
    try:
        registry, _ = models.load_registry()
        reg = IntegrationStatus(configured=bool(registry), detail=f"{len(registry)} model(s) in config/models.yaml")
    except models.RegistryError as exc:
        reg = IntegrationStatus(configured=False, detail=f"invalid: {exc}")
    return IntegrationsResponse(
        database=IntegrationStatus(configured=db["status"] == "ok", detail=db["status"]),
        models_registry=reg,
        speech_to_text=IntegrationStatus(configured=providers.stt_configured(settings),
                                         detail="configured" if providers.stt_configured(settings)
                                         else "not configured: browser voice input or typing only"),
        llm=IntegrationStatus(configured=providers.llm_configured(settings),
                              detail=(f"configured ({settings.llm_provider_name or 'provider'} · {settings.llm_model})"
                                      if providers.llm_configured(settings)
                                      else "not configured: chat runs in REDUTAX analysis mode")),
        vapi_webhook=IntegrationStatus(configured=bool(vapi.auth_modes(settings)),
                                       detail=("authentication configured: " + ", ".join(vapi.auth_modes(settings)))
                                       if vapi.auth_modes(settings) else "no webhook secret: requests are refused"),
    )


# ---------- Feature 10: Vapi ----------
@router.get("/vapi/status", response_model=VapiStatusResponse)
def vapi_status(settings: Settings = Depends(get_settings)) -> VapiStatusResponse:
    return VapiStatusResponse(webhook_path=vapi.WEBHOOK_PATH, auth_configured=bool(vapi.auth_modes(settings)),
                              auth_modes=vapi.auth_modes(settings), tools=sorted(vapi.TOOLS),
                              assistant_config="config/vapi/redutax-assistant.json",
                              connection_guide="docs/VAPI_FINAL_CONNECTION_GUIDE.md", live_call_verified=False)


@router.post("/vapi/webhook")
async def vapi_webhook(request: Request, settings: Settings = Depends(get_settings)):
    """Vapi server URL. Authenticated (Bearer / X-Vapi-Secret / HMAC). Tool calls → HTTP 200
    {"results": [...]}; other events → {}."""
    body = await request.body()
    if len(body) > vapi.MAX_BODY_BYTES:
        raise ApiException(413, "payload_too_large", "Request body is too large.")
    try:
        ok = vapi.verify(dict(request.headers), body, settings)
    except vapi.AuthNotConfigured:
        raise ApiException(503, "vapi_not_configured",
                           "The Vapi webhook secret is not configured on the server; requests are refused.")
    if not ok:
        raise ApiException(401, "unauthorized", "Invalid or missing Vapi credentials.")
    try:
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("body must be a JSON object")
        result = vapi.handle(payload, settings)
    except (ValueError, json.JSONDecodeError) as exc:
        raise ApiException(422, "invalid_request", f"Invalid Vapi payload: {exc}")
    return JSONResponse(status_code=200, content=result)
