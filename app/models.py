import enum
from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Status(enum.StrEnum):
    wishlist = "wishlist"
    applied = "applied"
    interview = "interview"
    offer = "offer"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    resume_text: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    applications: Mapped[list["Application"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(120), index=True)
    role: Mapped[str] = mapped_column(String(160))
    location: Mapped[str | None] = mapped_column(String(120), default=None)
    url: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.applied, index=True)
    applied_on: Mapped[date | None] = mapped_column(Date, default=None)
    job_description: Mapped[str | None] = mapped_column(Text, default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)
    match_score: Mapped[int | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="applications")
