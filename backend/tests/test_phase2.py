"""Phase 2: model registry, cost (F4), recommendation (F7), pipeline (F8), chat (F9), providers.
Models below are TEST FIXTURES with made-up ids and prices — not real model data."""
import json

import httpx
import pytest

from app.core.config import Settings
from app.integrations import providers
from app.schemas import (
    AnalyzeRequest, ApplyEditsRequest, ChatAnalyzeRequest, ChatSendRequest, CostEstimateRequest, ModelSpec,
    RecommendRequest, TextEdit,
)
from app.services import chat, models, pipeline
from app.tokenizers import get_tokenizer

KN = "ದಯವಿಟ್ಟು   ವರದಿ ಕಳುಹಿಸಿ!!!!!!"
KN_DUP = "ದಯವಿಟ್ಟು   ವರದಿ ಕಳುಹಿಸಿ!!!!!! ದಯವಿಟ್ಟು ವರದಿ ಕಳುಹಿಸಿ!!!!!!"   # repeat → suggestion in safe mode


def m(mid, **kw):
    base = {"id": mid, "provider": "TestProvider", "source": "user"}
    base.update(kw)
    return ModelSpec(**base)


CHEAP = m("test-cheap", encoding="o200k_base", context_window_tokens=8000,
          pricing={"currency": "USD", "input_per_1m": 0.5, "output_per_1m": 1.5}, languages={"kn": "unknown"})
GOOD = m("test-good", encoding="cl100k_base", context_window_tokens=8000, quality_tier=4,
         pricing={"currency": "USD", "input_per_1m": 2.0, "output_per_1m": 8.0}, languages={"kn": "claimed"},
         tasks=["general", "summarization"])
NOPRICE = m("test-noprice", languages={"kn": "verified"})


@pytest.fixture(autouse=True)
def empty_registry(tmp_path, monkeypatch):
    p = tmp_path / "models.yaml"
    p.write_text("models: []\n", encoding="utf-8")
    monkeypatch.setattr(models, "registry_path", lambda: p)
    return p


def write_registry(path, entries):
    import yaml
    path.write_text(yaml.safe_dump({"models": entries}), encoding="utf-8")


# ---------- registry ----------
def test_shipped_registry_is_empty_and_valid(monkeypatch):
    monkeypatch.setattr(models, "registry_path", lambda: models.DEFAULT_REGISTRY)
    reg, _ = models.load_registry()
    assert reg == []
    assert "empty" in models.registry_response().warnings[-1]


def test_registry_entries_loaded_and_marked_registry(empty_registry):
    write_registry(empty_registry, [{"id": "reg-1", "provider": "P", "source": "user",
                                     "pricing": {"currency": "usd", "input_per_1m": 1, "output_per_1m": 2}}])
    reg, warnings = models.load_registry()
    assert reg[0].source == "registry" and reg[0].pricing.currency == "USD"
    assert any("not verified" in w for w in warnings)


@pytest.mark.parametrize("entries,msg", [
    ([{"id": "a"}], "entry 1"),
    ([{"id": "a", "provider": "P"}, {"id": "a", "provider": "P"}], "duplicate"),
    ([{"id": "a", "provider": "P", "languages": {"kn": "great"}}], "entry 1"),
])
def test_invalid_registry_rejected(empty_registry, entries, msg):
    write_registry(empty_registry, entries)
    with pytest.raises(models.RegistryError, match=msg):
        models.load_registry()


# ---------- Feature 4: cost ----------
def test_cost_math_uses_real_token_counts():
    r = models.estimate_cost(CostEstimateRequest(text="Hello world", custom_models=[GOOD], expected_output_tokens=1000))
    c = r.models[0]
    tin = get_tokenizer("cl100k_base").count("Hello world")
    assert c.input_tokens == tin and c.encoding_used == "cl100k_base" and c.encoding_status == "model_encoding"
    assert c.input_cost == pytest.approx(tin / 1e6 * 2.0) and c.output_cost == pytest.approx(1000 / 1e6 * 8.0)
    assert c.total_cost == pytest.approx(c.input_cost + c.output_cost)
    assert c.count_status == "estimate" and c.price_status == "user_entered"
    assert any("not provider billing" in w or "provider billing" in w for w in r.warnings)


