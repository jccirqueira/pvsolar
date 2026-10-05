"""Camada de persistência do pvSolar Auth (PostgreSQL via SQLAlchemy 2.0)."""

from src.db.base import Base, create_engine, create_session_factory
from src.db.models import APIKeyRow, RoleRow, TenantRow, UserRow
from src.db.service import PersistenceService

__all__ = [
    "Base",
    "create_engine",
    "create_session_factory",
    "PersistenceService",
    "UserRow",
    "APIKeyRow",
    "TenantRow",
    "RoleRow",
]
