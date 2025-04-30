"""Database connection utilities."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Default to SQLite database in data directory
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///data/app.db"

# Get database URL from environment or use default
database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# Create async engine
engine = create_async_engine(
    database_url,
    echo=False,  # Set to True for SQL query logging
    future=True,
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session.

    Yields:
        AsyncSession: Database session

    Example:
        async with get_session() as session:
            result = await session.execute(...)
            await session.commit()
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise 