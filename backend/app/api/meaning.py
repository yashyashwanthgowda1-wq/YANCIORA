from fastapi import APIRouter

from app.schemas import (
    CriticalDetailsRequest, CriticalDetailsResponse, MeaningCheckRequest, MeaningCheckResponse,
)
from app.services import meaning

router = APIRouter(prefix="/api", tags=["meaning"])


@router.post("/meaning-check", response_model=MeaningCheckResponse)
def meaning_check(req: MeaningCheckRequest) -> MeaningCheckResponse:
    """Compare critical details of an original prompt and a rewrite (rules_v1).

    Status `preserved` means no rule found a problem; it is not a guarantee of
    semantic equivalence. See `limitations` in the response."""
    return meaning.check(req)


@router.post("/critical-details", response_model=CriticalDetailsResponse)
def critical_details(req: CriticalDetailsRequest) -> CriticalDetailsResponse:
    """List the critical details in a text with character offsets into `text` (NFC form)."""
    return meaning.critical_details(req)
