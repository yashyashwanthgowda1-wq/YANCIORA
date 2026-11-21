"""Read-only access to the native-speaker review datasets (D57). Reviewer decisions are NOT
written by the web server: the review screen exports a decisions file that the team merges with
research/scripts/apply_review_decisions.py (see docs/LINGUISTIC_REVIEW_GUIDE.md)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import ApiException
from app.linguistics import review as RV
from app.schemas import ReviewEntryOut, ReviewLanguageResponse, ReviewSummaryResponse

router = APIRouter(prefix="/api/linguistics", tags=["linguistics"])

HOW_TO_SUBMIT = ("Decisions made on the review screen stay in your browser until you export them. "
                 "Send the exported JSON (or the filled spreadsheet) to the team; they merge it with "
                 "research/scripts/apply_review_decisions.py. Nothing is approved until then.")


def _use(e: RV.Entry) -> str:
    if e.decision == "rejected":
        return "not used (rejected)"
    if not e.is_rewrite:
        return ("detection (protective); " + ("approved" if e.is_approved else "pending review: word changes stay at_risk"))
    if e.auto_eligible:
        return "applied automatically in balanced mode"
    if e.is_approved:
        return "suggestion only (approved, but not safe for automatic use)"
    return "suggestion in aggressive mode only, labelled pending review"


def _out(e: RV.Entry) -> ReviewEntryOut:
    return ReviewEntryOut(
        id=e.id, language=e.language, category=e.category, script=e.script, expression=e.expression,
        gloss=e.gloss, match=e.match, detect_as=e.detect_as, canonical=e.canonical, original=e.original,
        proposed=e.proposed, preserves_meaning=e.preserves_meaning, changes_register=e.changes_register,
        safe_for_auto=e.safe_for_auto, auto_eligible=e.auto_eligible, use=_use(e), decision=e.decision,
        reviewer=e.reviewer, reviewed_at=e.reviewed_at, review_notes=e.review_notes, note=e.note,
        provenance=e.provenance)


@router.get("/summary", response_model=ReviewSummaryResponse)
def review_summary() -> ReviewSummaryResponse:
    return ReviewSummaryResponse(languages=RV.summary(), note=HOW_TO_SUBMIT)


@router.get("/review/{language}", response_model=ReviewLanguageResponse)
def review_language(language: str) -> ReviewLanguageResponse:
    data = RV.load_all()
    if language not in data:
        raise ApiException(404, "not_found", f"No review dataset for language '{language}'.")
    entries = data[language]
    return ReviewLanguageResponse(
        language=language, schema_id=RV.SCHEMA, entries=[_out(e) for e in entries],
        counts={d: sum(1 for e in entries if e.decision == d) for d in RV.DECISIONS},
        how_to_submit=HOW_TO_SUBMIT)
