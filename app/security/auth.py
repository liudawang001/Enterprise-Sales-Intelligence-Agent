from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, Request

from app.security.principal import Principal, Role
from app.settings.production import AuthMode, Settings


class JWTAuthProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._jwks_client = jwt.PyJWKClient(settings.auth_jwks_url) if settings.auth_jwks_url else None

    def authenticate(self, token: str) -> Principal:
        if not self._jwks_client:
            raise ValueError("AUTH_JWKS_NOT_CONFIGURED")
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        claims: dict[str, Any] = jwt.decode(
            token,
            signing_key.key,
            algorithms=self.settings.auth.algorithms,
            audience=self.settings.auth_audience,
            issuer=self.settings.auth_issuer,
            options={"require": ["exp", "sub"]},
        )
        workspace_id = claims.get("workspace_id") or claims.get("tenant_id")
        if not workspace_id:
            raise ValueError("JWT_WORKSPACE_REQUIRED")
        roles = {Role(value.upper()) for value in claims.get("roles", [])}
        return Principal(user_id=str(claims["sub"]), workspace_id=str(workspace_id), roles=roles)


def dev_principal() -> Principal:
    return Principal(user_id="local-user", workspace_id="local", roles={Role.ADMIN, Role.ANALYST, Role.VIEWER})


def principal_from_request(request: Request) -> Principal:
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise HTTPException(401, "UNAUTHENTICATED")
    return principal


def require_roles(principal: Principal, *roles: Role) -> None:
    if not principal.has_any_role(*roles):
        raise HTTPException(403, "FORBIDDEN")


def authenticate_request(request: Request, settings: Settings, provider: JWTAuthProvider | None) -> Principal:
    if settings.auth_mode == AuthMode.DISABLED:
        return dev_principal()
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "UNAUTHENTICATED")
    try:
        assert provider is not None
        return provider.authenticate(token)
    except Exception as exc:
        raise HTTPException(401, "INVALID_TOKEN") from exc
