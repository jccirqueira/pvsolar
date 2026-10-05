"""Testes da camada de persistência do pvSolar Auth (PostgreSQL).

Roda por padrão em SQLite (aiosqlite) para ser reproduzível em qualquer
máquina. Para validar contra um PostgreSQL real:

    set PVSOLAR_TEST_DB_URL=postgresql+asyncpg://postgres:senha@localhost:5432/pvsolar_auth_test
    .\\venv\\Scripts\\python.exe -m pytest tests/test_persistence.py -q

ATENCAO: o schema e dropado/criado a cada teste. Use SEMPRE um banco
dedicado de testes (o sufixo ``_test`` e criado por
``scripts\\create_databases.py``) e nunca aponte ``PVSOLAR_TEST_DB_URL``
para o banco de producao.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from src.api.app import create_app
from src.core.config import (
    AuthConfig,
    DatabaseConfig,
    Permission,
    TenantStatus,
    UserRole,
    UserStatus,
)
from src.db.base import Base, create_engine
from src.db.service import PersistenceService, _safe_url
from src.rbac.rbac_engine import RBACEngine
from src.tenants.tenant_manager import TenantManager
from src.users.user_manager import UserManager

TEST_URL = os.environ.get("PVSOLAR_TEST_DB_URL", "").strip()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def db_url(tmp_path) -> str:
    """URL de banco do teste (PostgreSQL via env ou SQLite temporário)."""
    if TEST_URL:
        return TEST_URL
    return f"sqlite+aiosqlite:///{tmp_path.as_posix()}/pvsolar_test.db"


def make_config(url: str) -> DatabaseConfig:
    return DatabaseConfig(enabled=True, url=url, create_tables=True)


async def reset_schema(url: str) -> None:
    """Dropa as tabelas (isolamento entre testes em banco persistente)."""
    engine = create_engine(DatabaseConfig(enabled=True, url=url))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def start_service(url: str) -> PersistenceService:
    service = PersistenceService(make_config(url))
    await service.startup()
    return service


def auth_config(url: str) -> AuthConfig:
    return AuthConfig(database=make_config(url))


# ---------------------------------------------------------------------------
# Ciclo de vida
# ---------------------------------------------------------------------------

class TestStartup:
    async def test_disabled_is_noop(self):
        service = PersistenceService(DatabaseConfig(enabled=False, url=""))
        await service.startup()
        assert service.enabled is False
        assert service.started is False
        assert await service.ping() is False
        # gravações são no-op silencioso
        um = UserManager()
        await service.save_user(um.create_user("u", "u@t.com", "p"))
        await service.delete_user("qualquer")

    async def test_startup_creates_tables(self, tmp_path):
        url = db_url(tmp_path)
        service = await start_service(url)
        assert service.started is True
        assert await service.ping() is True
        await service.dispose()
        assert service.started is False

    async def test_hydrate_without_startup_raises(self):
        service = PersistenceService(make_config("sqlite+aiosqlite://"))
        with pytest.raises(RuntimeError, match="startup"):
            await service.hydrate(UserManager(), TenantManager(), RBACEngine())

    def test_safe_url_masks_password(self):
        url = "postgresql+asyncpg://postgres:senha_secreta@localhost:5432/pvsolar_auth"
        masked = _safe_url(url)
        assert "senha_secreta" not in masked
        assert "postgres:***@localhost:5432" in masked
        assert _safe_url("sqlite+aiosqlite:///tmp/x.db") == "sqlite+aiosqlite:///tmp/x.db"


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------

class TestUserPersistence:
    async def test_roundtrip_preserves_all_fields(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        um = UserManager()
        user = um.create_user(
            "carlos", "carlos@t.com", "SenhaForte1",
            full_name="Carlos Silva", role=UserRole.OPERATOR, tenant_id="t1",
        )
        um.change_password(user.id, "NovaSenha123")
        user = um.get_user(user.id)
        user.login_attempts = 3
        user.last_login = datetime.now(UTC)
        user.locked_until = datetime.now(UTC) + timedelta(minutes=10)
        await service.save_user(user)

        # novo "processo"
        um2, tm2, rb2 = UserManager(), TenantManager(), RBACEngine()
        stats = await service.hydrate(um2, tm2, rb2)

        got = um2.get_user(user.id)
        assert got is not None
        # senha preservada como hash (não é re-hasheada na hidratação)
        assert got.hashed_password == user.hashed_password
        assert got.username == "carlos"
        assert got.email == "carlos@t.com"
        assert got.full_name == "Carlos Silva"
        assert got.role == UserRole.OPERATOR
        assert got.status == UserStatus.ACTIVE
        assert got.tenant_id == "t1"
        assert got.login_attempts == 3
        assert got.last_login is not None and got.last_login.tzinfo is not None
        assert got.locked_until is not None and got.locked_until.tzinfo is not None
        # índices reconstruídos
        assert um2.username_index["carlos"] == user.id
        assert um2.email_index["carlos@t.com"] == user.id
        assert stats["users"] == 1

        # a senha nova funciona no novo processo
        assert um2.authenticate("carlos", "NovaSenha123") is not None
        await service.dispose()

    async def test_save_updates_existing_row(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        um = UserManager()
        user = um.create_user("ana", "ana@t.com", "senha1")
        await service.save_user(user)

        um.update_user(user.id, full_name="Ana Souza", role=UserRole.ADMIN)
        await service.save_user(um.get_user(user.id))

        um2 = UserManager()
        await service.hydrate(um2, TenantManager(), RBACEngine())
        got = um2.get_user(user.id)
        assert got.full_name == "Ana Souza"
        assert got.role == UserRole.ADMIN
        assert len(um2.users) == 1  # sem duplicatas
        await service.dispose()

    async def test_delete_removes_user_and_api_keys(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        um = UserManager()
        user = um.create_user("bruno", "bruno@t.com", "senha1")
        api_key = um.create_api_key(user.id, "integracao")
        await service.save_user(um.get_user(user.id))
        await service.save_api_key(api_key)

        um2 = UserManager()
        stats = await service.hydrate(um2, TenantManager(), RBACEngine())
        assert stats == {"users": 1, "api_keys": 1, "tenants": 0, "roles": 0}
        assert um2.api_keys[api_key.id].key == api_key.key
        assert um2.get_user(user.id).api_keys == [api_key.id]

        await service.delete_user(user.id)

        um3 = UserManager()
        stats = await service.hydrate(um3, TenantManager(), RBACEngine())
        assert stats["users"] == 0
        assert stats["api_keys"] == 0
        assert um3.get_user_by_username("bruno") is None
        assert api_key.id not in um3.api_keys
        await service.dispose()

    async def test_lockout_state_survives(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        um = UserManager()
        um.create_user("rita", "rita@t.com", "senha_correta")
        for _ in range(5):
            um.authenticate("rita", "errada")
        locked = um.get_user_by_username("rita")
        assert locked.status == UserStatus.LOCKED
        await service.save_user(locked)

        um2 = UserManager()
        await service.hydrate(um2, TenantManager(), RBACEngine())
        got = um2.get_user_by_username("rita")
        assert got.status == UserStatus.LOCKED
        assert got.login_attempts == 5
        assert got.locked_until is not None
        assert got.locked_until > datetime.now(UTC)
        # senha correta continua bloqueada após o reinício
        assert um2.authenticate("rita", "senha_correta") is None
        await service.dispose()


# ---------------------------------------------------------------------------
# Tenants e roles
# ---------------------------------------------------------------------------

class TestTenantAndRolePersistence:
    async def test_tenant_roundtrip(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        tm = TenantManager()
        tenant = tm.create_tenant(
            name="Usina Norte", slug="usina-norte",
            max_users=42, max_api_keys=7, features=["dashboard", "alerts"],
        )
        tm.update_tenant(tenant.id, status=TenantStatus.SUSPENDED)
        await service.save_tenant(tm.get_tenant(tenant.id))

        um, tm2, rb2 = UserManager(), TenantManager(), RBACEngine()
        stats = await service.hydrate(um, tm2, rb2)

        got = tm2.get_tenant(tenant.id)
        assert got is not None
        assert got.name == "Usina Norte"
        assert got.slug == "usina-norte"
        assert got.status == TenantStatus.SUSPENDED
        assert got.max_users == 42
        assert got.max_api_keys == 7
        assert got.features == ["dashboard", "alerts"]
        assert tm2.slug_index["usina-norte"] == tenant.id
        assert stats["tenants"] == 1
        await service.dispose()

    async def test_hydrate_keeps_default_roles_when_db_empty(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        rb = RBACEngine()
        stats = await service.hydrate(UserManager(), TenantManager(), rb)
        assert stats["roles"] == 0
        assert len(rb.roles) == 5  # padrões criados no construtor permanecem
        await service.dispose()

    async def test_db_is_authoritative_for_roles(self, tmp_path):
        url = db_url(tmp_path)
        await reset_schema(url)
        service = await start_service(url)

        # estado customizado: remove uma role padrão e cria uma própria
        rb = RBACEngine()
        victim = rb.get_role_by_name("api")
        rb.delete_role(victim.id)
        rb.create_role(name="engenheiro", description="Engenharia", permissions=[Permission.READ])
        await service.save_roles(rb)

        # novo processo: construtor reinicia com as 5 defaults
        rb2 = RBACEngine()
        assert rb2.get_role_by_name("api") is not None
        await service.hydrate(UserManager(), TenantManager(), rb2)

        assert rb2.get_role_by_name("api") is None  # banco manda
        assert rb2.get_role_by_name("engenheiro") is not None
        assert {r.name for r in rb2.roles.values()} == {
            "super_admin", "admin", "operator", "viewer", "engenheiro",
        }
        assert rb2.check_permission("engenheiro", Permission.READ) is True
        await service.dispose()


# ---------------------------------------------------------------------------
# Fim a fim (API + lifespan + reinício simulado)
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_seed_and_users_survive_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(auth_config(url))) as c1:
            resp = c1.post(
                "/api/users",
                json={
                    "username": "carlos",
                    "email": "carlos@t.com",
                    "password": "SenhaForte1",
                    "full_name": "Carlos",
                    "role": "operator",
                },
            )
            assert resp.status_code == 200
            user_id = resp.json()["id"]
            assert len(c1.get("/api/users").json()) == 2  # admin (seed) + carlos

        # "reinício": nova aplicação apontando para o mesmo banco
        with TestClient(create_app(auth_config(url))) as c2:
            users = c2.get("/api/users").json()
            assert len(users) == 2
            assert [u["username"] for u in users].count("admin") == 1  # seed não duplica
            assert any(u["id"] == user_id for u in users)
            # login do usuário criado antes do reinício
            resp = c2.post(
                "/api/auth/login",
                json={"username": "carlos", "password": "SenhaForte1"},
            )
            assert resp.status_code == 200

    def test_failed_logins_survive_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(auth_config(url))) as c1:
            for _ in range(5):
                resp = c1.post(
                    "/api/auth/login",
                    json={"username": "admin", "password": "senha_errada"},
                )
                assert resp.status_code == 401

        with TestClient(create_app(auth_config(url))) as c2:
            # conta segue bloqueada após o reinício (janela de lockout persistida)
            resp = c2.post(
                "/api/auth/login",
                json={"username": "admin", "password": "admin123"},
            )
            assert resp.status_code == 401

    def test_tenant_created_via_api_survives_restart(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(auth_config(url))) as c1:
            resp = c1.post(
                "/api/tenants",
                json={"name": "Usina Sul", "slug": "usina-sul", "features": ["reports"]},
            )
            assert resp.status_code == 200
            tenant_id = resp.json()["id"]
            # suspende — a mudança também precisa persistir
            assert c1.post(f"/api/tenants/{tenant_id}/suspend").status_code == 200

        with TestClient(create_app(auth_config(url))) as c2:
            tenants = c2.get("/api/tenants").json()
            assert len(tenants) == 2  # default (seed) + usina-sul
            got = c2.get(f"/api/tenants/{tenant_id}").json()
            assert got["status"] == "suspended"
            assert got["features"] == ["reports"]

    def test_health_and_statistics_report_database(self, tmp_path):
        url = db_url(tmp_path)
        if TEST_URL:
            asyncio.run(reset_schema(url))

        with TestClient(create_app(auth_config(url))) as client:
            health = client.get("/health").json()
            assert health["database"] == "connected"
            stats = client.get("/api/statistics").json()["database"]
            assert stats == {"enabled": True, "connected": True}

    def test_disabled_database_reports_disabled(self):
        with TestClient(create_app(AuthConfig())) as client:
            health = client.get("/health").json()
            assert health["database"] == "disabled"
            stats = client.get("/api/statistics").json()["database"]
            assert stats == {"enabled": False, "connected": False}
