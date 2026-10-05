"""Engine de autenticação JWT."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

import jwt
import structlog

from src.core.config import JWTConfig, UserStatus, UserRole

logger = structlog.get_logger()


@dataclass
class TokenPair:
    """Par de tokens."""
    access_token: str = ""
    refresh_token: str = ""
    token_type: str = "Bearer"
    expires_in: int = 0

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
        }


@dataclass
class TokenPayload:
    """Payload do token."""
    sub: str = ""
    username: str = ""
    email: str = ""
    role: str = ""
    tenant_id: str = ""
    permissions: list[str] = field(default_factory=list)
    exp: datetime | None = None
    iat: datetime | None = None
    jti: str = ""
    token_type: str = "access"


class AuthEngine:
    """Engine de autenticação JWT."""

    def __init__(self, config: JWTConfig | None = None) -> None:
        self.config = config or JWTConfig()
        self.revoked_tokens: set[str] = set()
        self.active_sessions: dict[str, dict] = {}

    def create_access_token(
        self,
        user_id: str,
        username: str,
        email: str,
        role: UserRole,
        tenant_id: str = "",
        permissions: list[str] | None = None,
    ) -> str:
        """Cria access token."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=self.config.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "username": username,
            "email": email,
            "role": role.value,
            "tenant_id": tenant_id,
            "permissions": permissions or [],
            "exp": exp,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "access",
            "iss": self.config.issuer,
            "aud": self.config.audience,
        }

        token = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        logger.info("token.access_created", user_id=user_id, expires=exp.isoformat())
        return token

    def create_refresh_token(self, user_id: str) -> str:
        """Cria refresh token."""
        now = datetime.now(timezone.utc)
        exp = now + timedelta(days=self.config.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "exp": exp,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "refresh",
            "iss": self.config.issuer,
        }

        token = jwt.encode(
            payload,
            self.config.secret_key,
            algorithm=self.config.algorithm,
        )
        logger.info("token.refresh_created", user_id=user_id)
        return token

    def create_token_pair(
        self,
        user_id: str,
        username: str,
        email: str,
        role: UserRole,
        tenant_id: str = "",
        permissions: list[str] | None = None,
    ) -> TokenPair:
        """Cria par de tokens."""
        access = self.create_access_token(
            user_id, username, email, role, tenant_id, permissions
        )
        refresh = self.create_refresh_token(user_id)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.config.access_token_expire_minutes * 60,
        )

    def decode_token(self, token: str, verify_audience: bool = True) -> TokenPayload | None:
        """Decodifica um token."""
        if token in self.revoked_tokens:
            logger.warning("token.revoked")
            return None

        try:
            options = {"verify_aud": verify_audience}
            payload = jwt.decode(
                token,
                self.config.secret_key,
                algorithms=[self.config.algorithm],
                issuer=self.config.issuer,
                options=options,
            )
            return TokenPayload(
                sub=payload.get("sub", ""),
                username=payload.get("username", ""),
                email=payload.get("email", ""),
                role=payload.get("role", ""),
                tenant_id=payload.get("tenant_id", ""),
                permissions=payload.get("permissions", []),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload.get("jti", ""),
                token_type=payload.get("token_type", "access"),
            )
        except jwt.ExpiredSignatureError:
            logger.warning("token.expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning("token.invalid", error=str(e))
            return None

    def refresh_access_token(self, refresh_token: str) -> TokenPair | None:
        """Renova access token usando refresh token."""
        payload = self.decode_token(refresh_token, verify_audience=False)
        if payload is None or payload.token_type != "refresh":
            return None

        self.revoke_token(refresh_token)

        access = self.create_access_token(
            user_id=payload.sub,
            username="",
            email="",
            role=UserRole.VIEWER,
        )
        refresh = self.create_refresh_token(payload.sub)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.config.access_token_expire_minutes * 60,
        )

    def revoke_token(self, token: str) -> bool:
        """Revoga um token."""
        self.revoked_tokens.add(token)
        logger.info("token.revoked")
        return True

    def is_token_valid(self, token: str) -> bool:
        """Verifica se um token é válido."""
        payload = self.decode_token(token, verify_audience=False)
        return payload is not None

    def get_token_claims(self, token: str) -> dict | None:
        """Retorna claims do token."""
        payload = self.decode_token(token, verify_audience=False)
        if payload is None:
            return None
        return {
            "sub": payload.sub,
            "username": payload.username,
            "email": payload.email,
            "role": payload.role,
            "tenant_id": payload.tenant_id,
            "permissions": payload.permissions,
        }

    def create_session(self, user_id: str, token: str) -> str:
        """Cria uma sessão."""
        session_id = str(uuid.uuid4())
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "token": token,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return session_id

    def invalidate_session(self, session_id: str) -> bool:
        """Invalida uma sessão."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            return True
        return False

    def get_user_sessions(self, user_id: str) -> list[dict]:
        """Retorna sessões do usuário."""
        return [
            s for s in self.active_sessions.values() if s["user_id"] == user_id
        ]

    def get_statistics(self) -> dict:
        """Retorna estatísticas."""
        return {
            "revoked_tokens": len(self.revoked_tokens),
            "active_sessions": len(self.active_sessions),
        }

    def clear(self) -> int:
        """Limpa tokens e sessões."""
        count = len(self.revoked_tokens) + len(self.active_sessions)
        self.revoked_tokens.clear()
        self.active_sessions.clear()
        return count
