from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import db_errors, get_db
from app.schemas import (
    MAX_PAGE_SIZE, DatasetRef, GroupSample, LanguageCode, SampleGroup, SampleGroupsResponse, Split,
)
from app.services import dataset_store

router = APIRouter(prefix="/api/samples", tags=["samples"])


@router.get("/groups", response_model=SampleGroupsResponse)
def sample_groups(
    engine: Any = Depends(get_db),
    dataset: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    dataset_version: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    language: Annotated[list[LanguageCode] | None, Query(
        description="Repeatable. Only groups containing every listed language.")] = None,
    split: Split | None = None,
    aligned_group_id: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> SampleGroupsResponse:
    """Aligned language groups from imported datasets (meaning-equivalent rows)."""
    with db_errors():
        groups, total = dataset_store.list_groups(
            engine, dataset=dataset, dataset_version=dataset_version, languages=language,
            split=split, aligned_group_id=aligned_group_id, page=page, page_size=page_size)
    items = [
        SampleGroup(
            aligned_group_id=g["aligned_group_id"],
            dataset=DatasetRef(name=g["dataset"], version=g["dataset_version"],
                               license=g["dataset_license"]),
            split=g["split"],
            languages=sorted({m["language_code"] for m in g["samples"]}),
            samples=[GroupSample(language=m["language_code"], **{
                k: m[k] for k in ("sample_id", "script", "variant_type", "domain", "text",
                                  "source_name", "source_url", "license", "human_verified")})
                for m in g["samples"]],
        )
        for g in groups
    ]
    return SampleGroupsResponse(items=items, page=page, page_size=page_size, total=total)
