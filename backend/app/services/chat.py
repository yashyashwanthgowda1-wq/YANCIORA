"""Chat (Feature 9): REDUTAX analysis of every message, then — only after the user approves
the prompt — a reply from the configured LLM provider.

- Analysis mode works without credentials and is deterministic: it reports what REDUTAX
  measured and changed. It never produces an AI-style answer.
- LLM replies come only from a real provider call (app.integrations.providers).
- History lives in process memory per session (bounded, expiring); it is never logged or stored
  in the database.
"""
from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from app.core.config import Settings
from app.integrations import providers
from app.schemas import (
    AnalyzeResponse, ChatAnalyzeRequest, ChatAnalyzeResponse, ChatHistoryResponse, ChatSendRequest,
    ChatSendResponse, ChatTurn, LlmUsage,
)
from app.services import pipeline

MAX_SESSIONS = 200
MAX_TURNS = 40
SESSION_TTL_SECONDS = 2 * 60 * 60
MAX_CONTEXT_TURNS = 12               # earlier turns sent to the LLM for context
ANALYSIS_NOTE = "REDUTAX analysis mode — this is not a live AI conversation."
SYSTEM_PROMPT = ("You are a helpful assistant. Answer in the same language as the user's message. "
                 "Keep numbers, dates, names, money amounts and negations exactly as given.")


class SessionNotFound(LookupError):
    pass


class _Store:
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: "OrderedDict[str, tuple[float, list[ChatTurn]]]" = OrderedDict()

    def _evict(self, now: float) -> None:
        for sid in [k for k, (t, _) in self._sessions.items() if now - t > SESSION_TTL_SECONDS]:
            del self._sessions[sid]
        while len(self._sessions) > MAX_SESSIONS:
            self._sessions.popitem(last=False)

    def get_or_create(self, sid: str | None) -> tuple[str, list[ChatTurn]]:
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if sid and sid in self._sessions:
                self._sessions.move_to_end(sid)
                return sid, self._sessions[sid][1]
            new = secrets.token_urlsafe(12)
            self._sessions[new] = (now, [])
            return new, self._sessions[new][1]

    def get(self, sid: str) -> list[ChatTurn]:
        with self._lock:
            self._evict(time.monotonic())
            if sid not in self._sessions:
                raise SessionNotFound(sid)
            return self._sessions[sid][1]

    def append(self, sid: str, *turns: ChatTurn) -> list[ChatTurn]:
        with self._lock:
            _, hist = self._sessions.get(sid, (0.0, []))
            hist.extend(turns)
            del hist[:-MAX_TURNS]
            self._sessions[sid] = (time.monotonic(), hist)
            return list(hist)

    def delete(self, sid: str) -> None:
        with self._lock:
            self._sessions.pop(sid, None)


store = _Store()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def analysis_reply(a: AnalyzeResponse) -> str:
    """Plain-language summary of the REDUTAX analysis. Deterministic; contains no AI answer."""
    o, t = a.optimization, a.tokens
    before, after = o.token_counts[0].before, o.token_counts[0].after
    lines = [ANALYSIS_NOTE,
             f"Language: {a.language or 'not detected (choose one)'} · script: {a.script or 'none'}.",
             f"Tokens ({t.tokenizer.name}): {before} → {after} after safe optimization "
             f"({o.token_counts[0].saved} saved).",
             f"Edits: {len(o.accepted)} applied automatically, {len(o.suggestions)} waiting for your "
             f"approval, {len(o.rejected)} rejected.",
             f"Meaning check ({o.meaning_check.method}): {o.meaning_check.status}."]
    if a.recommendation and a.recommendation.recommended:
        r = a.recommendation.recommended
        cost = (f", estimated {r.cost.total_cost:.6f} {r.cost.currency}" if r.cost.total_cost is not None else "")
        lines.append(f"Recommended model: {r.model_id} ({r.provider}){cost}.")
    elif a.recommendation:
        lines.append("No configured model meets every requirement.")
    else:
        lines.append("No models configured, so no recommendation or cost estimate.")
    lines.append(a.next_step)
    return "\n".join(lines)


def analyze_turn(req: ChatAnalyzeRequest, settings: Settings) -> ChatAnalyzeResponse:
    sid, _ = store.get_or_create(req.session_id)
    analysis = pipeline.analyze(req)
    reply = analysis_reply(analysis)
    hist = store.append(
        sid,
        ChatTurn(role="user", kind="message", content=req.text, created_at=_now(),
                 meta={"language": analysis.language, "tokens": analysis.tokens.token_count}),
        ChatTurn(role="assistant", kind="analysis", content=reply, created_at=_now(),
                 meta={"optimized": analysis.optimization.optimized,
                       "requires_review": analysis.requires_review,
                       "meaning_status": analysis.optimization.meaning_check.status}),
    )
    return ChatAnalyzeResponse(session_id=sid, mode="analysis", reply=reply, analysis=analysis,
                               llm_available=providers.llm_configured(settings), history=hist)


def send_turn(sid: str, req: ChatSendRequest, settings: Settings, transport=None) -> ChatSendResponse:
    """Send the approved prompt (with recent conversation context) to the configured LLM."""
    history = store.get(sid)
    context = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in history[-MAX_CONTEXT_TURNS:]:
        if turn.kind == "llm_reply":
            context.append({"role": "assistant", "content": turn.content})
        elif turn.kind == "message" and turn.meta.get("sent"):
            context.append({"role": "user", "content": turn.content})
    context.append({"role": "user", "content": req.text})
    reply = providers.chat_complete(settings, context, transport=transport)
    provider_name = settings.llm_provider_name or "configured provider"
    hist = store.append(
        sid,
        ChatTurn(role="user", kind="message", content=req.text, created_at=_now(),
                 meta={"sent": True, "approved_prompt": True}),
        ChatTurn(role="assistant", kind="llm_reply", content=reply.text, created_at=_now(),
                 meta={"provider": provider_name, "model": reply.model,
                       "prompt_tokens": reply.prompt_tokens, "completion_tokens": reply.completion_tokens}),
    )
    usage = (LlmUsage(prompt_tokens=reply.prompt_tokens, completion_tokens=reply.completion_tokens,
                      total_tokens=reply.total_tokens, status="provider_reported")
             if any(v is not None for v in (reply.prompt_tokens, reply.completion_tokens, reply.total_tokens))
             else None)
    return ChatSendResponse(session_id=sid, reply=reply.text, provider=provider_name, model=reply.model,
                            usage=usage, history=hist)


def history(sid: str) -> ChatHistoryResponse:
    return ChatHistoryResponse(session_id=sid, history=list(store.get(sid)))
