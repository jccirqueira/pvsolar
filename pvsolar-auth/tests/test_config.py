"""Testes do módulo config do pvSolar Auth."""

from pathlib import Path

import pytest
from src.core import config as config_module
from src.core.config import (
    AuthConfig,
    JWTConfig,
    OAuthConfig,
    PasswordConfig,
    Permission,
    RateLimitConfig,
    RBACConfig,
    SessionConfig,
    TenantConfig,
    TenantStatus,
    UserRole,
    UserStatus,
    load_config,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TestUserRole:
    def test_super_admin(self):
        assert UserRole.SUPER_ADMIN == "super_admin"
    def test_admin(self):
        assert UserRole.ADMIN == "admin"
    def test_operator(self):
        assert UserRole.OPERATOR == "operator"
    def test_viewer(self):
        assert UserRole.VIEWER == "viewer"
    def test_api(self):
        assert UserRole.API == "api"


class TestPermission:
    def test_read(self):
        assert Permission.READ == "read"
    def test_write(self):
        assert Permission.WRITE == "write"
    def test_delete(self):
        assert Permission.DELETE == "delete"
    def test_admin(self):
        assert Permission.ADMIN == "admin"
    def test_manage_users(self):
        assert Permission.MANAGE_USERS == "manage_users"


class TestTenantStatus:
    def test_active(self):
        assert TenantStatus.ACTIVE == "active"
    def test_inactive(self):
        assert TenantStatus.INACTIVE == "inactive"
    def test_suspended(self):
        assert TenantStatus.SUSPENDED == "suspended"


class TestUserStatus:
    def test_active(self):
        assert UserStatus.ACTIVE == "active"
    def test_locked(self):
        assert UserStatus.LOCKED == "locked"


# ---------------------------------------------------------------------------
# Config Models
# ---------------------------------------------------------------------------

class TestJWTConfig:
    def test_defaults(self):
        c = JWTConfig()
        assert c.algorithm == "HS256"
        assert c.access_token_expire_minutes == 30
        assert c.refresh_token_expire_days == 7


class TestPasswordConfig:
    def test_defaults(self):
        c = PasswordConfig()
        assert c.min_length == 8
        assert c.require_uppercase is True
        assert c.max_age_days == 90


class TestRateLimitConfig:
    def test_defaults(self):
        c = RateLimitConfig()
        assert c.login_attempts == 5
        assert c.login_lockout_minutes == 15


class TestSessionConfig:
    def test_defaults(self):
        c = SessionConfig()
        assert c.max_sessions == 5
        assert c.session_timeout_minutes == 60


class TestOAuthConfig:
    def test_defaults(self):
        c = OAuthConfig()
        assert c.enabled is False


class TestRBACConfig:
    def test_defaults(self):
        c = RBACConfig()
        assert c.default_role == UserRole.VIEWER


class TestTenantConfig:
    def test_defaults(self):
        c = TenantConfig()
        assert c.max_users == 100
        assert c.max_api_keys == 10


class TestAuthConfig:
    def test_defaults(self):
        c = AuthConfig()
        assert c.company_name == "pvSolar Auth"
        assert c.debug is False
        assert c.api.port == 8007


# ---------------------------------------------------------------------------
# Load Config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_load_default(self, monkeypatch):
        # isola a descoberta automatica (config/auth.yaml pode existir)
        monkeypatch.delenv("PVSOLAR_CONFIG", raising=False)
        monkeypatch.setattr(config_module, "_default_config_path", lambda: None)
        c = load_config()
        assert c.company_name == "pvSolar Auth"

    def test_load_nonexistent(self):
        c = load_config("/nonexistent/path.yaml")
        assert c.company_name == "pvSolar Auth"

    def test_load_yaml(self, tmp_path):
        config_file = tmp_path / "test.yaml"
        config_file.write_text(
            "company_name: TestCo\ndebug: true\napi:\n  port: 9000\n"
        )
        c = load_config(config_file)
        assert c.company_name == "TestCo"
        assert c.debug is True
        assert c.api.port == 9000

    # ------------------------------------------------------------------
    # Descoberta automatica (PVSOLAR_CONFIG / config/auth.yaml)
    # ------------------------------------------------------------------

    def test_env_config_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "meu_auth.yaml"
        config_file.write_text("company_name: ViaEnv\ndebug: true\n")
        monkeypatch.setenv("PVSOLAR_CONFIG", str(config_file))
        c = load_config()
        assert c.company_name == "ViaEnv"
        assert c.debug is True

    def test_env_config_missing_falls_back_to_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PVSOLAR_CONFIG", str(tmp_path / "nao_existe.yaml"))
        monkeypatch.setattr(config_module, "_default_config_path", lambda: None)
        c = load_config()
        assert c.company_name == "pvSolar Auth"

    def test_env_vars_override_config_file(self, tmp_path, monkeypatch):
        config_file = tmp_path / "db.yaml"
        config_file.write_text('database:\n  enabled: false\n  url: ""\n')
        monkeypatch.setenv("PVSOLAR_CONFIG", str(config_file))
        monkeypatch.setenv(
            "PVSOLAR_DATABASE_URL",
            "postgresql+asyncpg://postgres:senha@localhost:5432/pvsolar_auth",
        )
        c = load_config()
        assert c.database.enabled is True
        assert c.database.url.endswith("/pvsolar_auth")
