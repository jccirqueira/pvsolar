"""Sistema RBAC (Role-Based Access Control)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import structlog

from src.core.config import Permission

logger = structlog.get_logger()


@dataclass
class Role:
    """Representa uma role."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    permissions: list[Permission] = field(default_factory=list)
    is_default: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.value for p in self.permissions],
            "is_default": self.is_default,
        }


@dataclass
class Policy:
    """Política de acesso."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    effect: str = "allow"  # allow or deny
    resources: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effect": self.effect,
            "resources": self.resources,
            "actions": self.actions,
            "roles": self.roles,
        }


class RBACEngine:
    """Engine RBAC."""

    def __init__(self) -> None:
        self.roles: dict[str, Role] = {}
        self.policies: dict[str, Policy] = {}
        self.role_name_index: dict[str, str] = {}
        self._setup_default_roles()

    def _setup_default_roles(self) -> None:
        """Configura roles padrão."""
        self.create_role(
            name="super_admin",
            description="Super Administrador com acesso total",
            permissions=list(Permission),
        )
        self.create_role(
            name="admin",
            description="Administrador com acesso amplo",
            permissions=[
                Permission.READ, Permission.WRITE, Permission.DELETE,
                Permission.MANAGE_USERS, Permission.VIEW_DASHBOARD,
                Permission.MANAGE_ALERTS, Permission.EXPORT_DATA,
            ],
        )
        self.create_role(
            name="operator",
            description="Operador com acesso operacional",
            permissions=[
                Permission.READ, Permission.WRITE,
                Permission.VIEW_DASHBOARD, Permission.MANAGE_ALERTS,
            ],
        )
        self.create_role(
            name="viewer",
            description="Visualizador com acesso somente leitura",
            permissions=[Permission.READ, Permission.VIEW_DASHBOARD],
        )
        self.create_role(
            name="api",
            description="Acesso via API",
            permissions=[Permission.READ, Permission.EXPORT_DATA],
        )

    def create_role(
        self,
        name: str,
        description: str = "",
        permissions: list[Permission] | None = None,
    ) -> Role:
        """Cria uma role."""
        role = Role(
            name=name,
            description=description,
            permissions=permissions or [],
        )
        self.roles[role.id] = role
        self.role_name_index[name] = role.id
        logger.info("role.created", role_id=role.id, name=name)
        return role

    def get_role(self, role_id: str) -> Role | None:
        """Busca role por ID."""
        return self.roles.get(role_id)

    def get_role_by_name(self, name: str) -> Role | None:
        """Busca role por nome."""
        role_id = self.role_name_index.get(name)
        if role_id:
            return self.roles.get(role_id)
        return None

    def update_role(self, role_id: str, **kwargs) -> bool:
        """Atualiza uma role."""
        role = self.get_role(role_id)
        if role is None:
            return False
        for key, value in kwargs.items():
            if hasattr(role, key) and key != "id":
                setattr(role, key, value)
        logger.info("role.updated", role_id=role_id)
        return True

    def delete_role(self, role_id: str) -> bool:
        """Deleta uma role."""
        role = self.get_role(role_id)
        if role is None:
            return False
        self.role_name_index.pop(role.name, None)
        del self.roles[role_id]
        logger.info("role.deleted", role_id=role_id)
        return True

    def add_permission_to_role(self, role_id: str, permission: Permission) -> bool:
        """Adiciona permissão a uma role."""
        role = self.get_role(role_id)
        if role is None:
            return False
        if permission not in role.permissions:
            role.permissions.append(permission)
        return True

    def remove_permission_from_role(self, role_id: str, permission: Permission) -> bool:
        """Remove permissão de uma role."""
        role = self.get_role(role_id)
        if role is None:
            return False
        if permission in role.permissions:
            role.permissions.remove(permission)
        return True

    def create_policy(
        self,
        name: str,
        effect: str = "allow",
        resources: list[str] | None = None,
        actions: list[str] | None = None,
        roles: list[str] | None = None,
    ) -> Policy:
        """Cria uma política."""
        policy = Policy(
            name=name,
            effect=effect,
            resources=resources or [],
            actions=actions or [],
            roles=roles or [],
        )
        self.policies[policy.id] = policy
        logger.info("policy.created", policy_id=policy.id, name=name)
        return policy

    def get_policy(self, policy_id: str) -> Policy | None:
        """Busca política por ID."""
        return self.policies.get(policy_id)

    def delete_policy(self, policy_id: str) -> bool:
        """Deleta uma política."""
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False

    def check_permission(self, role_name: str, permission: Permission) -> bool:
        """Verifica se uma role tem uma permissão."""
        role = self.get_role_by_name(role_name)
        if role is None:
            return False
        return permission in role.permissions

    def check_any_permission(self, role_name: str, permissions: list[Permission]) -> bool:
        """Verifica se uma role tem qualquer uma das permissões."""
        role = self.get_role_by_name(role_name)
        if role is None:
            return False
        return any(p in role.permissions for p in permissions)

    def check_all_permissions(self, role_name: str, permissions: list[Permission]) -> bool:
        """Verifica se uma role tem todas as permissões."""
        role = self.get_role_by_name(role_name)
        if role is None:
            return False
        return all(p in role.permissions for p in permissions)

    def get_role_permissions(self, role_name: str) -> list[Permission]:
        """Retorna permissões de uma role."""
        role = self.get_role_by_name(role_name)
        if role is None:
            return []
        return list(role.permissions)

    def get_roles_with_permission(self, permission: Permission) -> list[Role]:
        """Retorna roles que têm uma permissão."""
        return [
            r for r in self.roles.values() if permission in r.permissions
        ]

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        return {
            "total_roles": len(self.roles),
            "total_policies": len(self.policies),
            "roles": {r.name: len(r.permissions) for r in self.roles.values()},
        }

    def clear(self) -> int:
        """Limpa roles e políticas."""
        count = len(self.roles) + len(self.policies)
        self.roles.clear()
        self.policies.clear()
        self.role_name_index.clear()
        self._setup_default_roles()
        return count
