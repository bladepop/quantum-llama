"""Models for tracking code analysis and modification runs."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic.dataclasses import dataclass
from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.models import Base, PlanItem


class RunStatus(str, Enum):
    """Status of a code analysis and modification run."""

    PENDING = "pending"
    ANALYZING = "analyzing"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class RunResult(str, Enum):
    """Result of a completed run."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


@dataclass
class Run:
    """A code analysis and modification run.
    
    Attributes:
        id: Unique identifier for the run
        repo_url: URL of the target repository
        branch: Branch being analyzed/modified
        status: Current status of the run
        result: Final result of the run (if completed)
        error: Error message if run failed
        created_at: When the run was created
        updated_at: When the run was last updated
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    repo_url: str
    branch: str
    status: RunStatus = RunStatus.PENDING
    result: Optional[RunResult] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RunModel(Base):
    """SQLAlchemy model for runs."""

    __tablename__ = "runs"

    id: Mapped[UUID] = mapped_column(UUID, primary_key=True)
    repo_url: Mapped[str] = mapped_column(String)
    branch: Mapped[str] = mapped_column(String)
    status: Mapped[RunStatus] = mapped_column(SQLEnum(RunStatus))
    result: Mapped[Optional[RunResult]] = mapped_column(SQLEnum(RunResult), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    plan_items = relationship(PlanItem, back_populates="run") 