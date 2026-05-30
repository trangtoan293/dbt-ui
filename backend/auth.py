"""Keycloak JWT authentication."""
import os
from dataclasses import dataclass, field
from typing import List

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Request, status

ISSUER = os.environ.get("KEYCLOAK_ISSUER", "")
JWKS_URI = os.environ.get("KEYCLOAK_JWKS_URI", "")
AUDIENCE = os.environ.get("KEYCLOAK_AUDIENCE", "account")

_jwks_client: PyJWKClient | None = None


@dataclass(frozen=True)
class CurrentUser:
    sub: str
    email: str
    roles: List[str] = field(default_factory=list)


def _get_signing_key(token: str):
    """Fetch the RSA signing key for this token from Keycloak JWKS (cached)."""
    global _jwks_client
    if _jwks_client is None:
        if not JWKS_URI:
            raise HTTPException(status_code=500, detail="JWKS URI not configured")
        _jwks_client = PyJWKClient(JWKS_URI)
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_token(token: str) -> CurrentUser:
    """Validate a Keycloak access token and return the CurrentUser."""
    try:
        key = _get_signing_key(token)
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={"require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return CurrentUser(
        sub=claims["sub"],
        email=claims.get("email", ""),
        roles=claims.get("realm_access", {}).get("roles", []),
    )


def get_current_user(request: Request) -> CurrentUser:
    """FastAPI dependency: extract and validate the Bearer token."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(header[len("Bearer "):])


def require_role(role: str):
    """Dependency factory: require the user to have a given realm role."""
    def _guard(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if role not in user.roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {role}")
        return user
    return _guard
