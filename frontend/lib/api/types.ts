/**
 * Mirror of backend/app/schemas.py (and the inline response shapes in backend/app/api/*.py).
 * Change both together. Field names, optionality and literal unions match exactly.
 * Python `X | None` → TS `X | null`. Fields with a server default are optional in requests.
 */

export type LanguageCode = "kn" | "hi" | "ta" | "te" | "en";
export type Script = "Knda" | "Deva" | "Taml" | "Telu" | "Latn" | "mixed";
export type VariantType = "original" | "translation" | "transliteration" | "code_mixed" | "paraphrase";
export type CountStatus = "exact" | "estimate" | "provider_reported" | "research" | "mock" | "unsupported";
export type TokenizerKind = "baseline" | "experimental" | "model_input";
export type Split = "train" | "validation" | "test";

export const MAX_TEXT_CHARS = 20_000;
export const MAX_VARIANTS = 12;
export const MAX_PAGE_SIZE = 100;

export const LANGUAGE_CODES: readonly LanguageCode[] = ["kn", "hi", "ta", "te", "en"];
export const SCRIPTS: readonly Script[] = ["Knda", "Deva", "Taml", "Telu", "Latn", "mixed"];
export const VARIANT_TYPES: readonly VariantType[] = [
  "original", "translation", "transliteration", "code_mixed", "paraphrase",
];
export const SPLITS: readonly Split[] = ["train", "validation", "test"];

export interface TokenizerRef {
  name: string;
  library: string;
  version: string;
  kind: TokenizerKind;
}

// ---------- POST /api/tokenize ----------
export interface TokenizeRequest {
  text: string;
  tokenizer: string;
  language?: LanguageCode | "auto"; // server default "auto"
  script?: Script | null;
  include_pieces?: boolean; // server default false
}

export interface TokenizeResponse {
  tokenizer: TokenizerRef;
  status: CountStatus;
  language: LanguageCode | null;
  script: Script | null;
  token_count: number;
  word_count: number;
  char_count: number;
  tokens_per_word: number | null;
  normalization: string;
  word_count_method: string;
  pieces?: string[] | null;
}

// ---------- POST /api/compare-languages ----------
export interface CompareVariant {
  language: LanguageCode;
  script: Script;
  variant_type: VariantType;
  text: string;
}

export interface CompareRequest {
  tokenizer: string;
  reference_index?: number; // server default 0
  variants: CompareVariant[]; // 2..MAX_VARIANTS
  aligned_group_id?: string | null;
}

export interface CompareRow extends CompareVariant {
  token_count: number;
  word_count: number;
  tokens_per_word: number | null;
  /** tokens-per-word ratio vs the reference variant — a tokenization ratio, NOT a cost multiplier */
  ratio_vs_reference: number | null;
}

export interface CompareResponse {
  tokenizer: TokenizerRef;
  status: CountStatus;
  aligned: boolean;
  rows: CompareRow[];
  warnings: string[];
}

// ---------- GET /api/samples/groups ----------
export interface DatasetRef {
  name: string;
  version: string;
  license?: string | null;
}

export interface GroupSample {
  sample_id: string;
  language: LanguageCode;
  script: Script;
  variant_type: VariantType;
  domain: string;
  text: string;
  source_name: string | null;
  source_url: string | null;
  license: string | null;
  human_verified: boolean;
}

export interface SampleGroup {
  aligned_group_id: string;
  dataset: DatasetRef;
  split: Split;
  languages: LanguageCode[];
  samples: GroupSample[];
}

export interface SampleGroupsResponse {
  items: SampleGroup[];
  page: number;
  page_size: number;
  total: number;
}

export interface SampleGroupsQuery {
  dataset?: string;
  dataset_version?: string;
  language?: LanguageCode[];
  split?: Split;
  aligned_group_id?: string;
  page?: number;
  page_size?: number;
}

// ---------- GET /api/benchmarks ----------
export interface BenchmarkSummary {
  tokenizer: TokenizerRef;
  status: CountStatus;
  language: LanguageCode;
  script: Script;
  n_samples: number;
  total_tokens: number;
  total_words: number;
  fertility_mean: number | null;
  fertility_median: number | null;
  fertility_stdev: number | null;
  fertility_ci95_low: number | null;
  fertility_ci95_high: number | null;
  paired_groups_with_reference: number;
  /** tokenization ratio, not a cost multiplier */
  ratio_vs_reference: number | null;
}

export interface BenchmarkRun {
  run_id: string;
  run_at: string;
  dataset: DatasetRef;
  split: Split | null;
  reference_language: LanguageCode;
  normalization: string;
  word_count_method: string;
  code_version: string | null;
  input_sha256: string | null;
  n_samples: number;
  tokenizers: TokenizerRef[];
  summaries: BenchmarkSummary[];
  note: string;
}

export interface BenchmarksResponse {
  items: BenchmarkRun[];
  page: number;
  page_size: number;
  total: number;
}

export interface BenchmarksQuery {
  run_id?: string;
  dataset?: string;
  dataset_version?: string;
  tokenizer?: string;
  language?: LanguageCode;
  page?: number;
  page_size?: number;
}

// ---------- GET /api/benchmarks/{run_id}/results ----------
export interface BenchmarkResultRow {
  sample_id: string;
  aligned_group_id: string | null;
  language: LanguageCode;
  script: Script;
  variant_type: VariantType;
  tokenizer: TokenizerRef;
  status: CountStatus;
  token_count: number;
  word_count: number;
  char_count: number;
  tokens_per_word: number | null;
}

export interface BenchmarkResultsResponse {
  run_id: string;
  items: BenchmarkResultRow[];
  page: number;
  page_size: number;
  total: number;
}

export interface BenchmarkResultsQuery {
  tokenizer?: string;
  language?: LanguageCode;
  script?: Script;
  aligned_group_id?: string;
  page?: number;
  page_size?: number;
}

// ---------- Inline shapes from route code ----------
/** GET /health (backend/app/api/health.py) */
export interface HealthResponse {
  app: string;
  version: string;
  env: "development" | "test" | "production";
  status: "ok" | "degraded";
  database: { status: "ok" | "not_configured" | "error"; error?: string };
}

/** GET /api/tokenizers (backend/app/api/counting.py) — names only */
export interface TokenizersResponse {
  tokenizers: string[];
}

/** Error body for every handled error (backend/app/api/errors.py) */
export interface ApiErrorBody {
  error: { code: string; message: string };
}

/** Error codes the backend emits today, plus client-side codes. */
export type KnownErrorCode =
  | "invalid_request"
  | "unknown_tokenizer"
  | "tokenizer_unavailable"
  | "not_found"
  | "database_not_configured"
  | "database_unavailable"
  | "network_error"
  | "bad_response";
