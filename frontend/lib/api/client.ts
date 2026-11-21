import type {
  ApiErrorBody, BenchmarkResultsQuery, BenchmarkResultsResponse, BenchmarksQuery, BenchmarksResponse,
  CompareRequest, CompareResponse, CriticalDetailsRequest, CriticalDetailsResponse, HealthResponse,
  MeaningCheckRequest, MeaningCheckResponse, OptimizeRequest, OptimizeResponse, SampleGroupsQuery,
  SampleGroupsResponse, ScriptVariantsRequest, ScriptVariantsResponse, TokenizeRequest, TokenizeResponse,
  TokenizersResponse,
  AnalyzeRequest, AnalyzeResponse, ApplyEditsRequest, ApplyEditsResponse, ChatAnalyzeRequest, ChatAnalyzeResponse,
  ChatHistoryResponse, ChatSendRequest, ChatSendResponse, CostEstimateRequest, CostEstimateResponse,
  IntegrationsResponse, ModelRegistryResponse, RecommendRequest, RecommendResponse, TranscribeRequest,
  TranscribeResponse, VapiStatusResponse,
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
  init: { method?: "GET" | "POST" | "DELETE"; body?: unknown } = {},
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
    if (res.status === 204) return undefined as T;
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

  // Feature 3 — smart prompt optimizer (opt_rules_v1)
  optimize: (body: OptimizeRequest, o?: RequestOptions) =>
    request<OptimizeResponse>("/api/optimize", { method: "POST", body }, o),

  // Feature 5 — meaning preservation (rules_v2)
  meaningCheck: (body: MeaningCheckRequest, o?: RequestOptions) =>
    request<MeaningCheckResponse>("/api/meaning-check", { method: "POST", body }, o),

  criticalDetails: (body: CriticalDetailsRequest, o?: RequestOptions) =>
    request<CriticalDetailsResponse>("/api/critical-details", { method: "POST", body }, o),

  // Feature 6 — script and transliteration variants (translit_v1)
  scriptVariants: (body: ScriptVariantsRequest, o?: RequestOptions) =>
    request<ScriptVariantsResponse>("/api/script-variants", { method: "POST", body }, o),

  // Feature 4 / 7 — model registry, cost, recommendation
  models: (o?: RequestOptions) => request<ModelRegistryResponse>("/api/models", {}, o),
  costEstimate: (body: CostEstimateRequest, o?: RequestOptions) =>
    request<CostEstimateResponse>("/api/cost/estimate", { method: "POST", body }, o),
  recommend: (body: RecommendRequest, o?: RequestOptions) =>
    request<RecommendResponse>("/api/models/recommend", { method: "POST", body }, o),

  // Feature 8 — pipeline and server transcription
  analyze: (body: AnalyzeRequest, o?: RequestOptions) =>
    request<AnalyzeResponse>("/api/pipeline/analyze", { method: "POST", body }, o),
  applyEdits: (body: ApplyEditsRequest, o?: RequestOptions) =>
    request<ApplyEditsResponse>("/api/pipeline/apply", { method: "POST", body }, o),
  transcribe: (body: TranscribeRequest, o?: RequestOptions) =>
    request<TranscribeResponse>("/api/voice/transcribe", { method: "POST", body }, o),

  // Feature 9 — chat
  chat: (body: ChatAnalyzeRequest, o?: RequestOptions) =>
    request<ChatAnalyzeResponse>("/api/chat", { method: "POST", body }, o),
  chatSend: (sessionId: string, body: ChatSendRequest, o?: RequestOptions) =>
    request<ChatSendResponse>(`/api/chat/${encodeURIComponent(sessionId)}/send`, { method: "POST", body }, o),
  chatHistory: (sessionId: string, o?: RequestOptions) =>
    request<ChatHistoryResponse>(`/api/chat/${encodeURIComponent(sessionId)}`, {}, o),
  chatDelete: (sessionId: string, o?: RequestOptions) =>
    request<void>(`/api/chat/${encodeURIComponent(sessionId)}`, { method: "DELETE" }, o),

  // Status (Feature 10 + providers)
  integrations: (o?: RequestOptions) => request<IntegrationsResponse>("/api/integrations/status", {}, o),
  vapiStatus: (o?: RequestOptions) => request<VapiStatusResponse>("/api/vapi/status", {}, o),
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
    case "transliteration_unavailable":
      return "Install the transliteration engine on the backend: pip install --no-deps --require-hashes -r requirements-translit.txt";
    case "stt_not_configured":
      return "Server transcription needs STT_BASE_URL, STT_API_KEY and STT_MODEL in the backend .env. Use browser voice input or type instead.";
    case "llm_not_configured":
      return "Sending to a model needs LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in the backend .env. REDUTAX analysis still works.";
    case "provider_error":
      return "The configured provider failed or timed out. Try again; check the provider's status and the backend logs.";
    case "provider_rate_limited":
      return "The provider's rate limit was reached. Wait for the time in the message, then retry. The message was not added to the conversation."
    case "registry_invalid":
      return "config/models.yaml has an invalid entry. Fix it and retry.";
    case "unknown_tokenizer":
      return "Pick a tokenizer from the list; the backend only accepts the names it reports at /api/tokenizers.";
    case "not_found":
      return "Nothing matches that dataset or run.";
    default:
      return null;
  }
}
