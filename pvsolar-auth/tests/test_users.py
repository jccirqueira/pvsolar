"""Testes do user_manager do pvSolar Auth."""

import pytest
from src.core.config import UserRole, UserStatus
from src.users.user_manager import (
    APIKey,
    User,
    UserManager,
    hash_password,
    verify_password,
)


class TestPasswordHash:
    def test_hash_password(self):
        h = hash_password("test123")
        assert ":" in h
        assert len(h) > 32

    def test_verify_password(self):
        h = hash_password("test123")
        assert verify_password("test123", h) is True
        assert verify_password("wrong", h) is False

    def test_verify_invalid_hash(self):
        assert verify_password("test", "invalid") is False


class TestUser:
    def test_create_user(self):
        u = User(username="admin", email="admin@test.com")
        assert u.username == "admin"
        assert u.role == UserRole.VIEWER

    def test_to_dict(self):
        u = User(username="admin", email="admin@test.com")
        d = u.to_dict()
        assert d["username"] == "admin"
        assert "id" in d


class TestAPIKey:
    def test_create_key(self):
        k = APIKey(name="test")
        assert k.name == "test"
        assert k.is_active is True
        assert len(k.key) > 32

    def test_to_dict(self):
        k = APIKey(name="test")
        d = k.to_dict()
        assert d["name"] == "test"
        assert "..." in d["key"]


class TestUserManager:
    def test_create_manager(self):
        m = UserManager()
        assert len(m.users) == 0

    def test_create_user(self):
        m = UserManager()
        u = m.create_user("admin", "admin@test.com", "pass123")
        assert u.username == "admin"
        assert len(m.users) == 1

    def test_create_duplicate_username(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass")
        with pytest.raises(ValueError):
            m.create_user("admin", "b@test.com", "pass")

    def test_create_duplicate_email(self):
        m = UserManager()
        m.create_user("user1", "a@test.com", "pass")
        with pytest.raises(ValueError):
            m.create_user("user2", "a@test.com", "pass")

    def test_get_user(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        found = m.get_user(u.id)
        assert found is not None
        assert found.id == u.id

    def test_get_user_by_username(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass")
        found = m.get_user_by_username("admin")
        assert found is not None

    def test_get_user_by_email(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass")
        found = m.get_user_by_email("a@test.com")
        assert found is not None

    def test_update_user(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        assert m.update_user(u.id, full_name="Admin User") is True
        assert m.get_user(u.id).full_name == "Admin User"

    def test_delete_user(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        assert m.delete_user(u.id) is True
        assert len(m.users) == 0

    def test_authenticate_success(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass123")
        user = m.authenticate("admin", "pass123")
        assert user is not None
        assert user.last_login is not None

    def test_authenticate_wrong_password(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass123")
        user = m.authenticate("admin", "wrong")
        assert user is None

    def test_authenticate_nonexistent(self):
        m = UserManager()
        user = m.authenticate("admin", "pass")
        assert user is None

    def test_lockout_after_attempts(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass123")
        for _ in range(5):
            m.authenticate("admin", "wrong")
        user = m.get_user_by_username("admin")
        assert user.status == UserStatus.LOCKED

    def test_change_password(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "old")
        assert m.change_password(u.id, "new") is True
        assert m.authenticate("admin", "new") is not None

    def test_create_api_key(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        key = m.create_api_key(u.id, "test-key")
        assert key is not None
        assert key.name == "test-key"

    def test_validate_api_key(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        key = m.create_api_key(u.id, "test-key")
        found = m.validate_api_key(key.key)
        assert found is not None

    def test_revoke_api_key(self):
        m = UserManager()
        u = m.create_user("admin", "a@test.com", "pass")
        key = m.create_api_key(u.id, "test-key")
        assert m.revoke_api_key(key.id) is True
        assert m.validate_api_key(key.key) is None

    def test_get_users_by_role(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass", role=UserRole.ADMIN)
        m.create_user("viewer", "b@test.com", "pass", role=UserRole.VIEWER)
        admins = m.get_users_by_role(UserRole.ADMIN)
        assert len(admins) == 1

    def test_get_statistics(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass")
        stats = m.get_statistics()
        assert stats["total_users"] == 1

    def test_clear(self):
        m = UserManager()
        m.create_user("admin", "a@test.com", "pass")
        count = m.clear()
        assert count == 1
        assert len(m.users) == 0
