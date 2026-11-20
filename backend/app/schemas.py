"""Request/response models. These match the TypeScript types in the UI/UX design
brief (lib/api/types.ts); change both together."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

LanguageCode = Literal["kn", "hi", "ta", "te", "en"]
Script = Literal["Knda", "Deva", "Taml", "Telu", "Latn", "mixed"]
VariantType = Literal["original", "translation", "transliteration", "code_mixed", "paraphrase"]
CountStatus = Literal["exact", "estimate", "provider_reported", "research", "mock", "unsupported"]

MAX_TEXT_CHARS = 20_000
MAX_VARIANTS = 12


class TokenizerRef(BaseModel):
    name: str
    library: str
    version: str
    kind: Literal["baseline", "experimental", "model_input"]


class TokenizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    tokenizer: str
    language: LanguageCode | Literal["auto"] = "auto"
    script: Script | None = None
    include_pieces: bool = False

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v


class TokenizeResponse(BaseModel):
    tokenizer: TokenizerRef
    status: CountStatus
    language: LanguageCode | None
    script: Script | None
    token_count: int
    word_count: int
    char_count: int
    tokens_per_word: float | None
    normalization: str
    word_count_method: str
    pieces: list[str] | None = None


class CompareVariant(BaseModel):
    language: LanguageCode
    script: Script
    variant_type: VariantType
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)


class CompareRequest(BaseModel):
    tokenizer: str
    reference_index: int = Field(default=0, ge=0)
    variants: list[CompareVariant] = Field(min_length=2, max_length=MAX_VARIANTS)
    aligned_group_id: str | None = None


class CompareRow(CompareVariant):
    token_count: int
    word_count: int
    tokens_per_word: float | None
    ratio_vs_reference: float | None


class CompareResponse(BaseModel):
    tokenizer: TokenizerRef
    status: CountStatus
    aligned: bool
    rows: list[CompareRow]
    warnings: list[str]


# ---------- Phase 1 retrieval APIs (GET /api/samples/groups, GET /api/benchmarks) ----------
Split = Literal["train", "validation", "test"]
MAX_PAGE_SIZE = 100


class DatasetRef(BaseModel):
    name: str
    version: str
    license: str | None = None


class GroupSample(BaseModel):
    """One member of an aligned group. language/script/variant_type/text match
    CompareVariant, so a group can be sent straight to POST /api/compare-languages."""
    sample_id: str
    language: LanguageCode
    script: Script
    variant_type: VariantType
    domain: str
    text: str
    source_name: str | None
    source_url: str | None
    license: str | None
    human_verified: bool


class SampleGroup(BaseModel):
    aligned_group_id: str
    dataset: DatasetRef
    split: Split
    languages: list[LanguageCode]
    samples: list[GroupSample]


class SampleGroupsResponse(BaseModel):
    items: list[SampleGroup]
    page: int
    page_size: int
    total: int


class BenchmarkSummary(BaseModel):
    tokenizer: TokenizerRef
    status: CountStatus
    language: LanguageCode
    script: Script
    n_samples: int
    total_tokens: int
    total_words: int
    fertility_mean: float | None
    fertility_median: float | None
    fertility_stdev: float | None
    fertility_ci95_low: float | None
    fertility_ci95_high: float | None
    paired_groups_with_reference: int
    ratio_vs_reference: float | None   # tokenization ratio, not a cost multiplier


class BenchmarkRun(BaseModel):
    run_id: str
    run_at: str
    dataset: DatasetRef
    split: Split | None
    reference_language: LanguageCode
    normalization: str
    word_count_method: str
    code_version: str | None
    input_sha256: str | None
    n_samples: int
    tokenizers: list[TokenizerRef]
    summaries: list[BenchmarkSummary]
    note: str


class BenchmarksResponse(BaseModel):
    items: list[BenchmarkRun]
    page: int
    page_size: int
    total: int


class BenchmarkResultRow(BaseModel):
    sample_id: str
    aligned_group_id: str | None
    language: LanguageCode
    script: Script
    variant_type: VariantType
    tokenizer: TokenizerRef
    status: CountStatus
    token_count: int
    word_count: int
    char_count: int
    tokens_per_word: float | None


class BenchmarkResultsResponse(BaseModel):
    run_id: str
    items: list[BenchmarkResultRow]
    page: int
    page_size: int
    total: int


# ---------- Feature 5: meaning preservation (POST /api/meaning-check, /api/critical-details) ----------
DetailCategory = Literal["code", "url", "email", "quoted", "money", "datetime", "number",
                         "negation", "protected_term"]
MeaningStatus = Literal["preserved", "at_risk", "changed"]
ReviewStatus = Literal["reviewed", "developer_curated", "unreviewed"]
MAX_PROTECTED_TERMS = 50


def _check_terms(terms: list[str]) -> list[str]:
    for t in terms:
        if not t.strip():
            raise ValueError("protected_terms must not contain blank terms")
    return terms


class CriticalDetailsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: LanguageCode | Literal["auto"] = "auto"
    protected_terms: list[str] = Field(default_factory=list, max_length=MAX_PROTECTED_TERMS)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v

    @field_validator("protected_terms")
    @classmethod
    def _terms_ok(cls, v: list[str]) -> list[str]:
        _check_terms(v)
        if any(len(t) > 200 for t in v):
            raise ValueError("protected terms must be at most 200 characters")
        return v


class LexiconRef(BaseModel):
    id: str
    language: LanguageCode
    script: Script
    review_status: ReviewStatus


class CriticalDetail(BaseModel):
    category: DetailCategory
    text: str               # as written; equals response.text[start:end]
    value: str              # comparison key (e.g. "INR 500", "100000", "not")
    start: int
    end: int


class CriticalDetailsResponse(BaseModel):
    method: str
    language: LanguageCode | None
    text: str               # NFC form of the input; offsets point into this string
    details: list[CriticalDetail]
    negation_lexicons: list[LexiconRef]
    warnings: list[str]


class MeaningCheckRequest(BaseModel):
    original: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    candidate: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: LanguageCode | Literal["auto"] = "auto"
    protected_terms: list[str] = Field(default_factory=list, max_length=MAX_PROTECTED_TERMS)

    @field_validator("original", "candidate")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v

    @field_validator("protected_terms")
    @classmethod
    def _terms_ok(cls, v: list[str]) -> list[str]:
        _check_terms(v)
        if any(len(t) > 200 for t in v):
            raise ValueError("protected terms must be at most 200 characters")
        return v


class DetailFinding(BaseModel):
    category: DetailCategory
    value: str
    example: str
    original_count: int
    candidate_count: int
    state: Literal["kept", "missing", "added"]


class MeaningCheckResponse(BaseModel):
    status: MeaningStatus
    method: str
    language: LanguageCode | None
    findings: list[DetailFinding]
    missing_count: int
    added_count: int
    risks: list[str]
    warnings: list[str]
    negation_lexicons: list[LexiconRef]
    limitations: list[str]


# ---------- Feature 3: smart prompt optimizer (POST /api/optimize) ----------
OptimizeMode = Literal["safe", "balanced", "aggressive"]
MAX_OPT_TOKENIZERS = 4


class OptimizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: LanguageCode | Literal["auto"] = "auto"
    mode: OptimizeMode = "safe"
    tokenizers: list[str] = Field(default_factory=lambda: ["cl100k_base"], min_length=1,
                                  max_length=MAX_OPT_TOKENIZERS,
                                  description="An edit must reduce tokens under at least one "
                                              "and must not increase tokens under any.")
    protected_terms: list[str] = Field(default_factory=list, max_length=MAX_PROTECTED_TERMS)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v

    @field_validator("tokenizers")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("tokenizers must not repeat")
        return v

    @field_validator("protected_terms")
    @classmethod
    def _terms_ok(cls, v: list[str]) -> list[str]:
        _check_terms(v)
        if any(len(t) > 200 for t in v):
            raise ValueError("protected terms must be at most 200 characters")
        return v


class OptimizeTokenCount(BaseModel):
    tokenizer: TokenizerRef
    status: CountStatus
    before: int
    after: int
    saved: int
    saved_pct: float


class EditReport(BaseModel):
    """One proposed edit. start/end are offsets into the NFC form of the original text."""
    rule: str
    start: int
    end: int
    before: str
    after: str
    token_delta: dict[str, int] | None = Field(
        description="Per tokenizer: tokens after minus tokens before this edit (negative = saved). "
                    "null when the edit was not measured.")
    reason: str


class AcceptedEdit(EditReport):
    meaning_status: Literal["preserved"] = "preserved"


class RejectedEdit(EditReport):
    stage: Literal["protected", "overlap", "limit", "tokens", "meaning"]


class OptimizeSuggestion(EditReport):
    """Not applied. The user decides."""
    kind: Literal["at_risk_edit", "duplicate_sentence", "script_variant"]
    meaning_status: Literal["preserved", "at_risk"]
    risks: list[str]
    requires_review: Literal[True] = True


class PhraseListRef(BaseModel):
    id: str
    language: LanguageCode
    review_status: ReviewStatus
    entries: int
    applied: bool


class OptimizeResponse(BaseModel):
    method: str
    mode: OptimizeMode
    language: LanguageCode | None
    original: str
    optimized: str
    changed: bool
    token_counts: list[OptimizeTokenCount]
    accepted: list[AcceptedEdit]
    suggestions: list[OptimizeSuggestion]
    rejected: list[RejectedEdit]
    requires_review: bool
    phrase_lists: list[PhraseListRef]
    meaning_check: MeaningCheckResponse
    warnings: list[str]
    limitations: list[str]


# ---------- Feature 6: script and transliteration (POST /api/script-variants) ----------
TranslitScheme = Literal["iso", "itrans_dravidian", "hk_dravidian", "optitrans_dravidian", "baraha"]
TRANSLIT_LANGUAGES = ("kn", "hi", "ta", "te")


class ScriptVariantsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: LanguageCode = Field(description="kn, hi, ta or te (English has no script variants)")
    direction: Literal["native_to_roman", "roman_to_native"] = "native_to_roman"
    source_scheme: TranslitScheme | Literal["casual"] | None = Field(
        default=None, description="Required for roman_to_native. 'casual' (everyday Romanized "
                                  "typing) is not a scheme and returns status 'unsupported'.")
    target_schemes: list[TranslitScheme] = Field(
        default_factory=lambda: ["iso"], min_length=1, max_length=5,
        description="Romanization schemes for native_to_roman (default ISO 15919).")
    tokenizers: list[str] = Field(default_factory=lambda: ["cl100k_base"], min_length=1,
                                  max_length=MAX_OPT_TOKENIZERS)
    protected_terms: list[str] = Field(default_factory=list, max_length=MAX_PROTECTED_TERMS)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text is blank")
        return v

    @field_validator("language")
    @classmethod
    def _indic_only(cls, v: str) -> str:
        if v not in TRANSLIT_LANGUAGES:
            raise ValueError("script variants are available for kn, hi, ta and te only")
        return v

    @field_validator("target_schemes", "tokenizers")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("values must not repeat")
        return v

    @field_validator("protected_terms")
    @classmethod
    def _terms_ok(cls, v: list[str]) -> list[str]:
        _check_terms(v)
        if any(len(t) > 200 for t in v):
            raise ValueError("protected terms must be at most 200 characters")
        return v

    @model_validator(mode="after")
    def _direction_needs(self) -> "ScriptVariantsRequest":
        if self.direction == "roman_to_native" and self.source_scheme is None:
            raise ValueError("source_scheme is required for roman_to_native "
                             "(use 'casual' for everyday Romanized typing)")
        return self


class VariantTokenCount(BaseModel):
    tokenizer: TokenizerRef
    status: CountStatus
    tokens: int
    tokens_per_word: float | None
    delta_vs_source: int
    ratio_vs_source: float | None   # tokenization ratio, not a cost multiplier


class ScriptSource(BaseModel):
    script: Script
    scheme: TranslitScheme | None
    text: str
    token_counts: list[VariantTokenCount]


class JoinerReport(BaseModel):
    """ZWJ (U+200D) / ZWNJ (U+200C) in the converted spans."""
    source_count: int
    output_count: int
    preserved_in_round_trip: bool


class ScriptVariant(BaseModel):
    script: Script
    scheme: TranslitScheme | None
    text: str
    lossless_round_trip: bool
    lossy_reasons: list[str]
    converted_spans: int
    protected_spans_skipped: int
    joiners: JoinerReport
    token_counts: list[VariantTokenCount]
    meaning_check: MeaningCheckResponse
    requires_review: Literal[True] = True
    warnings: list[str]


class TranslitLibrary(BaseModel):
    name: str
    version: str


class ScriptVariantsResponse(BaseModel):
    method: str
    status: Literal["ok", "unsupported"]
    language: LanguageCode
    direction: Literal["native_to_roman", "roman_to_native"]
    library: TranslitLibrary
    source: ScriptSource
    variants: list[ScriptVariant]
    warnings: list[str]
    limitations: list[str]
