"""Feature 10 — Vapi webhook with mocked Vapi events (payload shapes from Vapi's custom-tools docs).
No real Vapi account or call is involved; a live call has NOT been verified."""
import hashlib
import hmac
import json
import logging
import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.integrations import vapi  # noqa: E402
from app.main import create_app  # noqa: E402

SECRET = "test-webhook-secret"
HSECRET = "test-hmac-secret"
SETTINGS = Settings(vapi_webhook_secret=SECRET, vapi_hmac_secret=HSECRET, vapi_tool_timeout_seconds=5)


def client(settings=SETTINGS):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def tool_call_body(*calls, call_id="call-123"):
    return {"message": {"type": "tool-calls", "call": {"id": call_id},
                        "toolCallList": [{"id": f"tc-{i}", "type": "function",
                                          "function": {"name": n, "arguments": a}} for i, (n, a) in enumerate(calls)]}}


def post(c, body, headers=None):
    raw = json.dumps(body, ensure_ascii=False).encode()
    return c.post("/api/vapi/webhook", content=raw,
                  headers={"Content-Type": "application/json", **(headers or {"Authorization": f"Bearer {SECRET}"})})


# ---------- authentication ----------
def test_refuses_all_requests_without_configured_secret():
    r = post(client(Settings()), tool_call_body(("detect_language", {"text": "hi"})))
    assert r.status_code == 503 and r.json()["error"]["code"] == "vapi_not_configured"


