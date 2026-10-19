"""Tests for the audit state machine."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk

from app.api.v1 import audits as audits_api
from app.core import security
from app.core.config import settings
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign status-change tokens in this module."""
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
    public_jwk["kid"] = "test-key-audit-status"
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


def _token(rsa_keypair: dict[str, Any], tenant_id: str, role: str = "auditor") -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role)


def _create_audit(client: TestClient, token: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/audits/",
        json={"title": "Process audit"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def _change_status(
    client: TestClient, token: str, audit_id: str, new_status: str
) -> Any:
    return client.patch(
        f"/api/v1/audits/{audit_id}/status",
        json={"status": new_status},
        headers=_auth(token),
    )


def test_new_audit_has_no_status_timestamp(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Fresh Org")
    token = _token(rsa_keypair, tenant_id)
    created = _create_audit(client, token)
    assert created["status"] == "planned"
    assert created["status_changed_at"] is None


def test_forward_transitions_record_each_timestamp(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter(
        [
            datetime(2026, 10, 19, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 13, 0, tzinfo=UTC),
            datetime(2026, 10, 19, 14, 0, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(audits_api, "_utcnow", lambda: next(times))

    tenant_id = _create_tenant(client, "Flow Org")
    token = _token(rsa_keypair, tenant_id)
    audit_id = _create_audit(client, token)["id"]

    started = _change_status(client, token, audit_id, "in_progress")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["status_changed_at"].startswith("2026-10-19T12:00:00")

    finished = _change_status(client, token, audit_id, "completed")
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"
    assert finished.json()["status_changed_at"].startswith("2026-10-19T13:00:00")

    closed = _change_status(client, token, audit_id, "closed")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["status_changed_at"].startswith("2026-10-19T14:00:00")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("planned", "completed"),
        ("planned", "closed"),
        ("planned", "planned"),
        ("in_progress", "planned"),
        ("in_progress", "closed"),
        ("completed", "in_progress"),
        ("closed", "planned"),
    ],
)
def test_invalid_transition_returns_422(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    current: str,
    target: str,
) -> None:
    tenant_id = _create_tenant(client, f"Invalid {current} {target}")
    token = _token(rsa_keypair, tenant_id)
    audit_id = _create_audit(client, token)["id"]
    for step in ("in_progress", "completed", "closed"):
        if current == "planned":
            break
        moved = _change_status(client, token, audit_id, step)
        assert moved.status_code == 200
        if step == current:
            break

    response = _change_status(client, token, audit_id, target)
    assert response.status_code == 422

    unchanged = client.get(f"/api/v1/audits/{audit_id}", headers=_auth(token))
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] == current


def test_unknown_status_returns_422(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Unknown Status Org")
    token = _token(rsa_keypair, tenant_id)
    audit_id = _create_audit(client, token)["id"]
    response = _change_status(client, token, audit_id, "cancelled")
    assert response.status_code == 422


@pytest.mark.parametrize("role", ["auditor", "admin"])
def test_auditor_and_admin_can_change_status(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"Role {role}")
    creator = _token(rsa_keypair, tenant_id, role="auditor")
    audit_id = _create_audit(client, creator)["id"]
    actor = _token(rsa_keypair, tenant_id, role=role)
    response = _change_status(client, actor, audit_id, "in_progress")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


@pytest.mark.parametrize("role", ["qa_manager", "auditee"])
def test_other_roles_cannot_change_status(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"Blocked {role}")
    creator = _token(rsa_keypair, tenant_id, role="auditor")
    audit_id = _create_audit(client, creator)["id"]
    actor = _token(rsa_keypair, tenant_id, role=role)
    response = _change_status(client, actor, audit_id, "in_progress")
    assert response.status_code == 403

    unchanged = client.get(f"/api/v1/audits/{audit_id}", headers=_auth(creator))
    assert unchanged.json()["status"] == "planned"
    assert unchanged.json()["status_changed_at"] is None


def test_other_tenant_cannot_change_status(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Tenant A")
    tenant_b = _create_tenant(client, "Tenant B")
    token_a = _token(rsa_keypair, tenant_a)
    token_b = _token(rsa_keypair, tenant_b, role="admin")
    audit_id = _create_audit(client, token_a)["id"]

    response = _change_status(client, token_b, audit_id, "in_progress")
    assert response.status_code == 404

    unchanged = client.get(f"/api/v1/audits/{audit_id}", headers=_auth(token_a))
    assert unchanged.json()["status"] == "planned"
    assert unchanged.json()["status_changed_at"] is None


def test_status_change_requires_token(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/audits/some-id/status",
        json={"status": "in_progress"},
    )
    assert response.status_code == 401
