from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query

from app.api.deps import db_errors, get_db
from app.schemas import (
    MAX_PAGE_SIZE, BenchmarkResultRow, BenchmarkResultsResponse, BenchmarkRun, BenchmarksResponse,
    BenchmarkSummary, DatasetRef, LanguageCode, Script,
)
from app.services import benchmark_store

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])

RunId = Annotated[str, Path(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")]


@router.get("", response_model=BenchmarksResponse)
def benchmarks(
    engine: Any = Depends(get_db),
    run_id: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    dataset: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    dataset_version: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    tokenizer: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    language: LanguageCode | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> BenchmarksResponse:
    """Stored benchmark runs (newest first) with per tokenizer × language × script summaries."""
    with db_errors():
        runs, total = benchmark_store.list_runs(
            engine, run_id=run_id, dataset=dataset, dataset_version=dataset_version,
            tokenizer=tokenizer, language=language, page=page, page_size=page_size)
    items = [
        BenchmarkRun(
            **{k: r[k] for k in ("run_id", "split", "reference_language", "normalization",
                                 "word_count_method", "code_version", "input_sha256",
                                 "n_samples", "tokenizers", "note")},
            run_at=r["run_at"].isoformat(),
            dataset=DatasetRef(name=r["dataset"], version=r["dataset_version"],
                               license=r["dataset_license"]),
            summaries=[BenchmarkSummary(**s) for s in r["summaries"]],
        )
        for r in runs
    ]
    return BenchmarksResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{run_id}/results", response_model=BenchmarkResultsResponse)
def benchmark_results(
    run_id: RunId,
    engine: Any = Depends(get_db),
    tokenizer: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    language: LanguageCode | None = None,
    script: Script | None = None,
    aligned_group_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> BenchmarkResultsResponse:
    """Per-sample token counts stored for one run."""
    with db_errors():
        rows, total = benchmark_store.list_results(
            engine, run_id, tokenizer=tokenizer, language=language, script=script,
            aligned_group_id=aligned_group_id, page=page, page_size=page_size)
    return BenchmarkResultsResponse(
        run_id=run_id, items=[BenchmarkResultRow(**r) for r in rows],
        page=page, page_size=page_size, total=total)
