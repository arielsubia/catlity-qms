"""Tests for Cognito JWT validation, role authorization and registration."""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.core import security
from app.core.config import settings
from app.core.security import CurrentUser, get_current_tenant_id, require_role
from app.models.tenant import Tenant

# Test tokens are signed with an ephemeral RSA keypair generated per test run
# (see the rsa_keypair fixture). No key material is stored in the repository.


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """Generate an RSA keypair and expose JWK + PEM for signing test tokens."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    public_jwk = jwk.construct(
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
        algorithm="RS256",
    ).to_dict()
    public_jwk["kid"] = "test-key-1"
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"

    return {"private_pem": private_pem, "public_jwk": public_jwk}


@pytest.fixture(autouse=True)
def configure_cognito(
    rsa_keypair: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point settings at a fake pool and preload the JWKS cache."""
    monkeypatch.setattr(settings, "cognito_user_pool_id", "us-east-1_test", raising=False)
    monkeypatch.setattr(
        settings, "cognito_app_client_id", "test-client-id", raising=False
    )
    monkeypatch.setattr(settings, "aws_region", "us-east-1", raising=False)

    # Preload the JWKS cache so no network call happens during verification.
    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


def make_token(
    rsa_keypair: dict[str, Any],
    *,
    tenant_id: str | None = "tenant-001",
    role: str | None = "auditor",
    groups: list[str] | None = None,
    audience: str = "test-client-id",
    issuer: str | None = None,
    expired: bool = False,
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-sub-123",
        "email": "user@example.com",
        "aud": audience,
        "iss": issuer or settings.cognito_issuer,
        "iat": now,
        "exp": now - 60 if expired else now + 3600,
    }
    if tenant_id is not None:
        claims["custom:tenant_id"] = tenant_id
    if role is not None:
        claims["custom:role"] = role
    if groups is not None:
        claims["cognito:groups"] = groups
    return jwt.encode(
        claims,
        rsa_keypair["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_keypair["public_jwk"]["kid"]},
    )


# --- Test app exposing the security dependencies ----------------------------


@pytest.fixture()
def secured_app() -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(tenant_id: str = Depends(get_current_tenant_id)) -> dict[str, str]:
        return {"tenant_id": tenant_id}

    @app.get("/auditor-only")
    def auditor_only(
        user: CurrentUser = Depends(require_role(["auditor", "admin"])),
    ) -> dict[str, str]:
        return {"role": user.role}

    return app


@pytest.fixture()
def secured_client(secured_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(secured_app) as c:
        yield c


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Token validation -------------------------------------------------------


def test_valid_token_grants_access(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, tenant_id="tenant-abc")
    resp = secured_client.get("/whoami", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == "tenant-abc"


def test_missing_token_is_rejected(secured_client: TestClient) -> None:
    resp = secured_client.get("/whoami")
    assert resp.status_code == 401


def test_malformed_token_is_rejected(secured_client: TestClient) -> None:
    resp = secured_client.get("/whoami", headers=_auth("not-a-jwt"))
    assert resp.status_code == 401


def test_expired_token_is_rejected(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, expired=True)
    resp = secured_client.get("/whoami", headers=_auth(token))
    assert resp.status_code == 401


def test_wrong_audience_is_rejected(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, audience="some-other-client")
    resp = secured_client.get("/whoami", headers=_auth(token))
    assert resp.status_code == 401


def test_wrong_issuer_is_rejected(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, issuer="https://evil.example.com/pool")
    resp = secured_client.get("/whoami", headers=_auth(token))
    assert resp.status_code == 401


def test_token_without_tenant_is_forbidden(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, tenant_id=None)
    resp = secured_client.get("/whoami", headers=_auth(token))
    assert resp.status_code == 403


# --- Role authorization -----------------------------------------------------


def test_role_authorized_via_custom_attribute(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, role="auditor")
    resp = secured_client.get("/auditor-only", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["role"] == "auditor"


def test_role_authorized_via_group(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, role=None, groups=["admin"])
    resp = secured_client.get("/auditor-only", headers=_auth(token))
    assert resp.status_code == 200


def test_role_forbidden_when_not_allowed(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token = make_token(rsa_keypair, role="auditee", groups=[])
    resp = secured_client.get("/auditor-only", headers=_auth(token))
    assert resp.status_code == 403


# --- Tenant isolation -------------------------------------------------------


def test_tenant_id_is_scoped_to_token(
    secured_client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    token_a = make_token(rsa_keypair, tenant_id="tenant-a")
    token_b = make_token(rsa_keypair, tenant_id="tenant-b")
    resp_a = secured_client.get("/whoami", headers=_auth(token_a))
    resp_b = secured_client.get("/whoami", headers=_auth(token_b))
    assert resp_a.json()["tenant_id"] == "tenant-a"
    assert resp_b.json()["tenant_id"] == "tenant-b"


# --- Registration endpoint --------------------------------------------------


def test_register_creates_user(
    client: TestClient, db, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = Tenant(name="AutoCorp", industry="automotive")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    monkeypatch.setattr(
        "app.api.v1.auth.cognito.register_user",
        lambda **kwargs: "cognito-sub-999",
    )

    payload = {
        "email": "newuser@example.com",
        "password": "SuperSecret123!",
        "full_name": "New User",
        "tenant_id": tenant.id,
        "role": "auditor",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "auditor"
    assert data["cognito_sub"] == "cognito-sub-999"


def test_register_rejects_invalid_role(client: TestClient, db) -> None:
    tenant = Tenant(name="AutoCorp", industry="automotive")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    payload = {
        "email": "u@example.com",
        "password": "SuperSecret123!",
        "full_name": "U",
        "tenant_id": tenant.id,
        "role": "superuser",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 422


def test_register_rejects_unknown_tenant(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.api.v1.auth.cognito.register_user",
        lambda **kwargs: "sub",
    )
    payload = {
        "email": "u@example.com",
        "password": "SuperSecret123!",
        "full_name": "U",
        "tenant_id": "does-not-exist",
        "role": "auditor",
    }
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 404
