"""API REST do pvSolar Auth."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.auth.auth_engine import AuthEngine
from src.core.config import AuthConfig, Permission, UserRole, load_config
from src.db.service import PersistenceService
from src.rbac.rbac_engine import RBACEngine
from src.tenants.tenant_manager import Tenant, TenantManager
from src.users.user_manager import User, UserManager

logger = structlog.get_logger()


def run_seed(
    config: AuthConfig,
    user_manager: UserManager,
    tenant_manager: TenantManager,
) -> tuple[Tenant | None, User | None]:
    """Cria o tenant/usuário inicial se não existir nenhum usuário.

    Retorna os objetos criados (``None`` quando o seed não se aplica),
    permitindo que o chamador os persista.
    """
    if not config.seed.enabled:
        return None, None
    if user_manager.get_user_by_username(config.seed.username) is not None:
        return None, None
    if user_manager.users:
        return None, None

    tenant: Tenant | None = None
    if not tenant_manager.tenants:
        tenant = tenant_manager.create_tenant(
            name="pvSolar Default",
            slug="default",
            max_users=config.tenant.max_users,
            max_api_keys=config.tenant.max_api_keys,
            features=config.tenant.features,
        )

    user = user_manager.create_user(
        username=config.seed.username,
        email=config.seed.email,
        password=config.seed.password,
        full_name=config.seed.full_name,
        role=config.seed.role,
        tenant_id=config.seed.tenant_id,
    )
    logger.info("seed.created", username=user.username)
    return tenant, user


def create_app(config: AuthConfig | None = None) -> FastAPI:
    """Cria a aplicação FastAPI."""
    if config is None:
        config = load_config()

    user_manager = UserManager(
        login_lockout_minutes=config.rate_limit.login_lockout_minutes
    )
    auth_engine = AuthEngine(config.jwt)
    rbac_engine = RBACEngine()
    tenant_manager = TenantManager()

    # Camada de persistência: no-op quando database.enabled=false, de modo
    # que os endpoints podem chamá-la incondicionalmente.
    persistence = PersistenceService(config.database)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if persistence.enabled:
            # 1) schema + estado do banco para a memória
            await persistence.startup()
            if config.database.hydrate_on_startup:
                await persistence.hydrate(user_manager, tenant_manager, rbac_engine)
            # 2) seed idempotente (só cria se o banco estiver vazio)
            tenant, user = run_seed(config, user_manager, tenant_manager)
            if tenant is not None:
                await persistence.save_tenant(tenant)
            if user is not None:
                await persistence.save_user(user)
            # 3) roles padrão do RBAC (upsert — no-op se já existem)
            await persistence.save_roles(rbac_engine)

        yield

        if persistence.enabled:
            await persistence.dispose()

    app = FastAPI(
        title=config.api.title,
        version="1.0.0",
        description="pvSolar Auth - Authentication & Authorization System",
        lifespan=lifespan,
    )

    # CORS: permite chamadas do pvSolar Web (localhost:3000) e demais frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Quando a persistência está desativada o seed roda agora (compatível com
    # testes que não disparam o lifespan do FastAPI).
    if not persistence.enabled:
        run_seed(config, user_manager, tenant_manager)

    @app.get("/health")
    async def health():
        db_state = "disabled"
        if persistence.enabled:
            db_state = "connected" if await persistence.ping() else "unavailable"
        return {"status": "ok", "service": "pvsolar-auth", "database": db_state}

    # --- Users ---
    @app.post("/api/users")
    async def create_user(data: dict):
        try:
            role = UserRole(data.get("role", "viewer"))
            user = user_manager.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"],
                full_name=data.get("full_name", ""),
                role=role,
                tenant_id=data.get("tenant_id", ""),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        # Write-through: se o banco falhar, desfaz a criação em memória para
        # não haver divergência entre o cache e a fonte de verdade.
        try:
            await persistence.save_user(user)
        except Exception as exc:
            user_manager.delete_user(user.id)
            logger.error("user.persist_failed", user_id=user.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar usuário no banco") from exc
        return user.to_dict()

    @app.get("/api/users")
    async def list_users():
        return [u.to_dict() for u in user_manager.users.values()]

    @app.get("/api/users/{user_id}")
    async def get_user(user_id: str):
        user = user_manager.get_user(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return user.to_dict()

    @app.put("/api/users/{user_id}")
    async def update_user(user_id: str, data: dict):
        if not user_manager.update_user(user_id, **data):
            raise HTTPException(status_code=404, detail="User not found")
        user = user_manager.get_user(user_id)
        if user is not None:
            try:
                await persistence.save_user(user)
            except Exception as exc:
                logger.error("user.persist_failed", user_id=user_id, error=str(exc))
                raise HTTPException(status_code=500, detail="Falha ao gravar usuário no banco") from exc
        return {"status": "updated"}

    @app.delete("/api/users/{user_id}")
    async def delete_user(user_id: str):
        if user_manager.get_user(user_id) is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Banco primeiro: se falhar, a memória permanece intacta.
        try:
            await persistence.delete_user(user_id)
        except Exception as exc:
            logger.error("user.persist_failed", user_id=user_id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao remover usuário do banco") from exc
        user_manager.delete_user(user_id)
        return {"status": "deleted"}

    # --- Auth ---
    @app.post("/api/auth/login")
    async def login(data: dict):
        user = user_manager.authenticate(data["username"], data["password"])
        if user is None:
            # Persiste tentativas/lockout (a proteção contra brute force
            # sobrevive a reinícios do serviço).
            failed = user_manager.get_user_by_username(data.get("username", ""))
            if failed is not None:
                await persistence.save_user(failed)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        try:
            await persistence.save_user(user)
        except Exception as exc:
            logger.error("user.persist_failed", user_id=user.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar usuário no banco") from exc

        permissions = [p.value for p in rbac_engine.get_role_permissions(user.role.value)]
        tokens = auth_engine.create_token_pair(
            user_id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            tenant_id=user.tenant_id,
            permissions=permissions,
        )
        return tokens.to_dict()

    @app.post("/api/auth/refresh")
    async def refresh_token(data: dict):
        tokens = auth_engine.refresh_access_token(data["refresh_token"])
        if tokens is None:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return tokens.to_dict()

    @app.post("/api/auth/logout")
    async def logout(data: dict):
        auth_engine.revoke_token(data.get("token", ""))
        return {"status": "logged_out"}

    @app.get("/api/auth/validate")
    async def validate_token(data: dict):
        claims = auth_engine.get_token_claims(data.get("token", ""))
        if claims is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return claims

    # --- API Keys ---
    @app.post("/api/users/{user_id}/api-keys")
    async def create_api_key(user_id: str, data: dict):
        api_key = user_manager.create_api_key(user_id, data.get("name", ""))
        if api_key is None:
            raise HTTPException(status_code=404, detail="User not found")
        try:
            await persistence.save_api_key(api_key)
        except Exception as exc:
            logger.error("apikey.persist_failed", key_id=api_key.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar chave de API no banco") from exc
        return {"key": api_key.key, "id": api_key.id}

    @app.post("/api/auth/validate-api-key")
    async def validate_api_key(data: dict):
        api_key = user_manager.validate_api_key(data.get("key", ""))
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {"valid": True, "user_id": api_key.user_id}

    # --- Roles ---
    @app.post("/api/roles")
    async def create_role(data: dict):
        permissions = [Permission(p) for p in data.get("permissions", [])]
        role = rbac_engine.create_role(
            name=data["name"],
            description=data.get("description", ""),
            permissions=permissions,
        )
        try:
            await persistence.save_role(role)
        except Exception as exc:
            rbac_engine.delete_role(role.id)
            logger.error("role.persist_failed", role_id=role.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar role no banco") from exc
        return role.to_dict()

    @app.get("/api/roles")
    async def list_roles():
        return [r.to_dict() for r in rbac_engine.roles.values()]

    @app.get("/api/roles/{role_name}/permissions")
    async def get_role_permissions(role_name: str):
        permissions = rbac_engine.get_role_permissions(role_name)
        return {"role": role_name, "permissions": [p.value for p in permissions]}

    @app.post("/api/roles/{role_name}/check")
    async def check_permission(role_name: str, data: dict):
        permission = Permission(data["permission"])
        allowed = rbac_engine.check_permission(role_name, permission)
        return {"allowed": allowed}

    # --- Tenants ---
    @app.post("/api/tenants")
    async def create_tenant(data: dict):
        try:
            tenant = tenant_manager.create_tenant(
                name=data["name"],
                slug=data["slug"],
                max_users=data.get("max_users", 100),
                max_api_keys=data.get("max_api_keys", 10),
                features=data.get("features", []),
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        try:
            await persistence.save_tenant(tenant)
        except Exception as exc:
            tenant_manager.delete_tenant(tenant.id)
            logger.error("tenant.persist_failed", tenant_id=tenant.id, error=str(exc))
            raise HTTPException(status_code=500, detail="Falha ao gravar tenant no banco") from exc
        return tenant.to_dict()

    @app.get("/api/tenants")
    async def list_tenants():
        return [t.to_dict() for t in tenant_manager.tenants.values()]

    @app.get("/api/tenants/{tenant_id}")
    async def get_tenant(tenant_id: str):
        tenant = tenant_manager.get_tenant(tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant.to_dict()

    @app.post("/api/tenants/{tenant_id}/suspend")
    async def suspend_tenant(tenant_id: str):
        if not tenant_manager.suspend_tenant(tenant_id):
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant = tenant_manager.get_tenant(tenant_id)
        if tenant is not None:
            try:
                await persistence.save_tenant(tenant)
            except Exception as exc:
                logger.error("tenant.persist_failed", tenant_id=tenant_id, error=str(exc))
                raise HTTPException(status_code=500, detail="Falha ao gravar tenant no banco") from exc
        return {"status": "suspended"}

    @app.post("/api/tenants/{tenant_id}/activate")
    async def activate_tenant(tenant_id: str):
        if not tenant_manager.activate_tenant(tenant_id):
            raise HTTPException(status_code=404, detail="Tenant not found")
        tenant = tenant_manager.get_tenant(tenant_id)
        if tenant is not None:
            try:
                await persistence.save_tenant(tenant)
            except Exception as exc:
                logger.error("tenant.persist_failed", tenant_id=tenant_id, error=str(exc))
                raise HTTPException(status_code=500, detail="Falha ao gravar tenant no banco") from exc
        return {"status": "activated"}

    # --- Statistics ---
    @app.get("/api/statistics")
    async def statistics():
        return {
            "users": user_manager.get_statistics(),
            "auth": auth_engine.get_statistics(),
            "rbac": rbac_engine.get_statistics(),
            "tenants": tenant_manager.get_statistics(),
            "database": {
                "enabled": persistence.enabled,
                "connected": await persistence.ping(),
            },
        }

    return app


# Instância padrão para uvicorn src.api.app:app
app = create_app()
