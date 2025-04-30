"""Database session management."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

logger = logging.getLogger(__name__)


def create_engine(database_url: str) -> AsyncEngine:
    """Create SQLAlchemy async engine.

    Args:
        database_url: Database connection URL

    Returns:
        Async engine instance
    """
    return create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL query logging
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


async def init_db(engine: AsyncEngine) -> None:
    """Initialize database schema.

    Args:
        engine: Database engine
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database schema created")


@asynccontextmanager
async def get_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Get database session.

    Args:
        engine: Database engine

    Yields:
        Database session
    """
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise 