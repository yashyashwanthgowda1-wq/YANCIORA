import { describe, expect, it, vi } from "vitest";
import { api, ApiError, buildQuery, request } from "@/lib/api/client";
import { estimateCost, validateCostInput } from "@/lib/cost";
import { csvCell, toCsv } from "@/lib/csv";
import { fmtInt, fmtPct, fmtRatio, pctChange } from "@/lib/format";
import { langTag } from "@/lib/languages";
import { classifyPiece, pieceStats, toDisplayPieces, visiblePiece } from "@/lib/pieces";

function fakeFetch(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(typeof body === "string" ? body : JSON.stringify(body), { status })) as unknown as typeof fetch;
}

describe("buildQuery", () => {
  it("repeats array params (FastAPI list query) and drops empty values", () => {
    expect(buildQuery({ dataset: "FLORES-200", language: ["kn", "en"], split: undefined, page: 2, x: "" }))
      .toBe("?dataset=FLORES-200&language=kn&language=en&page=2");
  });
  it("returns empty string when nothing is set", () => {
    expect(buildQuery({ a: undefined, b: null })).toBe("");
  });
});

describe("request", () => {
  it("parses the backend error body into ApiError", async () => {
    const f = fakeFetch(400, { error: { code: "unknown_tokenizer", message: "Unknown tokenizer 'x'." } });
    await expect(request("/api/tokenize", { method: "POST", body: {} }, { fetchImpl: f }))
      .rejects.toMatchObject({ status: 400, code: "unknown_tokenizer", message: "Unknown tokenizer 'x'." });
  });
  it("maps network failure to network_error with status 0", async () => {
    const f = vi.fn(async () => { throw new TypeError("Failed to fetch"); }) as unknown as typeof fetch;
    const err = await request("/health", {}, { fetchImpl: f }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 0, code: "network_error" });
  });
  it("flags a non-JSON error body as bad_response", async () => {
    await expect(request("/x", {}, { fetchImpl: fakeFetch(500, "Internal Server Error") }))
      .rejects.toMatchObject({ status: 500, code: "bad_response" });
  });
  it("accepts /health 503 degraded bodies", async () => {
    const body = { app: "REDUTAX", version: "0.1.0", env: "development", status: "degraded", database: { status: "error", error: "OperationalError" } };
    const res = await api.health({ fetchImpl: fakeFetch(503, body) });
    expect(res.status).toBe("degraded");
  });
  it("sends JSON bodies for POST", async () => {
    const f = fakeFetch(200, { ok: true });
    await request("/api/tokenize", { method: "POST", body: { text: "ನಮಸ್ಕಾರ" } }, { fetchImpl: f });
    const [, init] = (f as unknown as ReturnType<typeof vi.fn>).mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ text: "ನಮಸ್ಕಾರ" });
  });
});

describe("cost formula (PRD §10.3)", () => {
  it("computes input and output parts separately", () => {
    const r = estimateCost({ inputTokens: 1500, outputTokens: 500, inputPrice: 2, outputPrice: 8, billingUnit: 1_000_000 });
    expect(r.inputCost).toBeCloseTo(0.003, 10);
    expect(r.outputCost).toBeCloseTo(0.004, 10);
    expect(r.total).toBeCloseTo(0.007, 10);
  });
  it("rejects negative or zero billing unit", () => {
    expect(validateCostInput({ inputTokens: 1, outputTokens: 1, inputPrice: 1, outputPrice: 1, billingUnit: 0 })).toHaveLength(1);
    expect(() => estimateCost({ inputTokens: -1, outputTokens: 0, inputPrice: 0, outputPrice: 0, billingUnit: 1 })).toThrow(RangeError);
  });
});

describe("csv", () => {
  it("quotes commas, quotes and newlines", () => {
    expect(csvCell('a,"b"')).toBe('"a,""b"""');
    expect(csvCell(null)).toBe("");
    expect(toCsv(["x", "y"], [["ಕನ್ನಡ", 3]])).toBe("x,y\r\nಕನ್ನಡ,3");
  });
});

describe("token pieces", () => {
  it("classifies byte fragments, whitespace and text", () => {
    expect(classifyPiece("�")).toBe("fragment");
    expect(classifyPiece(" ")).toBe("space");
    expect(classifyPiece(" hello")).toBe("text");
  });
  it("makes whitespace visible", () => {
    expect(visiblePiece(" a\n")).toBe("·a↵");
    expect(toDisplayPieces([""])[0]?.display).toBe("∅");
  });
  it("computes fragment share", () => {
    expect(pieceStats(["a", "�", "�", " "])).toEqual({ total: 4, fragments: 2, whitespace: 1, fragmentShare: 0.5 });
  });
});

describe("format", () => {
  it("renders missing values as an em dash", () => {
    expect(fmtInt(null)).toBe("—");
    expect(fmtRatio(undefined)).toBe("—");
  });
  it("formats ratios and signed percentages", () => {
    expect(fmtRatio(2.345)).toBe("2.35×");
    expect(fmtPct(-12.34)).toBe("-12.3%");
    expect(fmtPct(5)).toBe("+5.0%");
    expect(pctChange(100, 80)).toBe(-20);
    expect(pctChange(0, 5)).toBeNull();
  });
});

describe("langTag", () => {
  it("tags Romanized Indic text with its script", () => {
    expect(langTag("kn", "Latn")).toBe("kn-Latn");
    expect(langTag("kn", "Knda")).toBe("kn");
    expect(langTag(null)).toBeUndefined();
  });
});
