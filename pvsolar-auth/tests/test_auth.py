"""Testes do auth_engine do pvSolar Auth."""

import pytest

from src.core.config import JWTConfig, UserRole
from src.auth.auth_engine import AuthEngine, TokenPair, TokenPayload


class TestAuthEngine:
    def test_create_engine(self):
        e = AuthEngine()
        assert e.config.algorithm == "HS256"

    def test_create_access_token(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        assert len(token) > 50

    def test_create_refresh_token(self):
        e = AuthEngine()
        token = e.create_refresh_token("user1")
        assert len(token) > 50

    def test_create_token_pair(self):
        e = AuthEngine()
        pair = e.create_token_pair("user1", "admin", "a@test.com", UserRole.ADMIN)
        assert pair.access_token != ""
        assert pair.refresh_token != ""
        assert pair.expires_in > 0

    def test_decode_token(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        payload = e.decode_token(token, verify_audience=False)
        assert payload is not None
        assert payload.sub == "user1"
        assert payload.username == "admin"
        assert payload.role == "admin"

    def test_decode_invalid_token(self):
        e = AuthEngine()
        payload = e.decode_token("invalid.token.here")
        assert payload is None

    def test_revoke_token(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        assert e.revoke_token(token) is True
        assert e.decode_token(token) is None

    def test_is_token_valid(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        assert e.is_token_valid(token) is True

    def test_is_token_valid_revoked(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        e.revoke_token(token)
        assert e.is_token_valid(token) is False

    def test_get_token_claims(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        claims = e.get_token_claims(token)
        assert claims is not None
        assert claims["sub"] == "user1"

    def test_create_session(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        session_id = e.create_session("user1", token)
        assert len(session_id) > 0

    def test_invalidate_session(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        session_id = e.create_session("user1", token)
        assert e.invalidate_session(session_id) is True
        assert e.invalidate_session("nonexistent") is False

    def test_get_user_sessions(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        e.create_session("user1", token)
        e.create_session("user1", token)
        sessions = e.get_user_sessions("user1")
        assert len(sessions) == 2

    def test_get_statistics(self):
        e = AuthEngine()
        stats = e.get_statistics()
        assert "revoked_tokens" in stats
        assert "active_sessions" in stats

    def test_clear(self):
        e = AuthEngine()
        token = e.create_access_token("user1", "admin", "a@test.com", UserRole.ADMIN)
        e.revoke_token(token)
        e.create_session("user1", token)
        count = e.clear()
        assert count == 2

    def test_refresh_access_token(self):
        e = AuthEngine()
        refresh = e.create_refresh_token("user1")
        pair = e.refresh_access_token(refresh)
        assert pair is not None
        assert pair.access_token != ""


class TestTokenPair:
    def test_to_dict(self):
        p = TokenPair(access_token="abc", refresh_token="def", expires_in=1800)
        d = p.to_dict()
        assert d["access_token"] == "abc"
        assert d["expires_in"] == 1800


class TestTokenPayload:
    def test_create_payload(self):
        p = TokenPayload(sub="user1", username="admin")
        assert p.sub == "user1"
        assert p.username == "admin"
