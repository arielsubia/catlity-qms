"""Security utilities — Cognito JWT validation and tenant isolation.

This module validates JWTs issued by an Amazon Cognito User Pool. It fetches
the pool's JSON Web Key Set (JWKS), verifies the token signature, issuer and
audience, and exposes FastAPI dependencies to extract the authenticated
principal (``tenant_id`` and ``role``) and to enforce role-based access.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

from app.core.config import settings

# Cognito custom attributes are exposed as namespaced claims in the token.
CLAIM_TENANT_ID = "custom:tenant_id"
CLAIM_ROLE = "custom:role"
CLAIM_GROUPS = "cognito:groups"

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """Authenticated principal derived from a validated Cognito JWT."""

    sub: str
    email: str | None
    tenant_id: str
    role: str
    groups: tuple[str, ...]


class _JWKSCache:
    """In-memory cache for the Cognito JSON Web Key Set.

    The JWKS rarely rotates, so caching avoids a network round-trip on every
    request. Entries are refreshed after ``ttl_seconds``.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._keys: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0

    def _is_stale(self) -> bool:
        return not self._keys or (time.monotonic() - self._fetched_at) > self._ttl

    def get_key(self, kid: str) -> dict[str, Any] | None:
        if self._is_stale():
            self._refresh()
        key = self._keys.get(kid)
        if key is None and not self._is_stale():
            # Unknown kid with a fresh cache: force one refresh in case of
            # a recent key rotation.
            self._refresh()
            key = self._keys.get(kid)
        return key

    def _refresh(self) -> None:
        response = httpx.get(settings.cognito_jwks_url, timeout=5.0)
        response.raise_for_status()
        payload = response.json()
        self._keys = {key["kid"]: key for key in payload.get("keys", [])}
        self._fetched_at = time.monotonic()


_jwks_cache = _JWKSCache()


def _credentials_exception(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify_signature(token: str, key_data: dict[str, Any]) -> None:
    """Verify the token's RS256 signature against the given JWK."""
    public_key = jwk.construct(key_data)
    message, encoded_signature = token.rsplit(".", 1)
    signature = base64url_decode(encoded_signature.encode("utf-8"))
    if not public_key.verify(message.encode("utf-8"), signature):
        raise _credentials_exception("Invalid token signature")


def decode_token(token: str) -> dict[str, Any]:
    """Validate a Cognito JWT and return its claims.

    Raises an HTTP 401 error if the token is malformed, has an unknown signing
    key, fails signature verification, or does not match the expected issuer
    and audience.
    """
    if not settings.cognito_user_pool_id or not settings.cognito_app_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )

    try:
        headers = jwt.get_unverified_headers(token)
    except JWTError as exc:
        raise _credentials_exception("Malformed token") from exc

    kid = headers.get("kid")
    if not kid:
        raise _credentials_exception("Token missing key id")

    key_data = _jwks_cache.get_key(kid)
    if key_data is None:
        raise _credentials_exception("Unknown signing key")

    _verify_signature(token, key_data)

    try:
        claims = jwt.decode(
            token,
            key_data,
            algorithms=["RS256"],
            audience=settings.cognito_app_client_id,
            issuer=settings.cognito_issuer,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise _credentials_exception(f"Invalid token: {exc}") from exc

    return claims


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """FastAPI dependency that resolves the authenticated user from a JWT."""
    if credentials is None or not credentials.credentials:
        raise _credentials_exception("Missing bearer token")

    claims = decode_token(credentials.credentials)

    tenant_id = claims.get(CLAIM_TENANT_ID)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is missing tenant assignment",
        )

    groups = tuple(claims.get(CLAIM_GROUPS, []))
    # Prefer the explicit custom:role attribute; fall back to the first group.
    role = claims.get(CLAIM_ROLE) or (groups[0] if groups else "")
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token is missing a role assignment",
        )

    return CurrentUser(
        sub=claims.get("sub", ""),
        email=claims.get("email"),
        tenant_id=tenant_id,
        role=role,
        groups=groups,
    )


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser | None:
    """Resolve the caller when a bearer token is present.

    Public endpoints use this so anonymous requests stay anonymous. A token
    that is present but invalid still fails with 401.
    """
    if credentials is None or not credentials.credentials:
        return None
    return get_current_user(credentials)


def get_current_tenant_id(
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    """Extract the tenant_id of the authenticated user for isolation checks."""
    return current_user.tenant_id


def require_role(allowed_roles: list[str]) -> Callable[[CurrentUser], CurrentUser]:
    """Build a dependency that only allows users with one of ``allowed_roles``.

    The check matches against the user's ``role`` as well as their Cognito
    group memberships, so either mechanism grants access.

    Usage::

        @router.get("/reports", dependencies=[Depends(require_role(["auditor"]))])
    """
    allowed = set(allowed_roles)

    def _dependency(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        held_roles = {current_user.role, *current_user.groups}
        if allowed.isdisjoint(held_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return current_user

    return _dependency
