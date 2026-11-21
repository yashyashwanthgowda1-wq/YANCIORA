"""Vapi server-URL integration (Feature 10): authentication, event dispatch and tools.

Request/response contract (Vapi docs, custom tools):
  request : {"message": {"type": "tool-calls", "toolCallList": [{"id", "type": "function",
             "function": {"name", "arguments"}}], "call": {"id", ...}, ...}}
  response: HTTP 200 {"results": [{"toolCallId": id, "name": tool, "result": "<flat string>"}]}
            (or "error" instead of "result" for a failed call). Checked against Vapi's OpenAPI spec
            (2026-11-21): ToolCallFunction.arguments is a JSON *string* (objects are accepted too);
            ToolCallResult requires toolCallId and name.
Other message types (status-update, end-of-call-report, transcript, ...) are acknowledged with {}.

Authentication (Vapi custom credentials): "Authorization: Bearer <secret>" or the legacy
"X-Vapi-Secret: <secret>", and/or an HMAC-SHA256 hex signature over "{timestamp}.{body}" (header
names configurable; the timestamp header is REQUIRED and must be within 5 minutes, so a captured
request cannot be replayed later). With no secret configured the webhook refuses every request.

Tools reuse the existing services — no business logic is duplicated here. Logs contain only the
event type, call id, tool name, duration and outcome; never transcripts or arguments.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from typing import Any, Callable

from pydantic import ValidationError

from app.core import text as T
from app.core.config import Settings
from app.schemas import (
    CostEstimateRequest, MeaningCheckRequest, OptimizeRequest, RecommendRequest, TokenizeRequest,
)
from app.services import counting, meaning, models, optimizer

logger = logging.getLogger("redutax.vapi")
WEBHOOK_PATH = "/api/vapi/webhook"
MAX_BODY_BYTES = 1_000_000
HMAC_MAX_SKEW_SECONDS = 300
_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="vapi-tool")


# ---------- authentication ----------
class AuthNotConfigured(RuntimeError):
    pass


def auth_modes(s: Settings) -> list[str]:
    modes = []
    if s.vapi_webhook_secret:
        modes += ["bearer", "x-vapi-secret"]
    if s.vapi_hmac_secret:
        modes.append("hmac-sha256")
    return modes


def verify(headers: dict[str, str], body: bytes, s: Settings, now: float | None = None) -> bool:
    """True when the request carries a valid credential. Raises AuthNotConfigured when no secret
    is configured (the webhook must then refuse every request)."""
    if not s.vapi_webhook_secret and not s.vapi_hmac_secret:
        raise AuthNotConfigured("VAPI_WEBHOOK_SECRET or VAPI_HMAC_SECRET is not set")
    h = {k.lower(): v for k, v in headers.items()}
    if s.vapi_webhook_secret:
        secret = s.vapi_webhook_secret.encode()
        auth = h.get("authorization", "")
        if auth.lower().startswith("bearer ") and hmac.compare_digest(auth[7:].strip().encode(), secret):
            return True
        if hmac.compare_digest(h.get("x-vapi-secret", "").encode(), secret) and h.get("x-vapi-secret"):
            return True
    if s.vapi_hmac_secret:
        sig = h.get(s.vapi_hmac_signature_header.lower(), "").strip()
        if sig.lower().startswith("sha256="):
            sig = sig[7:]
        ts = h.get(s.vapi_hmac_timestamp_header.lower(), "").strip()
        if sig and ts:                                           # no timestamp → no replay protection → refuse
            try:
                tsv = float(ts)
            except ValueError:
                return False
            tsv = tsv / 1000 if tsv > 1e11 else tsv              # milliseconds or seconds
            if abs((now or time.time()) - tsv) > HMAC_MAX_SKEW_SECONDS:
                return False
            payload = ts.encode() + b"." + body
            expected = hmac.new(s.vapi_hmac_secret.encode(), payload, hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig.lower().encode(), expected.encode()):
                return True
    return False


# ---------- tools (thin wrappers over existing services) ----------
def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def tool_detect_language(args: dict) -> str:
    text = str(args.get("text", ""))
    if not text.strip():
        raise ValueError("text is required")
    script = T.detect_script(T.normalize(text))
    lang = T.guess_language(script)
    if script in ("Latn", "mixed"):
        note = ("Latin script: the language could be English or Romanized Kannada/Hindi/Tamil/Telugu; "
                "ask the caller.")
    elif script is None:
        note = "No recognisable letters in the text; ask the caller to repeat or to name their language."
    else:
        note = ""
    return _json({"script": script, "language": lang, "note": note})


def tool_analyze_tokens(args: dict) -> str:
    r = counting.tokenize(TokenizeRequest(text=args.get("text", ""), tokenizer=args.get("tokenizer", "cl100k_base"),
                                          language=args.get("language", "auto")))
    return _json({"token_count": r.token_count, "word_count": r.word_count, "tokens_per_word": r.tokens_per_word,
                  "tokenizer": f"{r.tokenizer.name} ({r.tokenizer.library} {r.tokenizer.version})",
                  "count_status": r.status, "language": r.language, "script": r.script,
                  "note": "Tokenizer count, not provider billing."})


def tool_optimize_prompt(args: dict) -> str:
    r = optimizer.optimize(OptimizeRequest(text=args.get("text", ""), language=args.get("language", "auto"),
                                           mode="safe", tokenizers=[args.get("tokenizer", "cl100k_base")]))
    tc = r.token_counts[0]
    return _json({"optimized_text": r.optimized, "changed": r.changed, "tokens_before": tc.before,
                  "tokens_after": tc.after, "applied_edits": len(r.accepted),
                  "suggestions_needing_review": len(r.suggestions), "meaning_check": r.meaning_check.status,
                  "note": "Only edits that saved tokens and passed the meaning check were applied; "
                          "suggestions were NOT applied."})


def tool_check_meaning(args: dict) -> str:
    r = meaning.check(MeaningCheckRequest(original=args.get("original", ""), candidate=args.get("candidate", ""),
                                          language=args.get("language", "auto")))
    return _json({"status": r.status, "missing": [f"{f.category}:{f.example}" for f in r.findings if f.state == "missing"],
                  "added": [f"{f.category}:{f.example}" for f in r.findings if f.state == "added"],
                  "risks": r.risks, "note": "Rule-based check; 'preserved' is not a guarantee."})


def tool_recommend_model(args: dict) -> str:
    r = models.recommend(RecommendRequest(**{k: v for k, v in args.items() if k in RecommendRequest.model_fields}))
    rec = r.recommended
    return _json({"recommended": rec.model_id if rec else None,
                  "estimated_cost": (f"{rec.cost.total_cost:.6f} {rec.cost.currency}"
                                     if rec and rec.cost.total_cost is not None else None),
                  "alternatives": [c.model_id for c in r.alternatives][:3],
                  "explanation": r.explanation, "limitations": rec.limitations if rec else []})


def tool_estimate_cost(args: dict) -> str:
    r = models.estimate_cost(CostEstimateRequest(**{k: v for k, v in args.items()
                                                    if k in CostEstimateRequest.model_fields}))
    return _json({"models": [{"model": m.model_id, "input_tokens": m.input_tokens,
                              "total_cost": m.total_cost, "currency": m.currency,
                              "price_status": m.price_status} for m in r.models],
                  "note": "Estimates from encoding counts; not provider billing.",
                  "warnings": r.warnings[1:]})


TOOLS: dict[str, Callable[[dict], str]] = {
    "detect_language": tool_detect_language,
    "analyze_tokens": tool_analyze_tokens,
    "optimize_prompt": tool_optimize_prompt,
    "check_meaning": tool_check_meaning,
    "recommend_model": tool_recommend_model,
    "estimate_cost": tool_estimate_cost,
}


def _arguments(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        val = json.loads(raw)
        if isinstance(val, dict):
            return val
    if raw in (None, ""):
        return {}
    raise ValueError("tool arguments must be a JSON object")


def run_tool(name: str, raw_args: Any, timeout: float) -> tuple[str, str]:
    """('result'|'error', flat string)."""
    fn = TOOLS.get(name)
    if fn is None:
        return "error", f"Unknown tool '{name}'."
    try:
        args = _arguments(raw_args)
    except (ValueError, json.JSONDecodeError):
        return "error", "Invalid tool arguments: expected a JSON object."
    future = _pool.submit(fn, args)
    try:
        return "result", future.result(timeout=timeout)
    except FutureTimeout:
        return "error", f"Tool '{name}' timed out after {timeout:g} s."
    except ValidationError as exc:
        e = exc.errors()[0]
        return "error", f"Invalid arguments for '{name}': {'.'.join(map(str, e['loc']))}: {e['msg']}"
    except (ValueError, LookupError) as exc:
        return "error", f"'{name}' could not run: {exc}"
    except Exception as exc:  # noqa: BLE001 — a tool failure must not break the call
        logger.error("vapi tool %s failed: %s", name, type(exc).__name__)
        return "error", f"'{name}' failed ({type(exc).__name__})."


def tool_calls(message: dict) -> list[tuple[str, str, Any]]:
    """(tool_call_id, name, arguments) from toolCallList, falling back to toolWithToolCallList."""
    calls = []
    for c in message.get("toolCallList") or []:
        fn = c.get("function") or {}
        calls.append((str(c.get("id", "")), str(fn.get("name", "")), fn.get("arguments")))
    if not calls:
        for item in message.get("toolWithToolCallList") or []:
            c = item.get("toolCall") or {}
            fn = c.get("function") or {}
            calls.append((str(c.get("id", "")), str(fn.get("name", "")), fn.get("arguments")))
    return calls


def handle(body: dict, s: Settings) -> dict:
    message = body.get("message")
    if not isinstance(message, dict):
        raise ValueError("body must contain a 'message' object")
    mtype = str(message.get("type", ""))
    call_id = str((message.get("call") or {}).get("id", "") or "")[:64]
    if mtype != "tool-calls":
        logger.info("vapi event type=%s call=%s", mtype or "?", call_id or "-")
        return {}
    results = []
    for tool_call_id, name, args in tool_calls(message):
        start = time.perf_counter()
        kind, value = run_tool(name, args, s.vapi_tool_timeout_seconds)
        logger.info("vapi tool call=%s tool=%s outcome=%s ms=%.0f", call_id or "-", name, kind,
                    (time.perf_counter() - start) * 1000)
        results.append({"toolCallId": tool_call_id, "name": name, kind: value})
    return {"results": results}
