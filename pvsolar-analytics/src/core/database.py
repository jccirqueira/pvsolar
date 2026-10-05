"""
Database module - TimescaleDB connection and session management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = structlog.get_logger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_database(url: str, pool_size: int = 10, echo: bool = False) -> AsyncEngine:
    """
    Initialize the database engine and session factory.

    Args:
        url: Database connection URL
        pool_size: Connection pool size
        echo: Enable SQL logging

    Returns:
        AsyncEngine instance
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        url,
        pool_size=pool_size,
        echo=echo,
        pool_pre_ping=True,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Test connection
    async with _engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        result.scalar()

    logger.info("database.initialized", url=url.split("@")[-1], pool_size=pool_size)
    return _engine


async def close_database():
    """Close the database engine and all connections."""
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database.closed")


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session from the pool.

    Yields:
        AsyncSession instance

    Raises:
        RuntimeError: If database is not initialized
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def execute_query(query: str, params: dict | None = None) -> list[dict]:
    """
    Execute a raw SQL query and return results as dictionaries.

    Args:
        query: SQL query string
        params: Query parameters

    Returns:
        List of dictionaries with query results
    """
    async with get_session() as session:
        result = await session.execute(text(query), params or {})
        columns = result.keys()
        return [dict(zip(columns, row)) for row in result.fetchall()]


async def check_database_health() -> dict:
    """
    Check database health.

    Returns:
        Dictionary with health status
    """
    try:
        async with get_session() as session:
            result = await session.execute(text("SELECT 1"))
            result.scalar()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}
