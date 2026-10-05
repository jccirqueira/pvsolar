"""Testes do rbac_engine do pvSolar Auth."""

import pytest

from src.core.config import Permission, UserRole
from src.rbac.rbac_engine import Policy, RBACEngine, Role


class TestRBACEngine:
    def test_create_engine(self):
        e = RBACEngine()
        assert len(e.roles) >= 5

    def test_default_roles_created(self):
        e = RBACEngine()
        assert e.get_role_by_name("super_admin") is not None
        assert e.get_role_by_name("admin") is not None
        assert e.get_role_by_name("operator") is not None
        assert e.get_role_by_name("viewer") is not None
        assert e.get_role_by_name("api") is not None

    def test_create_role(self):
        e = RBACEngine()
        r = e.create_role("custom", "Custom role", [Permission.READ])
        assert r.name == "custom"
        assert Permission.READ in r.permissions

    def test_get_role(self):
        e = RBACEngine()
        r = e.create_role("test", "Test", [Permission.READ])
        found = e.get_role(r.id)
        assert found is not None
        assert found.name == "test"

    def test_get_role_by_name(self):
        e = RBACEngine()
        found = e.get_role_by_name("admin")
        assert found is not None

    def test_update_role(self):
        e = RBACEngine()
        r = e.create_role("test", "Old")
        assert e.update_role(r.id, description="New") is True
        assert e.get_role(r.id).description == "New"

    def test_delete_role(self):
        e = RBACEngine()
        r = e.create_role("test", "Test")
        assert e.delete_role(r.id) is True
        assert e.get_role(r.id) is None

    def test_add_permission(self):
        e = RBACEngine()
        r = e.create_role("test", "Test")
        e.add_permission_to_role(r.id, Permission.READ)
        assert Permission.READ in e.get_role(r.id).permissions

    def test_remove_permission(self):
        e = RBACEngine()
        r = e.create_role("test", "Test", [Permission.READ])
        e.remove_permission_from_role(r.id, Permission.READ)
        assert Permission.READ not in e.get_role(r.id).permissions

    def test_check_permission_true(self):
        e = RBACEngine()
        assert e.check_permission("admin", Permission.READ) is True

    def test_check_permission_false(self):
        e = RBACEngine()
        assert e.check_permission("viewer", Permission.DELETE) is False

    def test_check_any_permission(self):
        e = RBACEngine()
        assert e.check_any_permission("viewer", [Permission.READ, Permission.DELETE]) is True

    def test_check_all_permissions(self):
        e = RBACEngine()
        assert e.check_all_permissions("viewer", [Permission.READ, Permission.DELETE]) is False

    def test_get_role_permissions(self):
        e = RBACEngine()
        perms = e.get_role_permissions("admin")
        assert Permission.READ in perms
        assert Permission.WRITE in perms

    def test_get_roles_with_permission(self):
        e = RBACEngine()
        roles = e.get_roles_with_permission(Permission.READ)
        assert len(roles) >= 4

    def test_create_policy(self):
        e = RBACEngine()
        p = e.create_policy("test_policy", "allow", ["solar/*"], ["read"])
        assert p.name == "test_policy"
        assert p.effect == "allow"

    def test_get_policy(self):
        e = RBACEngine()
        p = e.create_policy("test", "allow")
        found = e.get_policy(p.id)
        assert found is not None

    def test_delete_policy(self):
        e = RBACEngine()
        p = e.create_policy("test", "allow")
        assert e.delete_policy(p.id) is True
        assert e.get_policy(p.id) is None

    def test_get_statistics(self):
        e = RBACEngine()
        stats = e.get_statistics()
        assert stats["total_roles"] >= 5

    def test_clear(self):
        e = RBACEngine()
        e.create_role("custom", "Test")
        count = e.clear()
        assert count >= 1


class TestRole:
    def test_to_dict(self):
        r = Role(name="test", description="Test", permissions=[Permission.READ])
        d = r.to_dict()
        assert d["name"] == "test"
        assert "read" in d["permissions"]


class TestPolicy:
    def test_to_dict(self):
        p = Policy(name="test", effect="allow", resources=["solar/*"])
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["effect"] == "allow"
