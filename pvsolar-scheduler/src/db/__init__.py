"""Camada de persistência do pvSolar Scheduler (PostgreSQL via SQLAlchemy 2.0)."""

from src.db.base import Base, create_engine, create_session_factory
from src.db.models import TaskResultRow, TaskRow
from src.db.service import PersistenceService

__all__ = [
    "Base",
    "create_engine",
    "create_session_factory",
    "PersistenceService",
    "TaskRow",
    "TaskResultRow",
]
