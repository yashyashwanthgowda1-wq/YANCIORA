"""Provider adapters (backend only; credentials never reach the frontend).

- Speech-to-text: OpenAI-compatible `POST {STT_BASE_URL}/audio/transcriptions` (multipart).
- Chat LLM: OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions`.

Both are optional. When a provider is not configured the caller gets ProviderNotConfigured and
the feature falls back to its documented non-LLM / text-input path. Nothing is simulated.
Errors never include API keys or response bodies (which may echo user content).
"""
from __future__ import annotations

import base64
import binascii
import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings

logger = logging.getLogger("redutax.providers")
STT_LANGUAGES = {"kn", "hi", "ta", "te", "en"}       # ISO 639-1 codes sent as the language hint
MAX_AUDIO_BYTES = 10 * 1024 * 1024


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderError(RuntimeError):
    """The provider failed. The message is safe to show (no keys, no content)."""


class ProviderRateLimited(ProviderError):
    """The provider answered HTTP 429. `retry_after` is its Retry-After value in seconds, if given."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _check_status(r: httpx.Response, label: str) -> None:
    if r.status_code == 200:
        return
    logger.warning("%s provider returned HTTP %s", label, r.status_code)
    if r.status_code == 429:
        raw = r.headers.get("retry-after", "")
        retry = int(raw) if raw.isdigit() else None
        hint = f" Retry after {retry} s." if retry is not None else " Try again later."
        raise ProviderRateLimited(f"{_LABELS[label]} provider rate limit reached.{hint}", retry)
    raise ProviderError(f"{_LABELS[label]} provider returned HTTP {r.status_code}.")


_LABELS = {"stt": "Speech-to-text", "llm": "LLM"}


@dataclass
class Transcript:
    text: str
    model: str | None


@dataclass
class LlmReply:
    text: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


def stt_configured(s: Settings) -> bool:
    return bool(s.stt_base_url and s.stt_api_key and s.stt_model)


def llm_configured(s: Settings) -> bool:
    return bool(s.llm_base_url and s.llm_api_key and s.llm_model)


def _client(transport: httpx.BaseTransport | None, timeout: float) -> httpx.Client:
    return httpx.Client(transport=transport, timeout=timeout)


def transcribe(s: Settings, audio_b64: str, mime_type: str, language: str | None,
               transport: httpx.BaseTransport | None = None) -> Transcript:
    if not stt_configured(s):
        raise ProviderNotConfigured("Speech-to-text is not configured on the server "
                                    "(STT_BASE_URL, STT_API_KEY, STT_MODEL).")
    try:
        audio = base64.b64decode(audio_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("audio_base64 is not valid base64") from exc
    if not audio:
        raise ValueError("audio is empty")
    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError(f"audio is larger than {MAX_AUDIO_BYTES // (1024 * 1024)} MB")
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav",
           "audio/mpeg": "mp3", "audio/mp4": "m4a"}.get(mime_type.split(";")[0].strip(), "webm")
    data = {"model": s.stt_model, "response_format": "json"}
    if language in STT_LANGUAGES:
        data["language"] = language
    try:
        with _client(transport, 60.0) as c:
            r = c.post(f"{s.stt_base_url.rstrip('/')}/audio/transcriptions",
                       headers={"Authorization": f"Bearer {s.stt_api_key}"},
                       data=data, files={"file": (f"audio.{ext}", audio, mime_type)})
    except httpx.TimeoutException as exc:
        raise ProviderError("Speech-to-text provider timed out.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"Speech-to-text provider unreachable ({type(exc).__name__}).") from exc
    _check_status(r, "stt")
    try:
        text = str(r.json()["text"])
    except (ValueError, KeyError, TypeError) as exc:
        raise ProviderError("Speech-to-text provider returned an unexpected response.") from exc
    return Transcript(text=text, model=s.stt_model)


def chat_complete(s: Settings, messages: list[dict[str, str]],
                  transport: httpx.BaseTransport | None = None) -> LlmReply:
    if not llm_configured(s):
        raise ProviderNotConfigured("No LLM provider is configured on the server "
                                    "(LLM_BASE_URL, LLM_API_KEY, LLM_MODEL).")
    try:
        with _client(transport, s.llm_timeout_seconds) as c:
            r = c.post(f"{s.llm_base_url.rstrip('/')}/chat/completions",
                       headers={"Authorization": f"Bearer {s.llm_api_key}"},
                       json={"model": s.llm_model, "messages": messages})
    except httpx.TimeoutException as exc:
        raise ProviderError("LLM provider timed out.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"LLM provider unreachable ({type(exc).__name__}).") from exc
    _check_status(r, "llm")
    try:
        body = r.json()
        text = str(body["choices"][0]["message"]["content"])
        usage = body.get("usage") or {}
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError("LLM provider returned an unexpected response.") from exc
    return LlmReply(text=text, model=str(body.get("model") or s.llm_model),
                    prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"))
