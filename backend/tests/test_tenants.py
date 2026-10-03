"""Tests for tenant endpoints scoped to the caller's JWT."""

from __future__ import annotations

import time
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk

from app.core import security
from app.core.config import settings
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign tenant-scoped tokens in this module."""
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
    public_jwk["kid"] = "test-key-tenants"
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

    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_tenant(client: TestClient, name: str, industry: str = "automotive") -> str:
    response = client.post(
        "/api/v1/tenants/",
        json={"name": name, "industry": industry},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_tenant(client: TestClient) -> None:
    payload = {
        "name": "AutoCorp",
        "industry": "automotive",
        "description": "IATF 16949 certified manufacturer",
    }
    response = client.post("/api/v1/tenants/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AutoCorp"
    assert data["industry"] == "automotive"
    assert data["is_active"] is True
    assert "id" in data


def test_list_tenants(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "Tenant A")
    token = make_token(rsa_keypair, tenant_id=tenant_id)
    response = client.get("/api/v1/tenants/", headers=_auth(token))
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == tenant_id
    assert data[0]["name"] == "Tenant A"


def test_get_tenant(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "GetMe")
    token = make_token(rsa_keypair, tenant_id=tenant_id)
    response = client.get(f"/api/v1/tenants/{tenant_id}", headers=_auth(token))
    assert response.status_code == 200
    assert response.json()["name"] == "GetMe"


def test_get_tenant_not_found(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    token = make_token(rsa_keypair, tenant_id="nonexistent-id")
    response = client.get(
        "/api/v1/tenants/nonexistent-id",
        headers=_auth(token),
    )
    assert response.status_code == 404


def test_update_tenant(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "Original")
    token = make_token(rsa_keypair, tenant_id=tenant_id)
    response = client.patch(
        f"/api/v1/tenants/{tenant_id}",
        json={"name": "Updated"},
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response.json()["industry"] == "automotive"


def test_delete_tenant(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "DeleteMe", industry="pharmaceutical")
    token = make_token(rsa_keypair, tenant_id=tenant_id)
    response = client.delete(f"/api/v1/tenants/{tenant_id}", headers=_auth(token))
    assert response.status_code == 204
    get_resp = client.get(f"/api/v1/tenants/{tenant_id}", headers=_auth(token))
    assert get_resp.status_code == 404