@pytest.mark.parametrize("headers", [
    {}, {"Authorization": "Bearer wrong"}, {"X-Vapi-Secret": "wrong"}, {"Authorization": SECRET},
])
def test_rejects_bad_credentials(headers):
    r = post(client(), tool_call_body(("detect_language", {"text": "hi"})), headers=headers or {"X": "y"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_accepts_bearer_and_legacy_header():
    assert post(client(), tool_call_body(("detect_language", {"text": "hi"}))).status_code == 200
    assert post(client(), tool_call_body(("detect_language", {"text": "hi"})),
                headers={"X-Vapi-Secret": SECRET}).status_code == 200


def _hmac_headers(raw: bytes, ts: str | None):
    payload = (ts.encode() + b"." + raw) if ts else raw
    return {"x-signature": hmac.new(HSECRET.encode(), payload, hashlib.sha256).hexdigest(),
            **({"x-timestamp": ts} if ts else {})}


def test_hmac_signature_with_timestamp_and_replay_window():
    raw = b'{"message":{"type":"status-update"}}'
    now = time.time()
    assert vapi.verify(_hmac_headers(raw, str(int(now))), raw, SETTINGS, now=now)
    assert vapi.verify(_hmac_headers(raw, str(int(now * 1000))), raw, SETTINGS, now=now)   # milliseconds
    assert not vapi.verify(_hmac_headers(raw, str(int(now) - 3600)), raw, SETTINGS, now=now)  # replay
    tampered = _hmac_headers(raw, str(int(now)))
    assert not vapi.verify(tampered, raw + b" ", SETTINGS, now=now)
    s = Settings(vapi_hmac_secret=HSECRET)
    # A body-only signature (no timestamp header) has no replay protection and is refused.
    assert not vapi.verify(_hmac_headers(raw, None), raw, s)
    assert not vapi.verify({"x-signature": _hmac_headers(raw, None)["x-signature"], "x-timestamp": "abc"}, raw, s)


def test_hmac_through_the_endpoint():
    body = tool_call_body(("detect_language", {"text": "ನಮಸ್ಕಾರ"}))
    raw = json.dumps(body, ensure_ascii=False).encode()
    r = client(Settings(vapi_hmac_secret=HSECRET)).post(
        "/api/vapi/webhook", content=raw,
        headers={"Content-Type": "application/json", **_hmac_headers(raw, str(int(time.time())))})
    assert r.status_code == 200 and json.loads(r.json()["results"][0]["result"])["language"] == "kn"


# ---------- tools ----------
def results(resp):
    assert resp.status_code == 200
    return {x["toolCallId"]: x for x in resp.json()["results"]}


def test_all_six_tools_return_flat_string_results():
    body = tool_call_body(
        ("detect_language", {"text": "ನಾನು ನಾಳೆ ಬರುವುದಿಲ್ಲ"}),
        ("analyze_tokens", {"text": "नमस्ते दोस्त", "tokenizer": "cl100k_base"}),
        ("optimize_prompt", {"text": "Please   pay ₹500 by 5 pm!!!", "language": "en"}),
        ("check_meaning", {"original": "Do not pay ₹500", "candidate": "Pay ₹500", "language": "en"}),
        ("recommend_model", {"text": "வணக்கம்", "language": "ta"}),
        ("estimate_cost", {"text": "నమస్కారం", "expected_output_tokens": 50}),
    )
    out = results(post(client(), body))
    assert set(out) == {f"tc-{i}" for i in range(6)}
    parsed = {k: json.loads(v["result"]) for k, v in out.items()}      # every result is a flat JSON string
    assert parsed["tc-0"]["language"] == "kn"
    assert parsed["tc-1"]["token_count"] > 0 and "not provider billing" in parsed["tc-1"]["note"]
    assert parsed["tc-2"]["changed"] and parsed["tc-2"]["meaning_check"] == "preserved"
    assert parsed["tc-3"]["status"] == "changed" and parsed["tc-3"]["missing"]
    assert parsed["tc-4"]["recommended"] is None and "does not invent" in parsed["tc-4"]["explanation"]
    assert parsed["tc-5"]["models"] == []


def test_string_arguments_and_tool_with_tool_call_list_fallback():
    body = {"message": {"type": "tool-calls", "toolWithToolCallList": [
        {"function": {"name": "detect_language"},
         "toolCall": {"id": "x1", "function": {"name": "detect_language", "arguments": '{"text": "hello"}'}}}]}}
    out = results(post(client(), body))
    assert json.loads(out["x1"]["result"])["script"] == "Latn"


@pytest.mark.parametrize("name,args,msg", [
    ("no_such_tool", {}, "Unknown tool"),
    ("detect_language", "not json", "Invalid tool arguments"),
    ("detect_language", {"text": "  "}, "could not run"),
    ("analyze_tokens", {"text": "hi", "tokenizer": "nope"}, "could not run"),
    ("recommend_model", {"text": "hi", "language": "fr"}, "Invalid arguments"),
])
def test_tool_errors_are_reported_per_call_with_http_200(name, args, msg):
    out = results(post(client(), tool_call_body((name, args))))
    assert "result" not in out["tc-0"] and msg in out["tc-0"]["error"]


def test_tool_timeout(monkeypatch):
    def slow(args):
        time.sleep(1.0)
        return "late"

    monkeypatch.setitem(vapi.TOOLS, "detect_language", slow)
    out = results(post(client(Settings(vapi_webhook_secret=SECRET, vapi_tool_timeout_seconds=0.2)),
                       tool_call_body(("detect_language", {"text": "hi"}))))
    assert "timed out" in out["tc-0"]["error"]


# ---------- other events, validation, logging ----------
@pytest.mark.parametrize("mtype", ["status-update", "end-of-call-report", "transcript", "conversation-update"])
def test_non_tool_events_acknowledged(mtype):
    r = post(client(), {"message": {"type": mtype, "call": {"id": "c1"}, "transcript": "secret words"}})
    assert r.status_code == 200 and r.json() == {}


@pytest.mark.parametrize("raw,status", [(b"not json", 422), (b'{"no_message": 1}', 422), (b"[1,2]", 422)])
def test_invalid_payloads(raw, status):
    r = client().post("/api/vapi/webhook", content=raw,
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {SECRET}"})
    assert r.status_code == status and r.json()["error"]["code"] == "invalid_request"


def test_oversized_body_rejected():
    r = client().post("/api/vapi/webhook", content=b"x" * (vapi.MAX_BODY_BYTES + 1),
                      headers={"Authorization": f"Bearer {SECRET}"})
    assert r.status_code == 413


def test_logs_contain_no_caller_content(caplog):
    caplog.set_level(logging.INFO, logger="redutax.vapi")
    post(client(), tool_call_body(("optimize_prompt", {"text": "MY PRIVATE SENTENCE 9876"})))
    post(client(), {"message": {"type": "transcript", "transcript": "MY PRIVATE TRANSCRIPT"}})
    logs = " ".join(r.getMessage() for r in caplog.records)
    assert "call-123" in logs and "optimize_prompt" in logs
    assert "PRIVATE" not in logs and "9876" not in logs and SECRET not in logs


def test_status_endpoint_never_claims_live_call():
    body = client().get("/api/vapi/status").json()
    assert body["auth_configured"] and body["live_call_verified"] is False
    assert body["tools"] == sorted(vapi.TOOLS) and body["webhook_path"] == "/api/vapi/webhook"
    assert SECRET not in json.dumps(body)


# ---------- assistant configuration stays in sync with the backend ----------
def test_assistant_config_matches_backend_tools():
    from pathlib import Path

    from app.schemas import CostEstimateRequest, RecommendRequest

    cfg = json.loads((Path(__file__).resolve().parents[2] / "config/vapi/redutax-assistant.json").read_text(encoding="utf-8"))
    assert cfg["name"] == "REDUTAX Indic AI Assistant"
    assert cfg["metadata"]["supportedLanguages"] == ["kn", "hi", "ta", "te", "en"]
    assert cfg["metadata"]["liveCallVerified"] is False
    tools = {t["function"]["name"]: t for t in cfg["model"]["tools"]}
    assert set(tools) == set(vapi.TOOLS)
    for t in tools.values():
        assert t["type"] == "function" and t["server"]["url"].endswith(vapi.WEBHOOK_PATH)
        assert t["server"]["url"].startswith("<PUBLIC_BACKEND_URL>")       # placeholder, no real URL
    assert set(tools["recommend_model"]["function"]["parameters"]["properties"]) <= set(RecommendRequest.model_fields)
    assert set(tools["estimate_cost"]["function"]["parameters"]["properties"]) <= set(CostEstimateRequest.model_fields)
    raw = json.dumps(cfg)
    assert "credentialId" in raw and "cred_" not in raw and "sk-" not in raw   # no real credential ids or keys


def test_assistant_config_tool_payloads_run_through_webhook():
    """Every tool, called with only its declared required arguments, returns a result."""
    from pathlib import Path

    cfg = json.loads((Path(__file__).resolve().parents[2] / "config/vapi/redutax-assistant.json").read_text(encoding="utf-8"))
    samples = {"text": "ನಮಸ್ಕಾರ", "original": "Pay ₹500", "candidate": "Pay ₹500", "language": "kn"}
    calls = []
    for t in cfg["model"]["tools"]:
        params = t["function"]["parameters"]
        calls.append((t["function"]["name"], {k: samples[k] for k in params["required"]}))
    out = results(post(client(), tool_call_body(*calls)))
    assert all("result" in v for v in out.values()), out


# ---------- integration-readiness audit (2026-11-21): Vapi OpenAPI spec + response precedence ----------
def test_response_precedence_unconfigured_unauthorized_invalid_ok():
    """413 (too large) -> 503 (no secret on the server) -> 401 (bad/missing credential) -> 422 -> 200."""
    good = tool_call_body(("detect_language", {"text": "hi"}))
    # No secret configured: refused with 503 even when a credential is sent.
    assert post(client(Settings()), good).status_code == 503
    assert post(client(Settings()), good, headers={"X-Vapi-Secret": "anything"}).status_code == 503
    # Secret configured: missing or wrong credential -> 401.
    only_bearer = Settings(vapi_webhook_secret=SECRET)
    assert post(client(only_bearer), good, headers={"X": "y"}).status_code == 401
    assert post(client(only_bearer), good, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert post(client(only_bearer), good, headers={"Authorization": SECRET}).status_code == 401  # prefix missing
    # Authenticated but malformed -> 422; authenticated and valid -> 200.
    c = client(only_bearer)
    bad = c.post("/api/vapi/webhook", content=b"[1,2]",
                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {SECRET}"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "invalid_request"
    assert post(c, good).status_code == 200


def test_hmac_endpoint_rejects_missing_timestamp_and_wrong_secret():
    body = tool_call_body(("detect_language", {"text": "hi"}))
    raw = json.dumps(body).encode()
    c = client(Settings(vapi_hmac_secret=HSECRET))
    no_ts = c.post("/api/vapi/webhook", content=raw, headers={"Content-Type": "application/json",
                                                               **_hmac_headers(raw, None)})
    assert no_ts.status_code == 401
    ts = str(int(time.time()))
    wrong = hmac.new(b"other-secret", ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    r = c.post("/api/vapi/webhook", content=raw, headers={"Content-Type": "application/json",
                                                           "x-signature": wrong, "x-timestamp": ts})
    assert r.status_code == 401


def test_spec_shaped_payload_string_arguments_both_lists_and_name():
    """Vapi OpenAPI spec: ToolCallFunction.arguments is a string; ServerMessageToolCalls carries
    BOTH toolCallList and toolWithToolCallList; ToolCallResult requires toolCallId and name."""
    call = {"id": "call_abc", "type": "function",
            "function": {"name": "detect_language", "arguments": json.dumps({"text": "ನಮಸ್ಕಾರ"})}}
    body = {"message": {"type": "tool-calls", "timestamp": 1763700000000, "call": {"id": "c-1"},
                        "toolCallList": [call],
                        "toolWithToolCallList": [{"type": "function", "function": {"name": "detect_language"},
                                                  "server": {"url": "https://example.invalid/api/vapi/webhook"},
                                                  "toolCall": call}]}}
    r = post(client(), body)
    assert r.status_code == 200
    res = r.json()["results"]
    assert len(res) == 1                                                # not duplicated across both lists
    assert res[0]["toolCallId"] == "call_abc" and res[0]["name"] == "detect_language"
    assert isinstance(res[0]["result"], str) and "\n" not in res[0]["result"]   # flat, single-line string
    assert json.loads(res[0]["result"])["language"] == "kn"
    err = results(post(client(), tool_call_body(("no_such_tool", {}))))["tc-0"]
    assert err["name"] == "no_such_tool" and "error" in err and "result" not in err


def test_tools_run_without_any_llm_or_stt_provider(monkeypatch):
    from app.integrations import providers

    def forbidden(*a, **k):
        raise AssertionError("a Vapi tool must not call an external provider")
    monkeypatch.setattr(providers, "chat_complete", forbidden)
    monkeypatch.setattr(providers, "transcribe", forbidden)
    s = Settings(vapi_webhook_secret=SECRET)                            # no LLM_*, no STT_*
    assert not providers.llm_configured(s) and not providers.stt_configured(s)
    body = tool_call_body(("detect_language", {"text": "नमस्ते"}), ("analyze_tokens", {"text": "नमस्ते"}),
                          ("optimize_prompt", {"text": "Please   pay ₹500!!!"}),
                          ("check_meaning", {"original": "a 5", "candidate": "a 5"}),
                          ("recommend_model", {"text": "x", "language": "hi"}), ("estimate_cost", {"text": "x"}))
    out = results(post(client(s), body))
    assert all("result" in v for v in out.values()), out


def test_assistant_tool_schemas_match_backend_contracts():
    """Every declared property and enum value of the six tool definitions is accepted by the backend,
    and the enums equal the backend's allowed values."""
    import typing
    from pathlib import Path

    from app.schemas import CostPreference, LanguageCode, TaskType

    cfg = json.loads((Path(__file__).resolve().parents[2] / "config/vapi/redutax-assistant.json").read_text(encoding="utf-8"))
    tools = {t["function"]["name"]: t["function"]["parameters"] for t in cfg["model"]["tools"]}
    langs = set(typing.get_args(LanguageCode))
    assert set(tools["recommend_model"]["properties"]["language"]["enum"]) == langs
    for name in ("analyze_tokens", "optimize_prompt", "check_meaning"):
        assert set(tools[name]["properties"]["language"]["enum"]) == langs | {"auto"}
    assert set(tools["recommend_model"]["properties"]["task_type"]["enum"]) == set(typing.get_args(TaskType))
    assert set(tools["recommend_model"]["properties"]["cost_preference"]["enum"]) == set(typing.get_args(CostPreference))
    for name in ("analyze_tokens", "optimize_prompt"):
        assert set(tools[name]["properties"]["tokenizer"]["enum"]) == {"cl100k_base", "o200k_base"}
    for name, params in tools.items():
        assert params["type"] == "object" and set(params["required"]) <= set(params["properties"])

    sample = {"text": "ನಮಸ್ಕಾರ ₹500", "original": "Pay ₹500", "candidate": "Pay ₹500", "optimized_text": "Pay ₹500",
              "model_ids": [], "expected_output_tokens": 20}
    calls = []
    for name, params in tools.items():
        base = {k: sample[k] for k in params["properties"] if k in sample}
        if name == "recommend_model":
            base["language"] = "kn"
        calls.append((name, base))                                     # all non-enum properties at once
        for prop, spec in params["properties"].items():
            for value in spec.get("enum", []):                         # every enum value individually
                calls.append((name, {**base, prop: value}))
    out = results(post(client(), tool_call_body(*calls)))
    errors = {k: v for k, v in out.items() if "error" in v}
    assert not errors, errors
    for i, (name, args) in enumerate(calls):                           # declared args actually reach the service
        if name == "analyze_tokens" and "tokenizer" in args:
            assert args["tokenizer"] in json.loads(out[f"tc-{i}"]["result"])["tokenizer"]
        if name == "analyze_tokens" and args.get("language", "auto") != "auto":
            assert json.loads(out[f"tc-{i}"]["result"])["language"] == args["language"]


def test_assistant_config_uses_only_current_vapi_fields():
    """Keys checked against Vapi's OpenAPI spec (CreateAssistantDTO, OpenAIModel, CreateFunctionToolDTO,
    Server, OpenAIFunction) on 2026-11-21; silenceTimeoutSeconds is no longer an assistant field."""
    import re
    from pathlib import Path

    cfg = json.loads((Path(__file__).resolve().parents[2] / "config/vapi/redutax-assistant.json").read_text(encoding="utf-8"))
    assert set(cfg) <= {"name", "firstMessage", "metadata", "transcriber", "voice", "model", "server",
                        "serverMessages", "endCallMessage", "maxDurationSeconds"}
    assert len(cfg["name"]) <= 40 and 10 <= cfg["maxDurationSeconds"] <= 43200
    assert set(cfg["model"]) <= {"provider", "model", "temperature", "messages", "tools"}
    assert set(cfg["serverMessages"]) <= {"tool-calls", "status-update", "end-of-call-report", "transcript",
                                          "hang", "conversation-update", "speech-update"}
    for t in cfg["model"]["tools"]:
        assert set(t) <= {"type", "function", "server", "async", "messages"} and t["type"] == "function"
        assert set(t["server"]) <= {"url", "credentialId", "headers", "timeoutSeconds"}
        assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", t["function"]["name"])
    assert set(cfg["server"]) <= {"url", "credentialId", "headers", "timeoutSeconds"}


def test_detect_language_explains_unreadable_text():
    """Garbled transcripts (e.g. '????') get an actionable note instead of a silent null."""
    out = results(post(client(), tool_call_body(("detect_language", {"text": "????"}))))
    r = json.loads(out["tc-0"]["result"])
    assert r["script"] is None and r["language"] is None and "ask the caller to repeat" in r["note"]
