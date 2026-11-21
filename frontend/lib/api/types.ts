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

// ---------- POST /api/critical-details, POST /api/meaning-check (Feature 5, rules_v4) ----------
export type DetailCategory =
  | "code" | "url" | "email" | "quoted" | "money" | "datetime" | "number"
  | "condition" | "constraint" | "question" | "negation" | "entity" | "protected_term";
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
  /** review-data word lists used (rules_v4); "unreviewed" = pending native-speaker review */
  marker_lists?: LexiconRef[];
  limitations: string[];
}

// ---------- POST /api/optimize (Feature 3, opt_rules_v2) ----------
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
  /** language whose rule produced the edit */
  language?: LanguageCode | null;
  /** review-dataset entry id for phrase rules */
  source?: string | null;
  risk?: EditRisk;
  approval_required?: boolean;
  /** meaning-check status, or the stage that rejected the edit */
  validation?: string;
  tokens_before?: Record<string, number> | null;
  tokens_after?: Record<string, number> | null;
}

export type EditRisk = "lossless" | "redundancy" | "wording" | "meaning_change";

export interface AcceptedEdit extends EditReport {
  meaning_status: "preserved";
}

export interface RejectedEdit extends EditReport {
  stage: "protected" | "overlap" | "limit" | "tokens" | "meaning";
}