def test_cost_original_vs_optimized_savings():
    r = models.estimate_cost(CostEstimateRequest(text=KN, optimized_text="ದಯವಿಟ್ಟು ವರದಿ ಕಳುಹಿಸಿ!", custom_models=[CHEAP]))
    c = r.models[0]
    assert c.optimized_input_tokens < c.input_tokens
    assert c.savings == pytest.approx(c.total_cost - c.optimized_total_cost) and c.savings_pct > 0


def test_cost_missing_price_and_fallback_encoding():
    r = models.estimate_cost(CostEstimateRequest(text="hi", custom_models=[NOPRICE], fallback_encoding="cl100k_base"))
    c = r.models[0]
    assert c.total_cost is None and c.price_status == "missing"
    assert c.encoding_status == "fallback_encoding" and c.encoding_used == "cl100k_base"
    assert any("No price configured" in w for w in c.warnings)


def test_cost_registry_price_status(empty_registry):
    write_registry(empty_registry, [
        {"id": "v", "provider": "P", "pricing": {"currency": "USD", "input_per_1m": 1, "output_per_1m": 1,
                                                 "verified_at": "2026-11-01", "source_url": "https://x"}},
        {"id": "u", "provider": "P", "pricing": {"currency": "EUR", "input_per_1m": 1, "output_per_1m": 1}}])
    r = models.estimate_cost(CostEstimateRequest(text="hi", model_ids=["v", "u", "missing-id"]))
    assert {c.model_id: c.price_status for c in r.models} == {"v": "verified", "u": "unverified"}
    assert r.unknown_model_ids == ["missing-id"] and any("different currencies" in w for w in r.warnings)


def test_cost_context_window_warning():
    small = m("small", encoding="o200k_base", context_window_tokens=5,
              pricing={"currency": "USD", "input_per_1m": 1, "output_per_1m": 1})
    r = models.estimate_cost(CostEstimateRequest(text="one two three four five six", custom_models=[small],
                                                 expected_output_tokens=10))
    assert any("exceeds the configured context window" in w for w in r.models[0].warnings)


def test_cost_no_models():
    r = models.estimate_cost(CostEstimateRequest(text="hi"))
    assert r.models == [] and any("No models to price" in w for w in r.warnings)


# ---------- Feature 7: recommendation ----------
def rec(**kw):
    base = {"text": "ನಮಸ್ಕಾರ", "language": "kn", "custom_models": [CHEAP, GOOD, NOPRICE], "expected_output_tokens": 100}
    base.update(kw)
    return models.recommend(RecommendRequest(**base))


def test_lowest_cost_preference():
    r = rec(cost_preference="lowest")
    assert r.recommended.model_id == "test-cheap" and r.recommended.rank == 1
    assert [c.model_id for c in r.alternatives] == ["test-good", "test-noprice"]   # unpriced last
    assert "lowest estimated cost" in r.explanation


def test_quality_preference():
    assert rec(cost_preference="quality").recommended.model_id == "test-good"


def test_balanced_prefers_documented_language_support():
    assert rec(cost_preference="balanced").recommended.model_id == "test-noprice"   # verified support


def test_language_requirement_excludes_with_reason():
    r = rec(require_language_support="claimed")
    assert {c.model_id for c in r.excluded} == {"test-cheap"}
    assert "needs claimed or verified" in r.excluded[0].exclusions[0]


def test_unsupported_language_always_excluded():
    bad = m("bad", languages={"kn": "unsupported"})
    r = rec(custom_models=[bad])
    assert r.recommended is None and "unsupported" in r.excluded[0].exclusions[0]
    assert "No model meets every requirement" in r.explanation


def test_context_task_and_quality_constraints():
    r = rec(min_context_tokens=16000)
    assert r.recommended is None and all(c.exclusions for c in r.excluded)
    r = rec(task_type="coding")
    assert "test-good" in {c.model_id for c in r.excluded}           # documented tasks exclude coding
    assert any("not documented" in lim for c in r.alternatives + ([r.recommended] if r.recommended else [])
               for lim in c.limitations)
    r = rec(min_quality_tier=3)
    assert r.recommended.model_id == "test-good" and len(r.alternatives) == 0


