"""Request/response models. These match the TypeScript types in the UI/UX design
brief (lib/api/types.ts); change both together."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

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
