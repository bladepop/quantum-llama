"""Database configuration and connection management."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from db.models import Base

logger = logging.getLogger(__name__)


class DatabaseSettings(BaseSettings):
    """Database connection settings."""

    db_url: PostgresDsn
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_echo: bool = False

    class Config:
        """Pydantic config."""

        env_prefix = "QL_"


class Database:
    """Database connection manager."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Initialize database manager.

        Args:
            settings: Database connection settings.
        """
        self.settings = settings
        self.engine: AsyncEngine | None = None
        self.async_session_maker: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        """Initialize database engine and session maker."""
        if self.engine is not None:
            return

        logger.info("Initializing database connection")
        self.engine = create_async_engine(
            str(self.settings.db_url),
            echo=self.settings.db_echo,
            pool_size=self.settings.db_pool_size,
            max_overflow=self.settings.db_max_overflow,
        )

        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables if they don't exist
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized successfully")

    async def close(self) -> None:
        """Close database connections."""
        if self.engine is None:
            return

        logger.info("Closing database connections")
        await self.engine.dispose()
        self.engine = None
        self.async_session_maker = None
        logger.info("Database connections closed")

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session.

        Yields:
            An async database session.

        Raises:
            RuntimeError: If database is not initialized.
        """
        if self.async_session_maker is None:
            raise RuntimeError("Database not initialized")

        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global database instance
db = Database(DatabaseSettings())  # type: ignore 