def test_locked_model_never_switched():
    r = rec(cost_preference="lowest", locked_model_id="test-good")
    assert r.locked and r.recommended.model_id == "test-good" and "locked by you" in r.explanation
    r2 = rec(require_language_support="verified", locked_model_id="test-cheap")
    assert r2.recommended.model_id == "test-cheap" and any("stays selected because it is locked" in w for w in r2.warnings)


def test_no_models_configured_explanation():
    r = rec(custom_models=[])
    assert r.recommended is None and "does not invent model data" in r.explanation


# ---------- pipeline (Feature 8 text workflow) ----------
def test_pipeline_without_models():
    a = pipeline.analyze(AnalyzeRequest(text=KN_DUP, language="kn"))
    assert a.language == "kn" and a.recommendation is None and a.cost is None
    assert a.requires_review and a.optimization.suggestions and "Add models" in a.next_step


def test_pipeline_with_models_and_approval_flow():
    a = pipeline.analyze(AnalyzeRequest(text=KN_DUP, language="kn", custom_models=[CHEAP], expected_output_tokens=50))
    assert a.recommendation.recommended.model_id == "test-cheap" and a.cost.models[0].model_id == "test-cheap"
    edits = [TextEdit(start=s.start, end=s.end, after=s.after) for s in a.optimization.suggestions]
    r = pipeline.apply_edits(ApplyEditsRequest(original=KN_DUP, edits=edits, language="kn"))
    assert r.applied_count == len(edits) and r.allowed and r.tokens_after <= r.tokens_before
    assert r.meaning_check.status == "at_risk"          # Kannada lists unreviewed → still flagged


def test_apply_rejects_bad_edits_and_flags_changed():
    with pytest.raises(pipeline.EditError, match="outside"):
        pipeline.apply_edits(ApplyEditsRequest(original="abc", edits=[TextEdit(start=1, end=9, after="")]))
    with pytest.raises(pipeline.EditError, match="overlap"):
        pipeline.apply_edits(ApplyEditsRequest(original="abcdef", edits=[TextEdit(start=0, end=3, after=""),
                                                                         TextEdit(start=2, end=4, after="")]))
    r = pipeline.apply_edits(ApplyEditsRequest(original="Pay 500 now", edits=[TextEdit(start=4, end=7, after="900")]))
    assert not r.allowed and r.meaning_check.status == "changed" and "do not use" in r.warnings[0]


# ---------- providers (mock transport only; no real calls) ----------
STT = Settings(stt_base_url="https://stt.test/v1", stt_api_key="sk-test-stt", stt_model="test-stt")
LLM = Settings(llm_base_url="https://llm.test/v1", llm_api_key="sk-test-llm", llm_model="test-llm",
               llm_provider_name="TestLLM")


def test_transcribe_success_sends_auth_and_language():
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "ನಮಸ್ಕಾರ"})

    t = providers.transcribe(STT, "AAECAwQF", "audio/webm", "kn", transport=httpx.MockTransport(handler))
    assert t.text == "ನಮಸ್ಕಾರ" and seen["auth"] == "Bearer sk-test-stt"
    assert seen["url"] == "https://stt.test/v1/audio/transcriptions" and b'name="language"' in seen["body"]


@pytest.mark.parametrize("handler,exc,msg", [
    (lambda r: httpx.Response(401, json={"error": "bad key sk-test-stt"}), providers.ProviderError, "HTTP 401"),
    (lambda r: httpx.Response(200, json={"nope": 1}), providers.ProviderError, "unexpected"),
])
def test_transcribe_errors_never_leak_key(handler, exc, msg):
    with pytest.raises(exc, match=msg) as e:
        providers.transcribe(STT, "AAECAwQF", "audio/webm", None, transport=httpx.MockTransport(handler))
    assert "sk-test" not in str(e.value)


def test_transcribe_timeout_and_validation():
    def boom(request):
        raise httpx.ReadTimeout("slow")

    with pytest.raises(providers.ProviderError, match="timed out"):
        providers.transcribe(STT, "AAECAwQF", "audio/webm", None, transport=httpx.MockTransport(boom))
    with pytest.raises(ValueError, match="base64"):
        providers.transcribe(STT, "not base64!!", "audio/webm", None)
    with pytest.raises(providers.ProviderNotConfigured):
        providers.transcribe(Settings(), "AAECAwQF", "audio/webm", None)


