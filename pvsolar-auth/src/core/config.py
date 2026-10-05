"""Configuração central do pvSolar Auth."""

from __future__ import annotations

import os
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API = "api"


class Permission(StrEnum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    MANAGE_USERS = "manage_users"
    MANAGE_TENANTS = "manage_tenants"
    VIEW_DASHBOARD = "view_dashboard"
    MANAGE_ALERTS = "manage_alerts"
    EXPORT_DATA = "export_data"


class TenantStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    LOCKED = "locked"
    PASSWORD_EXPIRED = "password_expired"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class JWTConfig(BaseModel):
    """Configuração JWT."""
    secret_key: str = Field(default="pvsolar-secret-key-change-in-production")
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=30)
    refresh_token_expire_days: int = Field(default=7)
    issuer: str = Field(default="pvsolar-auth")
    audience: str = Field(default="pvsolar")


class PasswordConfig(BaseModel):
    """Configuração de senha."""
    min_length: int = Field(default=8)
    require_uppercase: bool = Field(default=True)
    require_lowercase: bool = Field(default=True)
    require_digit: bool = Field(default=True)
    require_special: bool = Field(default=True)
    max_age_days: int = Field(default=90)
    history_count: int = Field(default=5)


class RateLimitConfig(BaseModel):
    """Configuração de rate limiting."""
    login_attempts: int = Field(default=5)
    login_lockout_minutes: int = Field(default=15)
    api_requests_per_minute: int = Field(default=100)
    api_requests_per_hour: int = Field(default=1000)


class SessionConfig(BaseModel):
    """Configuração de sessão."""
    max_sessions: int = Field(default=5)
    session_timeout_minutes: int = Field(default=60)
    absolute_timeout_minutes: int = Field(default=480)


class OAuthConfig(BaseModel):
    """Configuração OAuth2."""
    enabled: bool = Field(default=False)
    client_id: str = Field(default="")
    client_secret: str = Field(default="")
    authorization_url: str = Field(default="")
    token_url: str = Field(default="")
    userinfo_url: str = Field(default="")
    redirect_uri: str = Field(default="")
    scopes: list[str] = Field(default_factory=list)


class RBACConfig(BaseModel):
    """Configuração RBAC."""
    default_role: UserRole = Field(default=UserRole.VIEWER)
    role_hierarchy: dict[str, list[str]] = Field(default_factory=dict)


class TenantConfig(BaseModel):
    """Configuração de tenant."""
    max_users: int = Field(default=100)
    max_api_keys: int = Field(default=10)
    features: list[str] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    """Configuração da camada de persistência (PostgreSQL).

    A persistência é opcional: quando ``enabled`` é falso o serviço roda
    somente em memória (comportamento original, útil para testes unitários).
    Definir a variável de ambiente ``PVSOLAR_DATABASE_URL`` ativa a
    persistência automaticamente.
    """
    enabled: bool = Field(default=False)
    url: str = Field(default="")  # postgresql+asyncpg://user:senha@host:5432/pvsolar_auth
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5, ge=1)
    max_overflow: int = Field(default=10, ge=0)
    pool_timeout: int = Field(default=30, ge=1)
    create_tables: bool = Field(default=True)
    hydrate_on_startup: bool = Field(default=True)


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8007)
    title: str = Field(default="pvSolar Auth API")


class SeedConfig(BaseModel):
    """Configuração do usuário seed criado no startup."""
    enabled: bool = Field(default=True)
    username: str = Field(default="admin")
    email: str = Field(default="admin@pvsolar.com")
    password: str = Field(default="admin123")
    full_name: str = Field(default="Administrador")
    role: UserRole = Field(default=UserRole.ADMIN)
    tenant_id: str = Field(default="default")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    format: str = Field(default="json")


class AuthConfig(BaseModel):
    """Configuração principal do pvSolar Auth."""
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
            "http://localhost:3002",
            "http://127.0.0.1:3002",
        ]
    )
    password: PasswordConfig = Field(default_factory=PasswordConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    session: SessionConfig = Field(default_factory=SessionConfig)
    oauth: OAuthConfig = Field(default_factory=OAuthConfig)
    rbac: RBACConfig = Field(default_factory=RBACConfig)
    tenant: TenantConfig = Field(default_factory=TenantConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    seed: SeedConfig = Field(default_factory=SeedConfig)
    company_name: str = Field(default="pvSolar Auth")
    debug: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _apply_env_overrides(config: AuthConfig) -> AuthConfig:
    """Sobrepõe a configuração com variáveis de ambiente (12-factor).

    Variáveis suportadas:
      * ``PVSOLAR_DATABASE_URL`` — URL do PostgreSQL; ao ser definida,
        ativa a persistência automaticamente.
      * ``PVSOLAR_DB_ENABLED``   — força ``database.enabled`` (1/true/0/false).
    """
    url = os.environ.get("PVSOLAR_DATABASE_URL", "").strip()
    if url:
        config.database.url = url
        config.database.enabled = True

    enabled = os.environ.get("PVSOLAR_DB_ENABLED")
    if enabled is not None:
        config.database.enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}

    return config


def _default_config_path() -> Path | None:
    """Caminho padrão do arquivo de configuração, quando não informado.

    Precedência:
      1. Variável de ambiente ``PVSOLAR_CONFIG`` (caminho arbitrário)
      2. ``config/auth.yaml`` na raiz do projeto (copiado do example)

    Retorna ``None`` quando não há arquivo, sinalizando "usar padrões".
    """
    env = os.environ.get("PVSOLAR_CONFIG", "").strip()
    if env:
        return Path(env)
    candidate = Path(__file__).resolve().parents[2] / "config" / "auth.yaml"
    return candidate if candidate.exists() else None


def load_config(config_path: str | Path | None = None) -> AuthConfig:
    """Carrega config do arquivo YAML ou retorna padrão.

    Sem caminho explícito, procura ``PVSOLAR_CONFIG`` e depois
    ``config/auth.yaml``. Em qualquer caso, as variáveis de ambiente
    (ex.: ``PVSOLAR_DATABASE_URL``) têm prioridade sobre o arquivo.
    """
    if config_path is None:
        config_path = _default_config_path()
        if config_path is None:
            return _apply_env_overrides(AuthConfig())

    path = Path(config_path)
    if not path.exists():
        return _apply_env_overrides(AuthConfig())

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return _apply_env_overrides(AuthConfig(**data))
