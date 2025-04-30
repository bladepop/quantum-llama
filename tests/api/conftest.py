"""Test fixtures for API tests."""
from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from db.config import db


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests.

    Returns:
        asyncio.AbstractEventLoop: Event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for tests.

    Yields:
        AsyncSession: Database session.
    """
    await db.initialize()
    async with db.session() as session:
        yield session
    await db.close() 