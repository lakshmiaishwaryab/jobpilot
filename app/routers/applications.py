from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.config import get_settings
from app.deps import CurrentUser, DbSession
from app.models import Application, Status
from app.schemas import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationPage,
    ApplicationUpdate,
    MatchResult,
    Stats,
)
from app.services import llm, matcher

router = APIRouter(prefix="/applications", tags=["applications"])


def _get_owned(db: DbSession, user: CurrentUser, app_id: int) -> Application:
    application = db.get(Application, app_id)
    # 404 (not 403) for other users' rows so ids can't be probed.
    if application is None or application.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, user: CurrentUser, db: DbSession) -> Application:
    application = Application(owner_id=user.id, **payload.model_dump())
    if application.status != Status.wishlist and application.applied_on is None:
        application.applied_on = date.today()
    db.add(application)
    db.commit()
    return application


@router.get("", response_model=ApplicationPage)
def list_applications(
    user: CurrentUser,
    db: DbSession,
    status_filter: Status | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, description="Search company or role"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ApplicationPage:
    stmt = select(Application).where(Application.owner_id == user.id)
    if status_filter:
        stmt = stmt.where(Application.status == status_filter)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Application.company).like(like), func.lower(Application.role).like(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(Application.updated_at.desc(), Application.id.desc()).limit(limit).offset(offset)
    ).all()
    return ApplicationPage(items=list(rows), total=total, limit=limit, offset=offset)


@router.get("/stats", response_model=Stats)
def stats(user: CurrentUser, db: DbSession) -> Stats:
    counts = dict(
        db.execute(
            select(Application.status, func.count()).where(Application.owner_id == user.id).group_by(Application.status)
        ).all()
    )
    by_status = {s.value: counts.get(s, 0) for s in Status}
    submitted = sum(v for k, v in by_status.items() if k != Status.wishlist.value)
    replied = by_status["interview"] + by_status["offer"] + by_status["rejected"]
    avg = db.scalar(
        select(func.avg(Application.match_score)).where(
            Application.owner_id == user.id, Application.match_score.is_not(None)
        )
    )
    return Stats(
        total=sum(by_status.values()),
        by_status=by_status,
        response_rate=round(replied / submitted, 3) if submitted else 0.0,
        average_match_score=round(float(avg), 1) if avg is not None else None,
    )


@router.get("/follow-ups", response_model=list[ApplicationOut])
def follow_ups(
    user: CurrentUser,
    db: DbSession,
    days: int | None = Query(default=None, ge=1, le=90),
) -> list[Application]:
    """Applications still 'applied' with no reply after N days: time to follow up."""
    cutoff = date.today() - timedelta(days=days or get_settings().follow_up_after_days)
    stmt = (
        select(Application)
        .where(
            Application.owner_id == user.id,
            Application.status == Status.applied,
            Application.applied_on <= cutoff,
        )
        .order_by(Application.applied_on)
    )
    return list(db.scalars(stmt).all())


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int, user: CurrentUser, db: DbSession) -> Application:
    return _get_owned(db, user, app_id)


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(app_id: int, payload: ApplicationUpdate, user: CurrentUser, db: DbSession) -> Application:
    application = _get_owned(db, user, app_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    if payload.job_description is not None:
        application.match_score = None  # stale; re-score on demand
    db.commit()
    return application


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(app_id: int, user: CurrentUser, db: DbSession) -> Response:
    db.delete(_get_owned(db, user, app_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{app_id}/match", response_model=MatchResult)
def match_application(app_id: int, user: CurrentUser, db: DbSession) -> MatchResult:
    """Score the saved resume against this application's job description."""
    application = _get_owned(db, user, app_id)
    if not user.resume_text:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload your resume first: PUT /auth/me/resume")
    if not application.job_description:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This application has no job description")
    analysis = matcher.analyze(user.resume_text, application.job_description)
    tips, source = llm.suggestions(user.resume_text, application.job_description, analysis)
    application.match_score = analysis.score
    db.commit()
    return MatchResult(
        score=analysis.score,
        matched_skills=analysis.matched_skills,
        missing_skills=analysis.missing_skills,
        suggestions=tips,
        suggestions_source=source,
    )
