"""SQLAlchemy models for database tables."""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Float, Integer, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""


class RunStatus(str, enum.Enum):
    """Status of a run."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(Base):
    """Model for runs table."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repo_path: Mapped[str] = mapped_column(String(255))
    branch: Mapped[str] = mapped_column(String(255))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    plan_items: Mapped[list[PlanItem]] = relationship(back_populates="run")
    changes: Mapped[list[Change]] = relationship(back_populates="run")


class PlanItem(Base):
    """Model for plan_items table."""

    __tablename__ = "plan_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    file_path: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(50))
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    run: Mapped[Run] = relationship(back_populates="plan_items")
    changes: Mapped[list[Change]] = relationship(back_populates="plan_item")


class Change(Base):
    """Model for changes table."""

    __tablename__ = "changes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("runs.id"))
    plan_item_id: Mapped[UUID] = mapped_column(ForeignKey("plan_items.id"))
    file_path: Mapped[str] = mapped_column(String(255))
    diff: Mapped[str] = mapped_column(Text)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    run: Mapped[Run] = relationship(back_populates="changes")
    plan_item: Mapped[PlanItem] = relationship(back_populates="changes")
    verifications: Mapped[list[Verification]] = relationship(back_populates="change")


class VerificationStatus(str, enum.Enum):
    """Status of a verification."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class Verification(Base):
    """Model for verifications table."""

    __tablename__ = "verifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("changes.id"))
    total_tests: Mapped[int] = mapped_column(Integer)
    passed_tests: Mapped[int] = mapped_column(Integer)
    failed_tests: Mapped[int] = mapped_column(Integer)
    skipped_tests: Mapped[int] = mapped_column(Integer)
    coverage_diff: Mapped[float] = mapped_column(Float)
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    change: Mapped[Change] = relationship(back_populates="verifications") 