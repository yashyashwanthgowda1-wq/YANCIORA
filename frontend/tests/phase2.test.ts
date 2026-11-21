import { afterEach, describe, expect, it, vi } from "vitest";
import { api, errorHint } from "@/lib/api/client";
import { loadCustomModels, saveCustomModels } from "@/lib/models";
import type { ModelSpec } from "@/lib/api/types";

// Phase 2 (Features 4, 7, 8, 9, 10): client paths/methods, error hints, user-model storage.

function recordingFetch(status: number, body: unknown) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  const f = vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method ?? "GET", body: init.body ? JSON.parse(String(init.body)) : undefined });
    return new Response(body === null ? null : JSON.stringify(body), { status });
  }) as unknown as typeof fetch;
  return { f, calls };
}

describe("Phase 2 API client", () => {
  it("posts cost, recommend, pipeline and chat requests to the right paths", async () => {
    const { f, calls } = recordingFetch(200, { ok: true });
    const o = { fetchImpl: f };
    await api.costEstimate({ text: "x", expected_output_tokens: 10 }, o);
    await api.recommend({ text: "x", language: "kn" }, o);
    await api.analyze({ text: "x" }, o);
    await api.applyEdits({ original: "x", edits: [] }, o);
    await api.transcribe({ audio_base64: "AA==", mime_type: "audio/webm" }, o);
    await api.chat({ text: "x" }, o);
    await api.chatSend("a/b", { text: "x" }, o);
    expect(calls.map((c) => `${c.method} ${new URL(c.url).pathname}`)).toEqual([
      "POST /api/cost/estimate", "POST /api/models/recommend", "POST /api/pipeline/analyze",
      "POST /api/pipeline/apply", "POST /api/voice/transcribe", "POST /api/chat", "POST /api/chat/a%2Fb/send",
    ]);
    expect(calls[0]?.body).toEqual({ text: "x", expected_output_tokens: 10 });
  });

  it("reads status endpoints with GET and deletes chat sessions (204, no body)", async () => {
    const ok = recordingFetch(200, { ok: true });
    await api.models({ fetchImpl: ok.f });
    await api.integrations({ fetchImpl: ok.f });
    await api.vapiStatus({ fetchImpl: ok.f });
    expect(ok.calls.map((c) => `${c.method} ${new URL(c.url).pathname}`))
      .toEqual(["GET /api/models", "GET /api/integrations/status", "GET /api/vapi/status"]);
    const del = recordingFetch(204, null);
    await expect(api.chatDelete("s1", { fetchImpl: del.f })).resolves.toBeUndefined();
    expect(del.calls[0]?.method).toBe("DELETE");
  });

  it("surfaces llm_not_configured as an ApiError with a hint", async () => {
    const { f } = recordingFetch(503, { error: { code: "llm_not_configured", message: "No LLM provider is configured." } });
    await expect(api.chatSend("s1", { text: "x" }, { fetchImpl: f }))
      .rejects.toMatchObject({ status: 503, code: "llm_not_configured" });
    for (const code of ["stt_not_configured", "llm_not_configured", "provider_error", "provider_rate_limited", "registry_invalid"]) {
      expect(errorHint(code)).toBeTruthy();
    }
    expect(errorHint("llm_not_configured")).not.toMatch(/sk-|key=/i);
  });
});

describe("user-entered models (browser storage)", () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  function stubWindow() {
    const store = new Map<string, string>();
    const events: string[] = [];
    vi.stubGlobal("window", {
      localStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); } },
      dispatchEvent: (e: Event) => { events.push(e.type); return true; },
    });
    return { store, events };
  }

  const spec = { id: "test-model", provider: "TestProvider", encoding: "o200k_base", source: "registry" } as unknown as ModelSpec;

  it("saves models labelled source=user and loads them back", () => {
    const { events } = stubWindow();
    saveCustomModels([spec]);
    const loaded = loadCustomModels();
    expect(loaded).toHaveLength(1);
    expect(loaded[0]).toMatchObject({ id: "test-model", source: "user" });
    expect(events).toEqual(["redutax:custom-models"]);
  });

  it("ignores corrupt or malformed storage", () => {
    const { store } = stubWindow();
    store.set("redutax:custom-models", "{not json");
    expect(loadCustomModels()).toEqual([]);
    store.set("redutax:custom-models", JSON.stringify([{ id: 1 }, { id: "ok", provider: "P" }, null]));
    expect(loadCustomModels().map((m) => m.id)).toEqual(["ok"]);
  });

  it("returns [] when storage is unavailable", () => {
    vi.stubGlobal("window", { get localStorage() { throw new Error("blocked"); } });
    expect(loadCustomModels()).toEqual([]);
  });
});
