"""Infraestrutura de persistência do pvSolar Auth (SQLAlchemy 2.0 + PostgreSQL)."""

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
    """Base declarativa compartilhada por todos os modelos ORM."""


def create_engine(config: DatabaseConfig) -> AsyncEngine:
    """Cria o engine assíncrono a partir da configuração.

    O URL aceita ``postgresql+asyncpg://`` (produção) e
    ``sqlite+aiosqlite://`` (testes unitários).
    """
    if not config.url:
        raise ValueError("database.url nao configurado")

    kwargs: dict = {"echo": config.echo, "future": True}

    if config.url.startswith("sqlite"):
        # SQLite: sem pool de conexoes; :memory: exige pool estatico para
        # que todas as conexoes enxerguem as mesmas tabelas.
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
