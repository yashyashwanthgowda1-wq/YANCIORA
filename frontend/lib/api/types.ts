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
  | "bad_response"
  | "transliteration_unavailable";

// ---------- POST /api/critical-details, POST /api/meaning-check (Feature 5, rules_v1) ----------
export type DetailCategory =
  | "code" | "url" | "email" | "quoted" | "money" | "datetime" | "number" | "negation" | "protected_term";
export type MeaningStatus = "preserved" | "at_risk" | "changed";
export type ReviewStatus = "reviewed" | "developer_curated" | "unreviewed";
export const MAX_PROTECTED_TERMS = 50;

export interface LexiconRef {
  id: string;
  language: LanguageCode;
  script: Script;
  review_status: ReviewStatus;
}

export interface CriticalDetailsRequest {
  text: string;
  language?: LanguageCode | "auto"; // server default "auto"
  protected_terms?: string[]; // server default []
}

export interface CriticalDetail {
  category: DetailCategory;
  /** as written; equals response.text.slice(start, end) */
  text: string;
  /** comparison key, e.g. "INR 500", "100000", "not" */
  value: string;
  start: number;
  end: number;
}

export interface CriticalDetailsResponse {
  method: string;
  language: LanguageCode | null;
  /** NFC form of the input; offsets point into this string */
  text: string;
  details: CriticalDetail[];
  negation_lexicons: LexiconRef[];
  warnings: string[];
}

export interface MeaningCheckRequest {
  original: string;
  candidate: string;
  language?: LanguageCode | "auto"; // server default "auto"
  protected_terms?: string[]; // server default []
}

export interface DetailFinding {
  category: DetailCategory;
  value: string;
  example: string;
  original_count: number;
  candidate_count: number;
  state: "kept" | "missing" | "added";
}

export interface MeaningCheckResponse {
  /** "preserved" means no rule found a problem — not a guarantee of equivalent meaning */
  status: MeaningStatus;
  method: string;
  language: LanguageCode | null;
  findings: DetailFinding[];
  missing_count: number;
  added_count: number;
  risks: string[];
  warnings: string[];
  negation_lexicons: LexiconRef[];
  limitations: string[];
}

// ---------- POST /api/optimize (Feature 3, opt_rules_v1) ----------
export type OptimizeMode = "safe" | "balanced" | "aggressive";

export interface OptimizeRequest {
  text: string;
  language?: LanguageCode | "auto"; // server default "auto"
  mode?: OptimizeMode; // server default "safe"
  tokenizers?: string[]; // server default ["cl100k_base"]; 1..4, no repeats
  protected_terms?: string[]; // server default []
}

export interface OptimizeTokenCount {
  tokenizer: TokenizerRef;
  status: CountStatus;
  before: number;
  after: number;
  saved: number;
  saved_pct: number;
}

/** start/end are offsets into the NFC form of the original text. */
export interface EditReport {
  rule: string;
  start: number;
  end: number;
  before: string;
  after: string;
  /** per tokenizer: tokens after minus before this edit (negative = saved); null if not measured */
  token_delta: Record<string, number> | null;
  reason: string;
}

export interface AcceptedEdit extends EditReport {
  meaning_status: "preserved";
}

export interface RejectedEdit extends EditReport {
  stage: "protected" | "overlap" | "limit" | "tokens" | "meaning";
}

/** Not applied. The user decides. */
export interface OptimizeSuggestion extends EditReport {
  kind: "at_risk_edit" | "duplicate_sentence" | "script_variant";
  meaning_status: "preserved" | "at_risk";
  risks: string[];
  requires_review: true;
}

export interface PhraseListRef {
  id: string;
  language: LanguageCode;
  review_status: ReviewStatus;
  entries: number;
  applied: boolean;
}

export interface OptimizeResponse {
  method: string;
  mode: OptimizeMode;
  language: LanguageCode | null;
  original: string;
  optimized: string;
  changed: boolean;
  token_counts: OptimizeTokenCount[];
  accepted: AcceptedEdit[];
  suggestions: OptimizeSuggestion[];
  rejected: RejectedEdit[];
  requires_review: boolean;
  phrase_lists: PhraseListRef[];
  meaning_check: MeaningCheckResponse;
  warnings: string[];
  limitations: string[];
}

// ---------- POST /api/script-variants (Feature 6, translit_v1) ----------
export type TranslitScheme = "iso" | "itrans_dravidian" | "hk_dravidian" | "optitrans_dravidian" | "baraha";
export type TranslitLanguage = "kn" | "hi" | "ta" | "te";
export const TRANSLIT_SCHEMES: readonly TranslitScheme[] = [
  "iso", "itrans_dravidian", "hk_dravidian", "optitrans_dravidian", "baraha",
];
export const TRANSLIT_LANGUAGES: readonly TranslitLanguage[] = ["kn", "hi", "ta", "te"];

export interface ScriptVariantsRequest {
  text: string;
  language: TranslitLanguage;
  direction?: "native_to_roman" | "roman_to_native"; // server default "native_to_roman"
  /** required for roman_to_native; "casual" returns status "unsupported" */
  source_scheme?: TranslitScheme | "casual" | null;
  target_schemes?: TranslitScheme[]; // server default ["iso"]
  tokenizers?: string[]; // server default ["cl100k_base"]
  protected_terms?: string[];
}

export interface VariantTokenCount {
  tokenizer: TokenizerRef;
  status: CountStatus;
  tokens: number;
  tokens_per_word: number | null;
  delta_vs_source: number;
  /** tokenization ratio, not a cost multiplier */
  ratio_vs_source: number | null;
}

export interface ScriptSource {
  script: Script;
  scheme: TranslitScheme | null;
  text: string;
  token_counts: VariantTokenCount[];
}

export interface JoinerReport {
  source_count: number;
  output_count: number;
  preserved_in_round_trip: boolean;
}

export interface ScriptVariant {
  script: Script;
  scheme: TranslitScheme | null;
  text: string;
  lossless_round_trip: boolean;
  lossy_reasons: string[];
  converted_spans: number;
  protected_spans_skipped: number;
  joiners: JoinerReport;
  token_counts: VariantTokenCount[];
  meaning_check: MeaningCheckResponse;
  requires_review: true;
  warnings: string[];
}

export interface ScriptVariantsResponse {
  method: string;
  status: "ok" | "unsupported";
  language: LanguageCode;
  direction: "native_to_roman" | "roman_to_native";
  library: { name: string; version: string };
  source: ScriptSource;
  variants: ScriptVariant[];
  warnings: string[];
  limitations: string[];
}
