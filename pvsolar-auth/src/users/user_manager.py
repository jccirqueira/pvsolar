"""Gerenciador de usuários."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import structlog

from src.core.config import UserRole, UserStatus

logger = structlog.get_logger()


@dataclass
class User:
    """Representa um usuário."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    hashed_password: str = ""
    full_name: str = ""
    role: UserRole = UserRole.VIEWER
    status: UserStatus = UserStatus.ACTIVE
    tenant_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_login: datetime | None = None
    login_attempts: int = 0
    locked_until: datetime | None = None
    api_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role.value,
            "status": self.status.value,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "login_attempts": self.login_attempts,
            "api_keys_count": len(self.api_keys),
        }


@dataclass
class APIKey:
    """Chave de API."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    name: str = ""
    user_id: str = ""
    tenant_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    is_active: bool = True
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key[:8] + "...",
            "name": self.name,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
        }


def hash_password(password: str) -> str:
    """Hash de senha com SHA-256 + salt."""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """Verifica senha."""
    if ":" not in hashed:
        return False
    salt, hash_val = hashed.split(":", 1)
    computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return computed == hash_val


class UserManager:
    """Gerencia usuários."""

    def __init__(self, login_lockout_minutes: int = 15) -> None:
        # Janela de bloqueio após exceder as tentativas de login
        # (rate_limit.login_lockout_minutes na configuração).
        self.login_lockout_minutes = login_lockout_minutes
        self.users: dict[str, User] = {}
        self.api_keys: dict[str, APIKey] = {}
        self.username_index: dict[str, str] = {}
        self.email_index: dict[str, str] = {}

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str = "",
        role: UserRole = UserRole.VIEWER,
        tenant_id: str = "",
    ) -> User:
        """Cria um novo usuário."""
        if username in self.username_index:
            raise ValueError(f"Username '{username}' already exists")
        if email in self.email_index:
            raise ValueError(f"Email '{email}' already exists")

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            tenant_id=tenant_id,
        )
        self.users[user.id] = user
        self.username_index[username] = user.id
        self.email_index[email] = user.id
        logger.info("user.created", user_id=user.id, username=username)
        return user

    def get_user(self, user_id: str) -> User | None:
        """Busca usuário por ID."""
        return self.users.get(user_id)

    def get_user_by_username(self, username: str) -> User | None:
        """Busca usuário por username."""
        user_id = self.username_index.get(username)
        if user_id:
            return self.users.get(user_id)
        return None

    def get_user_by_email(self, email: str) -> User | None:
        """Busca usuário por email."""
        user_id = self.email_index.get(email)
        if user_id:
            return self.users.get(user_id)
        return None

    def update_user(self, user_id: str, **kwargs) -> bool:
        """Atualiza um usuário."""
        user = self.get_user(user_id)
        if user is None:
            return False

        for key, value in kwargs.items():
            if hasattr(user, key) and key not in ("id", "created_at"):
                setattr(user, key, value)

        user.updated_at = datetime.now(UTC)
        logger.info("user.updated", user_id=user_id)
        return True

    def delete_user(self, user_id: str) -> bool:
        """Deleta um usuário."""
        user = self.get_user(user_id)
        if user is None:
            return False

        self.username_index.pop(user.username, None)
        self.email_index.pop(user.email, None)
        del self.users[user_id]
        logger.info("user.deleted", user_id=user_id)
        return True

    def authenticate(self, username: str, password: str) -> User | None:
        """Autentica um usuário."""
        user = self.get_user_by_username(username)
        if user is None:
            return None

        if user.status == UserStatus.LOCKED:
            if user.locked_until and user.locked_until > datetime.now(UTC):
                logger.warning("user.locked", user_id=user.id)
                return None
            user.status = UserStatus.ACTIVE
            user.login_attempts = 0

        if not verify_password(password, user.hashed_password):
            user.login_attempts += 1
            if user.login_attempts >= 5:
                user.status = UserStatus.LOCKED
                # Bloqueio com janela real: sem ela o bloqueio expirava no
                # mesmo instante em que era aplicado (auto-liberação).
                user.locked_until = datetime.now(UTC) + timedelta(
                    minutes=self.login_lockout_minutes
                )
            logger.warning("user.auth_failed", user_id=user.id, attempts=user.login_attempts)
            return None

        user.login_attempts = 0
        user.last_login = datetime.now(UTC)
        user.status = UserStatus.ACTIVE
        logger.info("user.authenticated", user_id=user.id)
        return user

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Altera senha do usuário."""
        user = self.get_user(user_id)
        if user is None:
            return False
        user.hashed_password = hash_password(new_password)
        user.updated_at = datetime.now(UTC)
        logger.info("user.password_changed", user_id=user_id)
        return True

    def create_api_key(self, user_id: str, name: str) -> APIKey | None:
        """Cria uma chave de API."""
        user = self.get_user(user_id)
        if user is None:
            return None
        api_key = APIKey(name=name, user_id=user_id, tenant_id=user.tenant_id)
        self.api_keys[api_key.id] = api_key
        user.api_keys.append(api_key.id)
        logger.info("apikey.created", key_id=api_key.id, user_id=user_id)
        return api_key

    def validate_api_key(self, key: str) -> APIKey | None:
        """Valida uma chave de API."""
        for api_key in self.api_keys.values():
            if api_key.key == key and api_key.is_active:
                return api_key
        return None

    def revoke_api_key(self, key_id: str) -> bool:
        """Revoga uma chave de API."""
        api_key = self.api_keys.get(key_id)
        if api_key is None:
            return False
        api_key.is_active = False
        logger.info("apikey.revoked", key_id=key_id)
        return True

    def get_users_by_tenant(self, tenant_id: str) -> list[User]:
        """Retorna usuários por tenant."""
        return [u for u in self.users.values() if u.tenant_id == tenant_id]

    def get_users_by_role(self, role: UserRole) -> list[User]:
        """Retorna usuários por role."""
        return [u for u in self.users.values() if u.role == role]

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        by_status = {}
        for s in UserStatus:
            by_status[s.value] = sum(
                1 for u in self.users.values() if u.status == s
            )
        by_role = {}
        for r in UserRole:
            by_role[r.value] = sum(
                1 for u in self.users.values() if u.role == r
            )
        return {
            "total_users": len(self.users),
            "total_api_keys": len(self.api_keys),
            "by_status": by_status,
            "by_role": by_role,
        }

    def clear(self) -> int:
        """Limpa todos os usuários."""
        count = len(self.users)
        self.users.clear()
        self.api_keys.clear()
        self.username_index.clear()
        self.email_index.clear()
        return count
