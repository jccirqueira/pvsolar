"""Testes do tenant_manager do pvSolar Auth."""

import pytest

from src.core.config import TenantStatus
from src.tenants.tenant_manager import Tenant, TenantManager


class TestTenantManager:
    def test_create_manager(self):
        m = TenantManager()
        assert len(m.tenants) == 0

    def test_create_tenant(self):
        m = TenantManager()
        t = m.create_tenant("Empresa A", "empresa-a")
        assert t.name == "Empresa A"
        assert t.slug == "empresa-a"
        assert len(m.tenants) == 1

    def test_create_duplicate_slug(self):
        m = TenantManager()
        m.create_tenant("A", "slug")
        with pytest.raises(ValueError):
            m.create_tenant("B", "slug")

    def test_get_tenant(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        found = m.get_tenant(t.id)
        assert found is not None
        assert found.id == t.id

    def test_get_tenant_by_slug(self):
        m = TenantManager()
        m.create_tenant("A", "a")
        found = m.get_tenant_by_slug("a")
        assert found is not None

    def test_update_tenant(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        assert m.update_tenant(t.id, name="B") is True
        assert m.get_tenant(t.id).name == "B"

    def test_delete_tenant(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        assert m.delete_tenant(t.id) is True
        assert len(m.tenants) == 0

    def test_suspend_tenant(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        assert m.suspend_tenant(t.id) is True
        assert m.get_tenant(t.id).status == TenantStatus.SUSPENDED

    def test_activate_tenant(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        m.suspend_tenant(t.id)
        assert m.activate_tenant(t.id) is True
        assert m.get_tenant(t.id).status == TenantStatus.ACTIVE

    def test_get_active_tenants(self):
        m = TenantManager()
        m.create_tenant("A", "a")
        m.create_tenant("B", "b")
        active = m.get_active_tenants()
        assert len(active) == 2

    def test_check_user_limit(self):
        m = TenantManager()
        t = m.create_tenant("A", "a", max_users=2)
        assert m.check_user_limit(t.id, 1) is True
        assert m.check_user_limit(t.id, 2) is False

    def test_add_feature(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        assert m.add_feature(t.id, "analytics") is True
        assert m.has_feature(t.id, "analytics") is True

    def test_remove_feature(self):
        m = TenantManager()
        t = m.create_tenant("A", "a", features=["analytics"])
        assert m.remove_feature(t.id, "analytics") is True
        assert m.has_feature(t.id, "analytics") is False

    def test_has_feature_false(self):
        m = TenantManager()
        t = m.create_tenant("A", "a")
        assert m.has_feature(t.id, "analytics") is False

    def test_get_statistics(self):
        m = TenantManager()
        m.create_tenant("A", "a")
        stats = m.get_statistics()
        assert stats["total_tenants"] == 1

    def test_clear(self):
        m = TenantManager()
        m.create_tenant("A", "a")
        count = m.clear()
        assert count == 1
        assert len(m.tenants) == 0


class TestTenant:
    def test_to_dict(self):
        t = Tenant(name="A", slug="a")
        d = t.to_dict()
        assert d["name"] == "A"
        assert d["slug"] == "a"
        assert d["status"] == "active"
