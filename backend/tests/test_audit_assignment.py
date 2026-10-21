"""Tests for assigning an auditor and for who may see or move an audit."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.user import User
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign assignment tokens in this module."""
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
    public_jwk["kid"] = "test-key-audit-assignment"
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
    rsa_keypair: dict[str, Any],
    tenant_id: str,
    role: str,
    sub: str,
) -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role, sub=sub)


def _add_user(
    db: Session,
    tenant_id: str,
    role: str,
    sub: str,
    full_name: str,
    *,
    is_active: bool = True,
) -> User:
    user = User(
        tenant_id=tenant_id,
        cognito_sub=sub,
        email=f"{sub}@example.com",
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_audit(client: TestClient, token: str, title: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/audits/",
        json={"title": title},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def test_lead_auditor_assigns_an_auditor_of_the_same_tenant(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Audit Office")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    auditor = _add_user(db, tenant_id, "auditor", "auditor-1", "Ana Auditor")
    audit_id = _create_audit(client, lead, "Line audit")["id"]

    response = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": auditor.id},
        headers=_auth(lead),
    )
    assert response.status_code == 200
    assert response.json()["auditor_id"] == auditor.id
    assert response.json()["status"] == "planned"


@pytest.mark.parametrize("role", ["qa_manager", "auditee", "admin"])
def test_only_an_auditor_can_be_assigned(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    role: str,
) -> None:
    tenant_id = _create_tenant(client, f"Assign {role}")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    other = _add_user(db, tenant_id, role, f"person-{role}", "Not an auditor")
    audit_id = _create_audit(client, lead, "Line audit")["id"]

    response = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": other.id},
        headers=_auth(lead),
    )
    assert response.status_code == 422
    unchanged = client.get(f"/api/v1/audits/{audit_id}", headers=_auth(lead))
    assert unchanged.json()["auditor_id"] is None


def test_inactive_or_foreign_auditor_cannot_be_assigned(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Org A")
    tenant_b = _create_tenant(client, "Org B")
    lead = _token(rsa_keypair, tenant_a, "lead_auditor", "lead-a")
    inactive = _add_user(
        db, tenant_a, "auditor", "inactive-1", "Inactive", is_active=False
    )
    foreign = _add_user(db, tenant_b, "auditor", "foreign-1", "Foreign")
    audit_id = _create_audit(client, lead, "Local audit")["id"]

    inactive_response = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": inactive.id},
        headers=_auth(lead),
    )
    foreign_response = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": foreign.id},
        headers=_auth(lead),
    )
    assert inactive_response.status_code == 422
    assert foreign_response.status_code == 422


