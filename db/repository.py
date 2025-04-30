"""Repository layer for database operations."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Change, PlanItem, Run, Verification

logger = logging.getLogger(__name__)


class Repository:
    """Base repository class with common operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository.

        Args:
            session: Database session.
        """
        self.session = session


class RunRepository(Repository):
    """Repository for Run operations."""

    async def create(self, run: Run) -> Run:
        """Create a new run.

        Args:
            run: Run to create.

        Returns:
            Created run.
        """
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: int) -> Run | None:
        """Get a run by ID.

        Args:
            run_id: Run ID.

        Returns:
            Run if found, None otherwise.
        """
        return await self.session.get(Run, run_id)

    async def list_active(self, limit: int = 10) -> Sequence[Run]:
        """List active runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            List of active runs.
        """
        stmt = (
            select(Run)
            .where(Run.completed_at.is_(None))
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def complete(self, run_id: int) -> Run | None:
        """Mark a run as complete.

        Args:
            run_id: Run ID.

        Returns:
            Updated run if found, None otherwise.
        """
        run = await self.get(run_id)
        if run is not None:
            run.completed_at = datetime.utcnow()
            await self.session.flush()
        return run


class PlanItemRepository(Repository):
    """Repository for PlanItem operations."""

    async def create(self, plan_item: PlanItem) -> PlanItem:
        """Create a new plan item.

        Args:
            plan_item: Plan item to create.

        Returns:
            Created plan item.
        """
        self.session.add(plan_item)
        await self.session.flush()
        return plan_item

    async def get(self, item_id: int) -> PlanItem | None:
        """Get a plan item by ID.

        Args:
            item_id: Plan item ID.

        Returns:
            Plan item if found, None otherwise.
        """
        return await self.session.get(PlanItem, item_id)

    async def list_for_run(self, run_id: int) -> Sequence[PlanItem]:
        """List plan items for a run.

        Args:
            run_id: Run ID.

        Returns:
            List of plan items.
        """
        stmt = select(PlanItem).where(PlanItem.run_id == run_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ChangeRepository(Repository):
    """Repository for Change operations."""

    async def create(self, change: Change) -> Change:
        """Create a new change.

        Args:
            change: Change to create.

        Returns:
            Created change.
        """
        self.session.add(change)
        await self.session.flush()
        return change

    async def get(self, change_id: int) -> Change | None:
        """Get a change by ID.

        Args:
            change_id: Change ID.

        Returns:
            Change if found, None otherwise.
        """
        return await self.session.get(Change, change_id)

    async def list_for_plan_item(self, item_id: int) -> Sequence[Change]:
        """List changes for a plan item.

        Args:
            item_id: Plan item ID.

        Returns:
            List of changes.
        """
        stmt = select(Change).where(Change.plan_item_id == item_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class VerificationRepository(Repository):
    """Repository for Verification operations."""

    async def create(self, verification: Verification) -> Verification:
        """Create a new verification.

        Args:
            verification: Verification to create.

        Returns:
            Created verification.
        """
        self.session.add(verification)
        await self.session.flush()
        return verification

    async def get(self, verification_id: int) -> Verification | None:
        """Get a verification by ID.

        Args:
            verification_id: Verification ID.

        Returns:
            Verification if found, None otherwise.
        """
        return await self.session.get(Verification, verification_id)

    async def list_for_change(self, change_id: int) -> Sequence[Verification]:
        """List verifications for a change.

        Args:
            change_id: Change ID.

        Returns:
            List of verifications.
        """
        stmt = select(Verification).where(Verification.change_id == change_id)
        result = await self.session.execute(stmt)
        return result.scalars().all() 