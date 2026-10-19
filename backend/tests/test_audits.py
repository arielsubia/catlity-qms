"""Tests for tenant-scoped audit create, list, read, and update."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk

from app.core import security
from app.core.config import settings
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign audit tokens in this module."""
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
    public_jwk["kid"] = "test-key-audits"
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


def _create_tenant(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/v1/tenants/",
        json={"name": name, "industry": "automotive"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _token(
    rsa_keypair: dict[str, Any], tenant_id: str, role: str = "auditor"
) -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role)


def _create_audit(
    client: TestClient,
    token: str,
    title: str = "Internal process audit",
    **extra: Any,
) -> dict[str, Any]:
    payload = {"title": title, "audit_type": "internal", **extra}
    response = client.post("/api/v1/audits/", json=payload, headers=_auth(token))
    assert response.status_code == 201
    return response.json()


def test_create_audit_starts_as_planned(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "AutoCorp")
    token = _token(rsa_keypair, tenant_id)
    response = client.post(
        "/api/v1/audits/",
        json={
            "title": "ISO 9001 internal",
            "description": "Clause 9.2",
            "audit_type": "internal",
            "planned_date": "2026-11-02",
            "status": "closed",
            "auditor_id": "someone-else",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "ISO 9001 internal"
    assert data["description"] == "Clause 9.2"
    assert data["audit_type"] == "internal"
    assert data["planned_date"] == "2026-11-02"
    assert data["status"] == "planned"
    assert data["tenant_id"] == tenant_id
    assert data["auditor_id"] is None
    assert data["completion_date"] is None


@pytest.mark.parametrize("role", ["auditor", "admin", "qa_manager"])
def test_create_audit_allowed_roles(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"Org {role}")
    token = _token(rsa_keypair, tenant_id, role=role)
    created = _create_audit(client, token, title=f"Audit by {role}")
    assert created["status"] == "planned"


def test_auditee_cannot_create_audit(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Auditee Org")
    token = _token(rsa_keypair, tenant_id, role="auditee")
    response = client.post(
        "/api/v1/audits/",
        json={"title": "Should fail"},
        headers=_auth(token),
    )
    assert response.status_code == 403


def test_create_audit_requires_token(client: TestClient) -> None:
    response = client.post("/api/v1/audits/", json={"title": "No token"})
    assert response.status_code == 401


def test_create_audit_rejects_empty_title(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Validation Org")
    token = _token(rsa_keypair, tenant_id)
    response = client.post(
        "/api/v1/audits/",
        json={"title": ""},
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_list_audits_is_paginated(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Paged Org")
    token = _token(rsa_keypair, tenant_id)
    created_ids = {
        _create_audit(client, token, title=f"Audit {index}")["id"] for index in range(3)
    }

    first = client.get(
        "/api/v1/audits/",
        params={"skip": 0, "limit": 2},
        headers=_auth(token),
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["total"] == 3
    assert first_body["skip"] == 0
    assert first_body["limit"] == 2
    assert len(first_body["items"]) == 2

    second = client.get(
        "/api/v1/audits/",
        params={"skip": 2, "limit": 2},
        headers=_auth(token),
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["total"] == 3
    assert len(second_body["items"]) == 1

    seen = {item["id"] for item in first_body["items"] + second_body["items"]}
    assert seen == created_ids


def test_list_audits_filters_by_type_and_status(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Filter Org")
    token = _token(rsa_keypair, tenant_id)
    _create_audit(client, token, title="Internal one", audit_type="internal")
    external = _create_audit(client, token, title="Supplier visit", audit_type="supplier")

    by_type = client.get(
        "/api/v1/audits/",
        params={"audit_type": "supplier"},
        headers=_auth(token),
    )
    assert by_type.status_code == 200
    assert by_type.json()["total"] == 1
    assert by_type.json()["items"][0]["id"] == external["id"]

    by_status = client.get(
        "/api/v1/audits/",
        params={"status": "planned"},
        headers=_auth(token),
    )
    assert by_status.status_code == 200
    assert by_status.json()["total"] == 2

    other_status = client.get(
        "/api/v1/audits/",
        params={"status": "closed"},
        headers=_auth(token),
    )
    assert other_status.status_code == 200
    assert other_status.json()["total"] == 0
    assert other_status.json()["items"] == []


def test_list_audits_rejects_invalid_page_size(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Page Size Org")
    token = _token(rsa_keypair, tenant_id)
    response = client.get(
        "/api/v1/audits/",
        params={"limit": 0},
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_get_audit(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "Detail Org")
    token = _token(rsa_keypair, tenant_id)
    created = _create_audit(client, token, title="Detail me")
    response = client.get(
        f"/api/v1/audits/{created['id']}",
        headers=_auth(token),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Detail me"
    assert response.json()["status"] == "planned"


def test_get_audit_not_found(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Missing Org")
    token = _token(rsa_keypair, tenant_id)
    response = client.get(
        "/api/v1/audits/does-not-exist",
        headers=_auth(token),
    )
    assert response.status_code == 404


def test_update_audit(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "Edit Org")
    token = _token(rsa_keypair, tenant_id)
    created = _create_audit(client, token, title="Original", audit_type="internal")
    response = client.patch(
        f"/api/v1/audits/{created['id']}",
        json={
            "title": "Updated title",
            "planned_date": "2026-12-01",
            "status": "in_progress",
            "auditor_id": "lead-1",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["planned_date"] == "2026-12-01"
    assert data["audit_type"] == "internal"
    assert data["status"] == "planned"
    assert data["auditor_id"] is None


def test_tenant_cannot_see_another_tenants_audits(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Tenant A")
    tenant_b = _create_tenant(client, "Tenant B")
    token_a = _token(rsa_keypair, tenant_a)
    token_b = _token(rsa_keypair, tenant_b)
    own = _create_audit(client, token_a, title="Secret plan A")
    _create_audit(client, token_b, title="Plan B")

    listed = client.get("/api/v1/audits/", headers=_auth(token_b))
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.json()["items"]]
    assert titles == ["Plan B"]
    assert listed.json()["total"] == 1
    assert "Secret plan A" not in listed.text

    hidden = client.get(f"/api/v1/audits/{own['id']}", headers=_auth(token_b))
    assert hidden.status_code == 404
    assert "Secret plan A" not in hidden.text

    patched = client.patch(
        f"/api/v1/audits/{own['id']}",
        json={"title": "Stolen"},
        headers=_auth(token_b),
    )
    assert patched.status_code == 404

    still_owned = client.get(f"/api/v1/audits/{own['id']}", headers=_auth(token_a))
    assert still_owned.status_code == 200
    assert still_owned.json()["title"] == "Secret plan A"
    assert still_owned.json()["tenant_id"] == tenant_a


def test_delete_audit_is_not_available(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "No Delete Org")
    token = _token(rsa_keypair, tenant_id)
    created = _create_audit(client, token)
    response = client.delete(
        f"/api/v1/audits/{created['id']}",
        headers=_auth(token),
    )
    assert response.status_code == 405
