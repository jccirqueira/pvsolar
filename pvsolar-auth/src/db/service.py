"""Serviço de persistência do pvSolar Auth.

Responsável por:

1. **Startup** — criar o schema (``create_tables``) e carregar o estado do
   PostgreSQL para os gerenciadores em memória (``hydrate``).
2. **Write-through** — gravar cada mutação feita pela API (``save_user``,
   ``save_tenant``, ...) de forma síncrona com a resposta HTTP.

A camada de domínio (``UserManager``, ``TenantManager``, ``RBACEngine``)
continua sendo a fonte de leitura em runtime — o banco é a fonte de
verdade entre reinícios. Assim os 118 testes de domínio existentes seguem
intactos e a persistência fica isolada e testável.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select

from src.core.config import DatabaseConfig, Permission, TenantStatus, UserRole, UserStatus
from src.db.base import Base, create_engine, create_session_factory
from src.db.models import APIKeyRow, RoleRow, TenantRow, UserRow
from src.rbac.rbac_engine import RBACEngine, Role
from src.tenants.tenant_manager import Tenant, TenantManager
from src.users.user_manager import APIKey, User, UserManager

logger = structlog.get_logger()


def _as_utc(value: datetime | None) -> datetime | None:
    """Garante datetime com fuso horário.

    O PostgreSQL devolve datetime aware; o SQLite devolve naive. Sem esta
    normalização, comparações como ``locked_until > now(UTC)`` lançariam
    ``TypeError`` de mistura aware/naive.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


# ---------------------------------------------------------------------------
# Mapeamento row <-> domínio
# ---------------------------------------------------------------------------

def _user_from_row(row: UserRow, api_key_ids: list[str]) -> User:
    return User(
        id=row.id,
        username=row.username,
        email=row.email,
        hashed_password=row.hashed_password,
        full_name=row.full_name,
        role=UserRole(row.role),
        status=UserStatus(row.status),
        tenant_id=row.tenant_id,
        created_at=_as_utc(row.created_at) or datetime.now(UTC),
        updated_at=_as_utc(row.updated_at) or datetime.now(UTC),
        last_login=_as_utc(row.last_login),
        login_attempts=row.login_attempts or 0,
        locked_until=_as_utc(row.locked_until),
        api_keys=list(api_key_ids),
    )


def _apply_user(row: UserRow, user: User) -> None:
    row.username = user.username
    row.email = user.email
    row.hashed_password = user.hashed_password
    row.full_name = user.full_name
    row.role = user.role.value
    row.status = user.status.value
    row.tenant_id = user.tenant_id
    row.created_at = user.created_at
    row.updated_at = user.updated_at
    row.last_login = user.last_login
    row.login_attempts = user.login_attempts
    row.locked_until = user.locked_until


def _api_key_from_row(row: APIKeyRow) -> APIKey:
    return APIKey(
        id=row.id,
        key=row.key,
        name=row.name,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        created_at=_as_utc(row.created_at) or datetime.now(UTC),
        expires_at=_as_utc(row.expires_at),
        is_active=row.is_active,
        permissions=list(row.permissions or []),
    )


def _apply_api_key(row: APIKeyRow, api_key: APIKey) -> None:
    row.key = api_key.key
    row.name = api_key.name
    row.user_id = api_key.user_id
    row.tenant_id = api_key.tenant_id
    row.created_at = api_key.created_at
    row.expires_at = api_key.expires_at
    row.is_active = api_key.is_active
    row.permissions = list(api_key.permissions or [])


def _tenant_from_row(row: TenantRow) -> Tenant:
    return Tenant(
        id=row.id,
        name=row.name,
        slug=row.slug,
        status=TenantStatus(row.status),
        created_at=_as_utc(row.created_at) or datetime.now(UTC),
        updated_at=_as_utc(row.updated_at) or datetime.now(UTC),
        max_users=row.max_users,
        max_api_keys=row.max_api_keys,
        features=list(row.features or []),
        settings=dict(row.settings or {}),
    )


