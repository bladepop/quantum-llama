"""FastAPI service for the Quantum Llama API."""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from db.config import db
from db.models import Change, PlanItem, Run, Verification
from db.repository import ChangeRepository, PlanItemRepository, RunRepository, VerificationRepository

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quantum Llama API",
    description="API for managing and monitoring LLM-powered codebase operations",
    version="0.1.0",
)


# Response models
class PaginatedResponse(BaseModel):
    """Base class for paginated responses."""

    total: int
    page: int
    page_size: int
    has_next: bool


class RunResponse(BaseModel):
    """Response model for runs."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    repo_path: str
    branch: str
    status: str
    created_at: str
    completed_at: str | None


class PlanItemResponse(BaseModel):
    """Response model for plan items."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    file_path: str
    action: str
    reason: str
    confidence: float
    created_at: str


class ChangeResponse(BaseModel):
    """Response model for changes."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    plan_item_id: str
    file_path: str
    diff: str
    commit_sha: str | None
    created_at: str


class VerificationResponse(BaseModel):
    """Response model for verifications."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    coverage_diff: float
    status: str
    created_at: str


class PaginatedRunResponse(PaginatedResponse):
    """Paginated response for runs."""

    items: list[RunResponse]


class PaginatedPlanItemResponse(PaginatedResponse):
    """Paginated response for plan items."""

    items: list[PlanItemResponse]


class PaginatedChangeResponse(PaginatedResponse):
    """Paginated response for changes."""

    items: list[ChangeResponse]


class PaginatedVerificationResponse(PaginatedResponse):
    """Paginated response for verifications."""

    items: list[VerificationResponse]


# Dependencies
async def get_session() -> AsyncSession:
    """Get database session.

    Returns:
        AsyncSession: Database session.
    """
    async with db.session() as session:
        yield session


async def get_run_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> RunRepository:
    """Get run repository.

    Args:
        session: Database session.

    Returns:
        RunRepository: Run repository.
    """
    return RunRepository(session)


async def get_plan_item_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> PlanItemRepository:
    """Get plan item repository.

    Args:
        session: Database session.

    Returns:
        PlanItemRepository: Plan item repository.
    """
    return PlanItemRepository(session)


async def get_change_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> ChangeRepository:
    """Get change repository.

    Args:
        session: Database session.

    Returns:
        ChangeRepository: Change repository.
    """
    return ChangeRepository(session)


async def get_verification_repository(
    session: Annotated[AsyncSession, Depends(get_session)]
) -> VerificationRepository:
    """Get verification repository.

    Args:
        session: Database session.

    Returns:
        VerificationRepository: Verification repository.
    """
    return VerificationRepository(session)


