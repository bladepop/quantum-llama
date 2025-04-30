"""Tests for API endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.main import app
from models.change import Change
from models.plan_item import PlanItem
from models.run import Run, RunStatus
from models.verification import Verification


@pytest.fixture
def client() -> TestClient:
    """Create a test client.

    Returns:
        TestClient: Test client.
    """
    return TestClient(app)


@pytest.fixture
async def run(session: AsyncSession) -> Run:
    """Create a test run.

    Args:
        session: Database session.

    Returns:
        Run: Test run.
    """
    run = Run(
        id=str(uuid.uuid4()),
        repo_path="test/repo",
        branch="main",
        status=RunStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    return run


@pytest.fixture
async def plan_item(session: AsyncSession, run: Run) -> PlanItem:
    """Create a test plan item.

    Args:
        session: Database session.
        run: Test run.

    Returns:
        PlanItem: Test plan item.
    """
    plan_item = PlanItem(
        id=str(uuid.uuid4()),
        run_id=run.id,
        file_path="test/file.py",
        action="MODIFY",
        reason="Test reason",
        confidence=0.9,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(plan_item)
    await session.commit()
    return plan_item


@pytest.fixture
async def change(session: AsyncSession, plan_item: PlanItem) -> Change:
    """Create a test change.

    Args:
        session: Database session.
        plan_item: Test plan item.

    Returns:
        Change: Test change.
    """
    change = Change(
        id=str(uuid.uuid4()),
        plan_item_id=plan_item.id,
        file_path="test/file.py",
        patch="test patch",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(change)
    await session.commit()
    return change


@pytest.fixture
async def verification(session: AsyncSession, change: Change) -> Verification:
    """Create a test verification.

    Args:
        session: Database session.
        change: Test change.

    Returns:
        Verification: Test verification.
    """
    verification = Verification(
        id=str(uuid.uuid4()),
        change_id=change.id,
        status="PASSED",
        details={"test": "details"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(verification)
    await session.commit()
    return verification


@pytest.mark.asyncio
async def test_list_runs(client: TestClient, run: Run):
    """Test listing runs.

    Args:
        client: Test client.
        run: Test run.
    """
    response = client.get("/runs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == run.id


@pytest.mark.asyncio
async def test_get_run(client: TestClient, run: Run):
    """Test getting a run by ID.

    Args:
        client: Test client.
        run: Test run.
    """
    response = client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run.id


@pytest.mark.asyncio
async def test_list_plan_items(client: TestClient, run: Run, plan_item: PlanItem):
    """Test listing plan items for a run.

    Args:
        client: Test client.
        run: Test run.
        plan_item: Test plan item.
    """
    response = client.get(f"/runs/{run.id}/plan-items")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == plan_item.id


@pytest.mark.asyncio
async def test_get_plan_item(client: TestClient, plan_item: PlanItem):
    """Test getting a plan item by ID.

    Args:
        client: Test client.
        plan_item: Test plan item.
    """
    response = client.get(f"/plan-items/{plan_item.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == plan_item.id


@pytest.mark.asyncio
async def test_list_changes(client: TestClient, plan_item: PlanItem, change: Change):
    """Test listing changes for a plan item.

    Args:
        client: Test client.
        plan_item: Test plan item.
        change: Test change.
    """
    response = client.get(f"/plan-items/{plan_item.id}/changes")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == change.id


@pytest.mark.asyncio
async def test_get_change(client: TestClient, change: Change):
    """Test getting a change by ID.

    Args:
        client: Test client.
        change: Test change.
    """
    response = client.get(f"/changes/{change.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == change.id


@pytest.mark.asyncio
async def test_list_verifications(client: TestClient, change: Change, verification: Verification):
    """Test listing verifications for a change.

    Args:
        client: Test client.
        change: Test change.
        verification: Test verification.
    """
    response = client.get(f"/changes/{change.id}/verifications")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == verification.id


@pytest.mark.asyncio
async def test_get_verification(client: TestClient, verification: Verification):
    """Test getting a verification by ID.

    Args:
        client: Test client.
        verification: Test verification.
    """
    response = client.get(f"/verifications/{verification.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == verification.id 