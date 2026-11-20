import type {
  ApiErrorBody, BenchmarkResultsQuery, BenchmarkResultsResponse, BenchmarksQuery, BenchmarksResponse,
  CompareRequest, CompareResponse, HealthResponse, SampleGroupsQuery, SampleGroupsResponse,
  TokenizeRequest, TokenizeResponse, TokenizersResponse,
} from "./types";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

/** Every failure surfaces as ApiError. status 0 = the request never reached the server. */
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorBody(x: unknown): x is ApiErrorBody {
  if (typeof x !== "object" || x === null || !("error" in x)) return false;
  const e = (x as { error: unknown }).error;
  return typeof e === "object" && e !== null && "code" in e && "message" in e;
}

type QueryValue = string | number | boolean | undefined | null | readonly (string | number)[];

/** Builds a query string; arrays become repeated keys (FastAPI list params), empty values are dropped. */
export function buildQuery(params: Record<string, QueryValue>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((item) => sp.append(k, String(item)));
    else sp.append(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export interface RequestOptions {
  signal?: AbortSignal;
  /** Accept a non-2xx response that still carries a valid body (e.g. /health → 503 "degraded"). */
  acceptStatus?: number[];
  fetchImpl?: typeof fetch;
}

export async function request<T>(
  path: string,
  init: { method?: "GET" | "POST"; body?: unknown } = {},
  opts: RequestOptions = {},
): Promise<T> {
  const f = opts.fetchImpl ?? fetch;
  let res: Response;
  try {
    res = await f(`${API_BASE_URL}${path}`, {
      method: init.method ?? "GET",
      headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: opts.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "network_error",
      `Could not reach the REDUTAX backend at ${API_BASE_URL}. Is it running?`);
  }

  let body: unknown = null;
  const text = await res.text();
  if (text) {
    try { body = JSON.parse(text); } catch { body = null; }
  }

  if (res.ok || opts.acceptStatus?.includes(res.status)) {
    if (body === null) throw new ApiError(res.status, "bad_response", "The server returned an empty or non-JSON response.");
    return body as T;
  }
  if (isErrorBody(body)) throw new ApiError(res.status, body.error.code, body.error.message);
  throw new ApiError(res.status, "bad_response", `Unexpected response (HTTP ${res.status}).`);
}

// ---------- Implemented endpoints ----------
export const api = {
  health: (o?: RequestOptions) =>
    request<HealthResponse>("/health", {}, { ...o, acceptStatus: [503] }),

  tokenizers: (o?: RequestOptions) =>
    request<TokenizersResponse>("/api/tokenizers", {}, o),

  tokenize: (body: TokenizeRequest, o?: RequestOptions) =>
    request<TokenizeResponse>("/api/tokenize", { method: "POST", body }, o),

  compareLanguages: (body: CompareRequest, o?: RequestOptions) =>
    request<CompareResponse>("/api/compare-languages", { method: "POST", body }, o),

  sampleGroups: (q: SampleGroupsQuery = {}, o?: RequestOptions) =>
    request<SampleGroupsResponse>(`/api/samples/groups${buildQuery({ ...q })}`, {}, o),

  benchmarks: (q: BenchmarksQuery = {}, o?: RequestOptions) =>
    request<BenchmarksResponse>(`/api/benchmarks${buildQuery({ ...q })}`, {}, o),

  benchmarkResults: (runId: string, q: BenchmarkResultsQuery = {}, o?: RequestOptions) =>
    request<BenchmarkResultsResponse>(
      `/api/benchmarks/${encodeURIComponent(runId)}/results${buildQuery({ ...q })}`, {}, o),
};

/** Human guidance for known error codes (shown under the server's own message). */
export function errorHint(code: string): string | null {
  switch (code) {
    case "network_error":
      return "Start the backend: cd backend && uvicorn app.main:app --reload. Check NEXT_PUBLIC_API_BASE_URL and REDUTAX_CORS_ORIGINS.";
    case "tokenizer_unavailable":
      return "The backend could not load this tokenizer. tiktoken downloads its encoding files on first use; offline servers need TIKTOKEN_CACHE_DIR pre-filled.";
    case "database_not_configured":
      return "Set DATABASE_URL in the backend .env and run alembic upgrade head.";
    case "database_unavailable":
      return "The database is configured but unreachable. Start it with: docker compose up -d db.";
    case "not_found":
      return "Nothing matches that dataset or run.";
    default:
      return null;
  }
}
