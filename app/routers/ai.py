from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas import MatchRequest, MatchResult
from app.services import llm, matcher

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/match", response_model=MatchResult)
def match(payload: MatchRequest, _: CurrentUser) -> MatchResult:
    """Score any resume against any job description without saving anything."""
    analysis = matcher.analyze(payload.resume_text, payload.job_description)
    tips, source = llm.suggestions(payload.resume_text, payload.job_description, analysis)
    return MatchResult(
        score=analysis.score,
        matched_skills=analysis.matched_skills,
        missing_skills=analysis.missing_skills,
        suggestions=tips,
        suggestions_source=source,
    )