def test_qa_manager_views_status_and_cannot_edit(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Quality View")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    manager = _token(rsa_keypair, tenant_id, "qa_manager", "qa-1")
    auditor = _add_user(db, tenant_id, "auditor", "auditor-1", "Ana Auditor")
    created = _create_audit(client, lead, "Watched audit")
    assigned = client.patch(
        f"/api/v1/audits/{created['id']}/auditor",
        json={"auditor_id": auditor.id},
        headers=_auth(lead),
    )
    assert assigned.status_code == 200

    listed = client.get("/api/v1/audits/", headers=_auth(manager))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["status"] == "planned"

    edited = client.patch(
        f"/api/v1/audits/{created['id']}",
        json={"title": "Changed by quality"},
        headers=_auth(manager),
    )
    assert edited.status_code == 403
    detail = client.get(f"/api/v1/audits/{created['id']}", headers=_auth(manager))
    assert detail.json()["title"] == "Watched audit"


def test_assigned_auditor_sees_only_their_audits_and_moves_status(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "My Audits")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    ana = _add_user(db, tenant_id, "auditor", "ana", "Ana")
    luis = _add_user(db, tenant_id, "auditor", "luis", "Luis")
    ana_token = _token(rsa_keypair, tenant_id, "auditor", "ana")
    luis_token = _token(rsa_keypair, tenant_id, "auditor", "luis")
    first = _create_audit(client, lead, "Ana's audit")
    second = _create_audit(client, lead, "Luis's audit")
    for audit, user in ((first, ana), (second, luis)):
        response = client.patch(
            f"/api/v1/audits/{audit['id']}/auditor",
            json={"auditor_id": user.id},
            headers=_auth(lead),
        )
        assert response.status_code == 200

    mine = client.get("/api/v1/audits/", params={"mine": True}, headers=_auth(ana_token))
    assert mine.status_code == 200
    assert mine.json()["total"] == 1
    assert mine.json()["items"][0]["title"] == "Ana's audit"

    luis_mine = client.get(
        "/api/v1/audits/", params={"mine": True}, headers=_auth(luis_token)
    )
    assert luis_mine.status_code == 200
    assert luis_mine.json()["total"] == 1
    assert luis_mine.json()["items"][0]["title"] == "Luis's audit"

    moved = client.patch(
        f"/api/v1/audits/{first['id']}/status",
        json={"status": "in_progress"},
        headers=_auth(ana_token),
    )
    assert moved.status_code == 200
    assert moved.json()["status"] == "in_progress"

    denied = client.patch(
        f"/api/v1/audits/{second['id']}/status",
        json={"status": "in_progress"},
        headers=_auth(ana_token),
    )
    assert denied.status_code == 403


def test_unassigned_auditor_cannot_change_status(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Unassigned")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    _add_user(db, tenant_id, "auditor", "ana", "Ana")
    ana = _token(rsa_keypair, tenant_id, "auditor", "ana")
    audit_id = _create_audit(client, lead, "No owner yet")["id"]

    response = client.patch(
        f"/api/v1/audits/{audit_id}/status",
        json={"status": "in_progress"},
        headers=_auth(ana),
    )
    assert response.status_code == 403


def test_admin_can_change_status_of_any_audit(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Exception")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    admin = _token(rsa_keypair, tenant_id, "admin", "admin-1")
    ana = _add_user(db, tenant_id, "auditor", "ana", "Ana")
    audit_id = _create_audit(client, lead, "Needs an exception")["id"]
    assigned = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": ana.id},
        headers=_auth(lead),
    )
    assert assigned.status_code == 200

    response = client.patch(
        f"/api/v1/audits/{audit_id}/status",
        json={"status": "in_progress"},
        headers=_auth(admin),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


def test_lead_auditor_sees_status_and_cannot_change_it(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Lead View")
    lead = _token(rsa_keypair, tenant_id, "lead_auditor", "lead-1")
    ana = _add_user(db, tenant_id, "auditor", "ana", "Ana")
    audit_id = _create_audit(client, lead, "Team audit")["id"]
    client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": ana.id},
        headers=_auth(lead),
    )

    listed = client.get("/api/v1/audits/", headers=_auth(lead))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["status"] == "planned"

    denied = client.patch(
        f"/api/v1/audits/{audit_id}/status",
        json={"status": "in_progress"},
        headers=_auth(lead),
    )
    assert denied.status_code == 403


def test_list_available_auditors_is_limited_to_the_tenant(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Roster A")
    tenant_b = _create_tenant(client, "Roster B")
    lead = _token(rsa_keypair, tenant_a, "lead_auditor", "lead-a")
    manager = _token(rsa_keypair, tenant_a, "qa_manager", "qa-a")
    _add_user(db, tenant_a, "auditor", "ana", "Ana")
    _add_user(db, tenant_a, "auditor", "inactive", "Idle", is_active=False)
    _add_user(db, tenant_a, "auditee", "auditee-1", "Auditee")
    _add_user(db, tenant_b, "auditor", "foreign", "Foreign")

    listed = client.get("/api/v1/auditors/", headers=_auth(lead))
    assert listed.status_code == 200
    names = [item["full_name"] for item in listed.json()]
    assert names == ["Ana"]

    hidden = client.get("/api/v1/auditors/", headers=_auth(manager))
    assert hidden.status_code == 403


def test_another_tenant_cannot_assign(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Owner")
    tenant_b = _create_tenant(client, "Outsider")
    lead_a = _token(rsa_keypair, tenant_a, "lead_auditor", "lead-a")
    lead_b = _token(rsa_keypair, tenant_b, "lead_auditor", "lead-b")
    auditor = _add_user(db, tenant_a, "auditor", "ana", "Ana")
    audit_id = _create_audit(client, lead_a, "Private")["id"]

    response = client.patch(
        f"/api/v1/audits/{audit_id}/auditor",
        json={"auditor_id": auditor.id},
        headers=_auth(lead_b),
    )
    assert response.status_code == 404
