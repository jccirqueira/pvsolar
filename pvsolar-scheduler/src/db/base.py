"""Infraestrutura de persistência do pvSolar Scheduler (SQLAlchemy 2.0)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.core.config import DatabaseConfig


class Base(DeclarativeBase):
    """Base declarativa compartilhada pelos modelos ORM."""


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """Cria o engine assíncrono (``postgresql+asyncpg`` ou ``sqlite+aiosqlite``)."""
    if not config.url:
        raise ValueError("database.url nao configurado")

    kwargs: dict = {"echo": config.echo, "future": True}

    if config.url.startswith("sqlite"):
        if ":memory:" in config.url:
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(
            pool_size=config.pool_size,
            max_overflow=config.max_overflow,
            pool_timeout=config.pool_timeout,
        )

    return create_async_engine(config.url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Cria a factory de sessões (``expire_on_commit=False`` evita queries extras)."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
