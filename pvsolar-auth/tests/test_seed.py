"""Testes do seed de usuário inicial do pvSolar Auth."""

from fastapi.testclient import TestClient
from src.api.app import create_app
from src.core.config import AuthConfig, SeedConfig, UserRole


class TestSeedConfig:
    def test_defaults(self):
        s = SeedConfig()
        assert s.enabled is True
        assert s.username == "admin"
        assert s.password == "admin123"
        assert s.role == UserRole.ADMIN
        assert s.tenant_id == "default"

    def test_in_auth_config(self):
        c = AuthConfig()
        assert c.seed.enabled is True
        assert c.seed.username == "admin"


class TestSeedStartup:
    def test_seed_creates_admin(self):
        app = create_app(AuthConfig())
        client = TestClient(app)
        resp = client.get("/api/users")
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"

    def test_seed_allows_login(self):
        app = create_app(AuthConfig())
        client = TestClient(app)
        resp = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert resp.status_code == 200
        tokens = resp.json()
        assert "access_token" in tokens

    def test_seed_creates_tenant(self):
        app = create_app(AuthConfig())
        client = TestClient(app)
        resp = client.get("/api/tenants")
        assert resp.status_code == 200
        tenants = resp.json()
        assert len(tenants) == 1
        assert tenants[0]["slug"] == "default"

    def test_seed_disabled(self):
        config = AuthConfig(seed=SeedConfig(enabled=False))
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/api/users")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_seed_custom_credentials(self):
        config = AuthConfig(
            seed=SeedConfig(
                username="operador",
                email="op@pvsolar.com",
                password="senha-teste-123",
                role=UserRole.OPERATOR,
            )
        )
        app = create_app(config)
        client = TestClient(app)
        resp = client.post(
            "/api/auth/login",
            json={"username": "operador", "password": "senha-teste-123"},
        )
        assert resp.status_code == 200

    def test_seed_idempotent(self):
        """Segundo create_app não duplica usuários (novo UserManager a cada app)."""
        app = create_app(AuthConfig())
        client = TestClient(app)
        users_before = client.get("/api/users").json()
        # nova criação do app gera nova instância — não duplica
        app2 = create_app(AuthConfig())
        client2 = TestClient(app2)
        users_after = client2.get("/api/users").json()
        assert len(users_before) == len(users_after) == 1
