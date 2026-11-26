from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Status


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    has_resume: bool = False


class ResumeIn(BaseModel):
    resume_text: str = Field(min_length=50)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApplicationBase(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=160)
    location: str | None = None
    url: str | None = None
    status: Status = Status.applied
    applied_on: date | None = None
    job_description: str | None = None
    notes: str | None = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    """All fields optional so the client can PATCH just what changed."""

    company: str | None = Field(default=None, min_length=1, max_length=120)
    role: str | None = Field(default=None, min_length=1, max_length=160)
    location: str | None = None
    url: str | None = None
    status: Status | None = None
    applied_on: date | None = None
    job_description: str | None = None
    notes: str | None = None


class ApplicationOut(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_score: int | None
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    items: list[ApplicationOut]
    total: int
    limit: int
    offset: int


class Stats(BaseModel):
    total: int
    by_status: dict[str, int]
    response_rate: float = Field(description="Share of submitted applications that got a reply")
    average_match_score: float | None


class MatchRequest(BaseModel):
    resume_text: str = Field(min_length=20)
    job_description: str = Field(min_length=20)


class MatchResult(BaseModel):
    score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_skills: list[str]
    suggestions: list[str]
    suggestions_source: str = Field(description="'llm' or 'rules'")