def _apply_tenant(row: TenantRow, tenant: Tenant) -> None:
    row.name = tenant.name
    row.slug = tenant.slug
    row.status = tenant.status.value
    row.created_at = tenant.created_at
    row.updated_at = tenant.updated_at
    row.max_users = tenant.max_users
    row.max_api_keys = tenant.max_api_keys
    row.features = list(tenant.features or [])
    row.settings = dict(tenant.settings or {})


def _role_from_row(row: RoleRow) -> Role:
    return Role(
        id=row.id,
        name=row.name,
        description=row.description,
        permissions=[Permission(p) for p in (row.permissions or [])],
        is_default=row.is_default,
        created_at=_as_utc(row.created_at) or datetime.now(UTC),
    )


def _apply_role(row: RoleRow, role: Role) -> None:
    row.name = role.name
    row.description = role.description
    row.permissions = [p.value for p in role.permissions]
    row.is_default = role.is_default
    row.created_at = role.created_at


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------

class PersistenceService:
    """Façade de persistência (engine + sessões + hidratação)."""

    def __init__(self, config: DatabaseConfig) -> None:
        self.config = config
        self._engine = None
        self._sessions = None

    @property
    def enabled(self) -> bool:
        """Persistência ativa na configuração atual."""
        return self.config.enabled

    @property
    def started(self) -> bool:
        """Engine criado (``startup`` concluído)."""
        return self._sessions is not None

    # -- ciclo de vida ----------------------------------------------------

    async def startup(self) -> None:
        """Cria engine e schema (idempotente). No-op se desativado."""
        if not self.enabled:
            logger.info("database.disabled", reason="database.enabled=false")
            return

        self._engine = create_engine(self.config)
        self._sessions = create_session_factory(self._engine)

        if self.config.create_tables:
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        logger.info("database.started", url=_safe_url(self.config.url))

    async def dispose(self) -> None:
        """Fecha o pool de conexões (shutdown gracioso)."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessions = None
            logger.info("database.disposed")

    async def ping(self) -> bool:
        """Verifica conectividade (usado no /health)."""
        if not self.enabled:
            return False
        if self._sessions is None:
            return False
        try:
            from sqlalchemy import text

            async with self._sessions() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception as exc:  # pragma: no cover - depende da infra
            logger.warning("database.ping_failed", error=str(exc))
            return False

    def _require(self):
        if self._sessions is None:
            raise RuntimeError("PersistenceService.startup() nao foi chamado")
        return self._sessions

    # -- hidratação -------------------------------------------------------

    async def hydrate(
        self,
        user_manager: UserManager,
        tenant_manager: TenantManager,
        rbac_engine: RBACEngine,
    ) -> dict:
        """Carrega o estado do banco para os gerenciadores em memória.

        O banco é a fonte de verdade: se existirem roles no banco elas
        substituem as roles padrão criadas no construtor do ``RBACEngine``.
        """
        if not self.enabled:
            return {"users": 0, "api_keys": 0, "tenants": 0, "roles": 0}

        sessions = self._require()

        async with sessions() as session:
            user_rows = (await session.execute(select(UserRow))).scalars().all()
            key_rows = (await session.execute(select(APIKeyRow))).scalars().all()
            tenant_rows = (await session.execute(select(TenantRow))).scalars().all()
            role_rows = (await session.execute(select(RoleRow))).scalars().all()

        # --- usuários + chaves de API ---
        keys_by_user: dict[str, list[str]] = {}
        for key_row in key_rows:
            api_key = _api_key_from_row(key_row)
            user_manager.api_keys[api_key.id] = api_key
            keys_by_user.setdefault(api_key.user_id, []).append(api_key.id)

        user_manager.users.clear()
        user_manager.username_index.clear()
        user_manager.email_index.clear()
        for row in user_rows:
            user = _user_from_row(row, keys_by_user.get(row.id, []))
            user_manager.users[user.id] = user
            user_manager.username_index[user.username] = user.id
            user_manager.email_index[user.email] = user.id

        # --- tenants ---
        tenant_manager.tenants.clear()
        tenant_manager.slug_index.clear()
        for row in tenant_rows:
            tenant = _tenant_from_row(row)
            tenant_manager.tenants[tenant.id] = tenant
            tenant_manager.slug_index[tenant.slug] = tenant.id

        # --- roles (banco substitui as padrão quando existe registro) ---
        roles_loaded = 0
        if role_rows:
            rbac_engine.roles.clear()
            rbac_engine.role_name_index.clear()
            for row in role_rows:
                role = _role_from_row(row)
                rbac_engine.roles[role.id] = role
                rbac_engine.role_name_index[role.name] = role.id
                roles_loaded += 1

        stats = {
            "users": len(user_rows),
            "api_keys": len(key_rows),
            "tenants": len(tenant_rows),
            "roles": roles_loaded,
        }
        logger.info("database.hydrated", **stats)
        return stats

    # -- usuários ---------------------------------------------------------

    async def save_user(self, user: User) -> None:
        """Insere ou atualiza um usuário."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            row = await session.get(UserRow, user.id)
            if row is None:
                row = UserRow(id=user.id)
                session.add(row)
            _apply_user(row, user)
            await session.commit()
        logger.debug("database.user_saved", user_id=user.id, username=user.username)

    async def delete_user(self, user_id: str) -> None:
        """Remove um usuário e suas chaves de API."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            await session.execute(delete(APIKeyRow).where(APIKeyRow.user_id == user_id))
            await session.execute(delete(UserRow).where(UserRow.id == user_id))
            await session.commit()
        logger.debug("database.user_deleted", user_id=user_id)

    async def save_api_key(self, api_key: APIKey) -> None:
        """Insere ou atualiza uma chave de API."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            row = await session.get(APIKeyRow, api_key.id)
            if row is None:
                row = APIKeyRow(id=api_key.id)
                session.add(row)
            _apply_api_key(row, api_key)
            await session.commit()

    # -- tenants ----------------------------------------------------------

    async def save_tenant(self, tenant: Tenant) -> None:
        """Insere ou atualiza um tenant."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            row = await session.get(TenantRow, tenant.id)
            if row is None:
                row = TenantRow(id=tenant.id)
                session.add(row)
            _apply_tenant(row, tenant)
            await session.commit()
        logger.debug("database.tenant_saved", tenant_id=tenant.id, slug=tenant.slug)

    async def delete_tenant(self, tenant_id: str) -> None:
        """Remove um tenant."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            await session.execute(delete(TenantRow).where(TenantRow.id == tenant_id))
            await session.commit()

    # -- roles ------------------------------------------------------------

    async def save_role(self, role: Role) -> None:
        """Insere ou atualiza uma role."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            row = await session.get(RoleRow, role.id)
            if row is None:
                row = RoleRow(id=role.id)
                session.add(row)
            _apply_role(row, role)
            await session.commit()

    async def save_roles(self, rbac_engine: RBACEngine) -> int:
        """Persiste todas as roles em memória (upsert). Retorna o total."""
        if not self.enabled:
            return 0
        for role in list(rbac_engine.roles.values()):
            await self.save_role(role)
        return len(rbac_engine.roles)

    async def delete_role(self, role_id: str) -> None:
        """Remove uma role."""
        if not self.enabled:
            return
        sessions = self._require()
        async with sessions() as session:
            await session.execute(delete(RoleRow).where(RoleRow.id == role_id))
            await session.commit()


def _safe_url(url: str) -> str:
    """Mascara a senha da URL antes de logar."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.rsplit("@", 1)
    user = creds.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"