def test_llm_success_and_usage():
    def handler(request):
        body = json.loads(request.content)
        assert body["model"] == "test-llm" and body["messages"][-1]["content"] == "hello"
        return httpx.Response(200, json={"model": "test-llm-0", "choices": [{"message": {"content": "hi there"}}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}})

    r = providers.chat_complete(LLM, [{"role": "user", "content": "hello"}], transport=httpx.MockTransport(handler))
    assert (r.text, r.model, r.total_tokens) == ("hi there", "test-llm-0", 8)


def test_llm_errors():
    with pytest.raises(providers.ProviderNotConfigured):
        providers.chat_complete(Settings(), [])
    with pytest.raises(providers.ProviderError, match="HTTP 500"):
        providers.chat_complete(LLM, [], transport=httpx.MockTransport(lambda r: httpx.Response(500)))


def test_provider_rate_limit_is_distinct_and_safe():
    limited = httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "12"}, text="quota for sk-x"))
    with pytest.raises(providers.ProviderRateLimited) as e:
        providers.chat_complete(LLM, [], transport=limited)
    assert e.value.retry_after == 12 and "Retry after 12 s" in str(e.value) and "sk-" not in str(e.value)
    no_header = httpx.MockTransport(lambda r: httpx.Response(429))
    with pytest.raises(providers.ProviderRateLimited) as e2:
        providers.transcribe(STT, "AAECAwQF", "audio/webm", None, transport=no_header)
    assert e2.value.retry_after is None and "Speech-to-text" in str(e2.value)


def test_chat_send_failure_leaves_history_unchanged():
    a = chat.analyze_turn(ChatAnalyzeRequest(text="question", language="en"), Settings())
    before = len(chat.history(a.session_id).history)
    with pytest.raises(providers.ProviderRateLimited):
        chat.send_turn(a.session_id, ChatSendRequest(text="question"), LLM,
                       transport=httpx.MockTransport(lambda r: httpx.Response(429)))
    assert len(chat.history(a.session_id).history) == before


# ---------- Feature 9: chat ----------
def test_chat_analysis_mode_and_history():
    r = chat.analyze_turn(ChatAnalyzeRequest(text="Please   pay ₹500 by 5 pm!!!", language="en"), Settings())
    assert r.mode == "analysis" and not r.llm_available
    assert r.reply.startswith(chat.ANALYSIS_NOTE) and "Tokens" in r.reply
    assert [t.kind for t in r.history] == ["message", "analysis"]
    r2 = chat.analyze_turn(ChatAnalyzeRequest(text="Second", language="en", session_id=r.session_id), Settings())
    assert r2.session_id == r.session_id and len(r2.history) == 4


def test_chat_send_uses_llm_with_context():
    a = chat.analyze_turn(ChatAnalyzeRequest(text="first question", language="en"), Settings())
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["messages"])
        return httpx.Response(200, json={"choices": [{"message": {"content": f"answer {len(calls)}"}}]})

    t = httpx.MockTransport(handler)
    r1 = chat.send_turn(a.session_id, ChatSendRequest(text="first question"), LLM, transport=t)
    r2 = chat.send_turn(a.session_id, ChatSendRequest(text="follow up"), LLM, transport=t)
    assert r1.reply == "answer 1" and r2.reply == "answer 2" and r1.provider == "TestLLM"
    roles = [msg["role"] for msg in calls[1]]
    assert roles == ["system", "user", "assistant", "user"]           # prior turn carried as context
    assert r2.usage is None                                            # provider gave no usage


def test_chat_unknown_session():
    with pytest.raises(chat.SessionNotFound):
        chat.history("no-such-session")


def test_settings_hide_provider_secrets():
    s = Settings(stt_api_key="sk-a", llm_api_key="sk-b", vapi_webhook_secret="vs", vapi_hmac_secret="hs",
                 llm_base_url="https://user:pw@llm.test/v1")
    d = str(s.safe_dict())
    for secret in ("sk-a", "sk-b", "'vs'", "'hs'", "pw@", "llm.test"):
        assert secret not in d
