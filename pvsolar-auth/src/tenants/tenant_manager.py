"""Gerenciador de tenants (multi-tenant)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from src.core.config import TenantStatus

logger = structlog.get_logger()


@dataclass
class Tenant:
    """Representa um tenant."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    slug: str = ""
    status: TenantStatus = TenantStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    max_users: int = 100
    max_api_keys: int = 10
    features: list[str] = field(default_factory=list)
    settings: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "max_users": self.max_users,
            "max_api_keys": self.max_api_keys,
            "features": self.features,
        }


class TenantManager:
    """Gerencia tenants."""

    def __init__(self) -> None:
        self.tenants: dict[str, Tenant] = {}
        self.slug_index: dict[str, str] = {}

    def create_tenant(
        self,
        name: str,
        slug: str,
        max_users: int = 100,
        max_api_keys: int = 10,
        features: list[str] | None = None,
    ) -> Tenant:
        """Cria um novo tenant."""
        if slug in self.slug_index:
            raise ValueError(f"Tenant slug '{slug}' already exists")

        tenant = Tenant(
            name=name,
            slug=slug,
            max_users=max_users,
            max_api_keys=max_api_keys,
            features=features or [],
        )
        self.tenants[tenant.id] = tenant
        self.slug_index[slug] = tenant.id
        logger.info("tenant.created", tenant_id=tenant.id, name=name)
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Busca tenant por ID."""
        return self.tenants.get(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Busca tenant por slug."""
        tenant_id = self.slug_index.get(slug)
        if tenant_id:
            return self.tenants.get(tenant_id)
        return None

    def update_tenant(self, tenant_id: str, **kwargs) -> bool:
        """Atualiza um tenant."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        for key, value in kwargs.items():
            if hasattr(tenant, key) and key not in ("id", "created_at"):
                setattr(tenant, key, value)
        tenant.updated_at = datetime.now(UTC)
        logger.info("tenant.updated", tenant_id=tenant_id)
        return True

    def delete_tenant(self, tenant_id: str) -> bool:
        """Deleta um tenant."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        self.slug_index.pop(tenant.slug, None)
        del self.tenants[tenant_id]
        logger.info("tenant.deleted", tenant_id=tenant_id)
        return True

    def suspend_tenant(self, tenant_id: str) -> bool:
        """Suspende um tenant."""
        return self.update_tenant(tenant_id, status=TenantStatus.SUSPENDED)

    def activate_tenant(self, tenant_id: str) -> bool:
        """Ativa um tenant."""
        return self.update_tenant(tenant_id, status=TenantStatus.ACTIVE)

    def get_active_tenants(self) -> list[Tenant]:
        """Retorna tenants ativos."""
        return [
            t for t in self.tenants.values() if t.status == TenantStatus.ACTIVE
        ]

    def get_tenants_by_status(self, status: TenantStatus) -> list[Tenant]:
        """Retorna tenants por status."""
        return [t for t in self.tenants.values() if t.status == status]

    def check_user_limit(self, tenant_id: str, current_count: int) -> bool:
        """Verifica se tenant atingiu limite de usuários."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        return current_count < tenant.max_users

    def add_feature(self, tenant_id: str, feature: str) -> bool:
        """Adiciona feature ao tenant."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        if feature not in tenant.features:
            tenant.features.append(feature)
        return True

    def remove_feature(self, tenant_id: str, feature: str) -> bool:
        """Remove feature do tenant."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        if feature in tenant.features:
            tenant.features.remove(feature)
        return True

    def has_feature(self, tenant_id: str, feature: str) -> bool:
        """Verifica se tenant tem uma feature."""
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            return False
        return feature in tenant.features

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        by_status = {}
        for s in TenantStatus:
            by_status[s.value] = sum(
                1 for t in self.tenants.values() if t.status == s
            )
        return {
            "total_tenants": len(self.tenants),
            "by_status": by_status,
        }

    def clear(self) -> int:
        """Limpa todos os tenants."""
        count = len(self.tenants)
        self.tenants.clear()
        self.slug_index.clear()
        return count