# Routes
@app.get("/runs", response_model=PaginatedRunResponse)
async def list_runs(
    repository: Annotated[RunRepository, Depends(get_run_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedRunResponse:
    """List runs with pagination.

    Args:
        repository: Run repository.
        page: Page number.
        page_size: Number of items per page.

    Returns:
        PaginatedRunResponse: Paginated list of runs.
    """
    runs = await repository.list_active(limit=page_size)
    return PaginatedRunResponse(
        total=len(runs),
        page=page,
        page_size=page_size,
        has_next=False,  # TODO: Implement proper pagination
        items=[RunResponse.model_validate(run) for run in runs],
    )


@app.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str, repository: Annotated[RunRepository, Depends(get_run_repository)]
) -> RunResponse:
    """Get a run by ID.

    Args:
        run_id: Run ID.
        repository: Run repository.

    Returns:
        RunResponse: Run details.

    Raises:
        HTTPException: If run not found.
    """
    run = await repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return RunResponse.model_validate(run)


@app.get("/runs/{run_id}/plan-items", response_model=PaginatedPlanItemResponse)
async def list_run_plan_items(
    run_id: str,
    repository: Annotated[PlanItemRepository, Depends(get_plan_item_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedPlanItemResponse:
    """List plan items for a run.

    Args:
        run_id: Run ID.
        repository: Plan item repository.
        page: Page number.
        page_size: Number of items per page.

    Returns:
        PaginatedPlanItemResponse: Paginated list of plan items.
    """
    items = await repository.list_for_run(run_id)
    return PaginatedPlanItemResponse(
        total=len(items),
        page=page,
        page_size=page_size,
        has_next=False,  # TODO: Implement proper pagination
        items=[PlanItemResponse.model_validate(item) for item in items],
    )


@app.get("/plan-items/{item_id}", response_model=PlanItemResponse)
async def get_plan_item(
    item_id: str,
    repository: Annotated[PlanItemRepository, Depends(get_plan_item_repository)],
) -> PlanItemResponse:
    """Get a plan item by ID.

    Args:
        item_id: Plan item ID.
        repository: Plan item repository.

    Returns:
        PlanItemResponse: Plan item details.

    Raises:
        HTTPException: If plan item not found.
    """
    item = await repository.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Plan item not found")
    return PlanItemResponse.model_validate(item)


@app.get("/plan-items/{item_id}/changes", response_model=PaginatedChangeResponse)
async def list_plan_item_changes(
    item_id: str,
    repository: Annotated[ChangeRepository, Depends(get_change_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedChangeResponse:
    """List changes for a plan item.

    Args:
        item_id: Plan item ID.
        repository: Change repository.
        page: Page number.
        page_size: Number of items per page.

    Returns:
        PaginatedChangeResponse: Paginated list of changes.
    """
    changes = await repository.list_for_plan_item(item_id)
    return PaginatedChangeResponse(
        total=len(changes),
        page=page,
        page_size=page_size,
        has_next=False,  # TODO: Implement proper pagination
        items=[ChangeResponse.model_validate(change) for change in changes],
    )


@app.get("/changes/{change_id}", response_model=ChangeResponse)
async def get_change(
    change_id: str,
    repository: Annotated[ChangeRepository, Depends(get_change_repository)],
) -> ChangeResponse:
    """Get a change by ID.

    Args:
        change_id: Change ID.
        repository: Change repository.

    Returns:
        ChangeResponse: Change details.

    Raises:
        HTTPException: If change not found.
    """
    change = await repository.get(change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    return ChangeResponse.model_validate(change)


@app.get("/changes/{change_id}/verifications", response_model=PaginatedVerificationResponse)
async def list_change_verifications(
    change_id: str,
    repository: Annotated[VerificationRepository, Depends(get_verification_repository)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedVerificationResponse:
    """List verifications for a change.

    Args:
        change_id: Change ID.
        repository: Verification repository.
        page: Page number.
        page_size: Number of items per page.

    Returns:
        PaginatedVerificationResponse: Paginated list of verifications.
    """
    verifications = await repository.list_for_change(change_id)
    return PaginatedVerificationResponse(
        total=len(verifications),
        page=page,
        page_size=page_size,
        has_next=False,  # TODO: Implement proper pagination
        items=[VerificationResponse.model_validate(v) for v in verifications],
    )


@app.get("/verifications/{verification_id}", response_model=VerificationResponse)
async def get_verification(
    verification_id: str,
    repository: Annotated[VerificationRepository, Depends(get_verification_repository)],
) -> VerificationResponse:
    """Get a verification by ID.

    Args:
        verification_id: Verification ID.
        repository: Verification repository.

    Returns:
        VerificationResponse: Verification details.

    Raises:
        HTTPException: If verification not found.
    """
    verification = await repository.get(verification_id)
    if verification is None:
        raise HTTPException(status_code=404, detail="Verification not found")
    return VerificationResponse.model_validate(verification)


@app.on_event("startup")
async def startup() -> None:
    """Initialize database on startup."""
    await db.initialize()


@app.on_event("shutdown")
async def shutdown() -> None:
    """Close database connections on shutdown."""
    await db.close() 