/** Not applied. The user decides. */
export interface OptimizeSuggestion extends EditReport {
  kind: "at_risk_edit" | "duplicate_sentence" | "script_variant" | "unreviewed_phrase" | "approved_phrase";
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
  /** what this mode applies automatically and what it only suggests */
  mode_policy: string;
  language: LanguageCode | null;
  script: Script | null;
  original: string;
  optimized: string;
  changed: boolean;
  /** Unicode code points; a character reduction is not a token reduction */
  original_chars: number;
  optimized_chars: number;
  chars_saved: number;
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

// =====================================================================================
// Phase 2 — Features 4 (cost), 7 (recommendation), 8 (voice), 9 (chat), 10 (Vapi)
// Mirror of backend/app/schemas.py (Phase 2 section). Change both together.
// =====================================================================================
export type Encoding = "cl100k_base" | "o200k_base";
export type SupportLevel = "verified" | "claimed" | "unsupported" | "unknown";
export type TaskType = "general" | "summarization" | "translation" | "qa" | "coding" | "creative" | "classification" | "extraction";
export type CostPreference = "lowest" | "balanced" | "quality";
export const TASK_TYPES: readonly TaskType[] = ["general", "summarization", "translation", "qa", "coding", "creative", "classification", "extraction"];
export const MAX_MODELS_PER_REQUEST = 10;

export interface ModelPricing {
  currency: string;
  input_per_1m: number;
  output_per_1m: number;
  source_url?: string | null;
  verified_at?: string | null; // YYYY-MM-DD
}

export interface ModelSpec {
  id: string;
  provider: string;
  display_name?: string | null;
  encoding?: Encoding | null;
  encoding_source?: string | null;
  context_window_tokens?: number | null;
  max_output_tokens?: number | null;
  pricing?: ModelPricing | null;
  languages?: Partial<Record<LanguageCode, SupportLevel>>;
  language_source?: string | null;
  tasks?: TaskType[];
  quality_tier?: number | null;
  quality_source?: string | null;
  source?: "registry" | "user";
  notes?: string | null;
}

export interface ModelRegistryResponse { models: ModelSpec[]; count: number; registry_file: string; warnings: string[] }

export interface CostEstimateRequest {
  text: string;
  optimized_text?: string | null;
  model_ids?: string[];
  custom_models?: ModelSpec[];
  expected_output_tokens?: number;
  fallback_encoding?: Encoding;
}

export interface ModelCost {
  model_id: string;
  provider: string;
  display_name: string | null;
  source: "registry" | "user";
  encoding_used: Encoding;
  encoding_status: "model_encoding" | "fallback_encoding";
  count_status: CountStatus;
  input_tokens: number;
  optimized_input_tokens: number | null;
  output_tokens: number;
  currency: string | null;
  input_cost: number | null;
  output_cost: number | null;
  total_cost: number | null;
  optimized_total_cost: number | null;
  savings: number | null;
  savings_pct: number | null;
  price_status: "verified" | "unverified" | "user_entered" | "missing";
  price_source_url: string | null;
  price_verified_at: string | null;
  warnings: string[];
}

export interface CostEstimateResponse { method: string; models: ModelCost[]; expected_output_tokens: number; unknown_model_ids: string[]; warnings: string[] }

export interface RecommendRequest {
  text: string;
  language: LanguageCode;
  task_type?: TaskType;
  cost_preference?: CostPreference;
  require_language_support?: "verified" | "claimed" | "any";
  min_context_tokens?: number | null;
  min_quality_tier?: number | null;
  expected_output_tokens?: number;
  model_ids?: string[] | null;
  custom_models?: ModelSpec[];
  locked_model_id?: string | null;
}

export interface Candidate {
  model_id: string;
  provider: string;
  display_name: string | null;
  source: "registry" | "user";
  eligible: boolean;
  rank: number | null;
  language_support: SupportLevel;
  context_window_tokens: number | null;
  required_tokens: number;
  quality_tier: number | null;
  cost: ModelCost;
  reasons: string[];
  exclusions: string[];
  limitations: string[];
}

export interface RecommendResponse {
  method: string;
  language: LanguageCode;
  task_type: TaskType;
  cost_preference: CostPreference;
  recommended: Candidate | null;
  alternatives: Candidate[];
  excluded: Candidate[];
  locked: boolean;
  explanation: string;
  warnings: string[];
}

export interface AnalyzeRequest {
  text: string;
  language?: LanguageCode | "auto";
  tokenizer?: string;
  mode?: OptimizeMode;
  protected_terms?: string[];
  task_type?: TaskType;
  cost_preference?: CostPreference;
  expected_output_tokens?: number;
  model_ids?: string[] | null;
  custom_models?: ModelSpec[];
  locked_model_id?: string | null;
}

export interface AnalyzeResponse {
  method: string;
  language: LanguageCode | null;
  script: Script | null;
  tokens: TokenizeResponse;
  optimization: OptimizeResponse;
  recommendation: RecommendResponse | null;
  cost: CostEstimateResponse | null;
  requires_review: boolean;
  next_step: string;
}

export interface TextEdit { start: number; end: number; after: string }

export interface ApplyEditsRequest {
  original: string;
  edits: TextEdit[];
  language?: LanguageCode | "auto";
  tokenizer?: string;
  protected_terms?: string[];
}

export interface ApplyEditsResponse {
  text: string;
  applied_count: number;
  allowed: boolean;
  meaning_check: MeaningCheckResponse;
  tokenizer: TokenizerRef;
  tokens_before: number;
  tokens_after: number;
  warnings: string[];
}

export interface TranscribeRequest { audio_base64: string; mime_type?: string; language?: LanguageCode | "auto" }
export interface TranscribeResponse { text: string; language: LanguageCode | null; provider: string; model: string | null; status: "provider_transcript" }

export interface ChatTurn {
  role: "user" | "assistant";
  kind: "message" | "analysis" | "llm_reply";
  content: string;
  created_at: string;
  meta: Record<string, unknown>;
}

export interface ChatAnalyzeRequest extends AnalyzeRequest { session_id?: string | null }
export interface ChatAnalyzeResponse { session_id: string; mode: "analysis"; reply: string; analysis: AnalyzeResponse; llm_available: boolean; history: ChatTurn[] }
export interface ChatSendRequest { text: string; language?: LanguageCode | "auto" }
export interface LlmUsage { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null; status: "provider_reported" }
export interface ChatSendResponse { session_id: string; reply: string; provider: string; model: string; usage: LlmUsage | null; history: ChatTurn[] }
export interface ChatHistoryResponse { session_id: string; history: ChatTurn[] }

export interface IntegrationStatus { configured: boolean; detail: string }
export interface IntegrationsResponse {
  database: IntegrationStatus;
  models_registry: IntegrationStatus;
  speech_to_text: IntegrationStatus;
  llm: IntegrationStatus;
  vapi_webhook: IntegrationStatus;
}

export interface VapiStatusResponse {
  webhook_path: string;
  auth_configured: boolean;
  auth_modes: string[];
  tools: string[];
  assistant_config: string;
  connection_guide: string;
  live_call_verified: boolean;
}

// ---------- GET /api/linguistics/* (native-speaker review datasets, read-only) ----------
export type ReviewDecision = "pending_review" | "approved" | "rejected" | "corrected";
export interface ReviewEntry {
  id: string; language: LanguageCode; category: string; script: string; expression: string; gloss: string;
  match: string | null; detect_as: string | null; canonical: string | null; original: string | null; proposed: string | null;
  preserves_meaning: string; changes_register: string; safe_for_auto: boolean; auto_eligible: boolean;
  /** how the optimizer uses the entry today */
  use: string;
  decision: ReviewDecision; reviewer: string | null; reviewed_at: string | null; review_notes: string; note: string; provenance: string;
}
export interface ReviewLanguageResponse { language: LanguageCode; schema_id: string; entries: ReviewEntry[]; counts: Record<string, number>; how_to_submit: string }
export interface ReviewSummaryResponse { languages: Record<string, { total: number; decisions: Record<ReviewDecision, number>; auto_rules: number; categories: Record<string, Record<ReviewDecision, number>> }>; note: string }
