"""Tests for tenant-scoped corrective action create, list, read, update, and delete."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.finding import Finding
from app.models.user import User
from tests.test_audits import _auth, _create_audit, _create_tenant
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign corrective-action tokens in this module."""
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
    public_jwk["kid"] = "test-key-corrective-actions"
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


def _token(
    rsa_keypair: dict[str, Any],
    tenant_id: str,
    role: str = "auditor",
    sub: str = "user-sub-123",
) -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role, sub=sub)


def _open_finding(
    client: TestClient, rsa_keypair: dict[str, Any], name: str
) -> tuple[str, str, str]:
    """Create a tenant, an audit, and a finding. Return tenant id, creator token, finding id."""
    tenant_id = _create_tenant(client, name)
    creator = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")
    audit_id = _create_audit(client, creator)["id"]
    response = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json={"title": "Missing record"},
        headers=_auth(creator),
    )
    assert response.status_code == 201
    return tenant_id, creator, response.json()["id"]


def _assign_auditee(
    db: Session,
    tenant_id: str,
    finding_id: str,
    *,
    active: bool = True,
    sub: str = "auditee-sub",
) -> None:
    user = User(
        tenant_id=tenant_id,
        cognito_sub=sub,
        email=f"{sub}@example.com",
        full_name="Assigned auditee",
        role="auditee",
        is_active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    finding = db.query(Finding).filter(Finding.id == finding_id).one()
    finding.assignee_id = user.id
    db.commit()


def _create_action(
    client: TestClient,
    token: str,
    finding_id: str,
    description: str = "Recalibrate the gauge",
    **extra: Any,
) -> dict[str, Any]:
    payload = {"description": description, **extra}
    response = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json=payload,
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def test_create_action_starts_pending(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Create Action")
    _assign_auditee(db, tenant_id, finding_id)
    other = _open_finding(client, rsa_keypair, "Other Finding Org")
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    response = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={
            "description": "Replace the record",
            "due_date": "2026-11-15",
            "completion_date": "2026-11-20",
            "effectiveness": "Effective after review",
            "status": "closed",
            "action_type": "preventive",
            "responsible_id": "someone",
            "finding_id": other[2],
        },
        headers=_auth(auditee),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Replace the record"
    assert data["due_date"] == "2026-11-15"
    assert data["completion_date"] == "2026-11-20"
    assert data["effectiveness"] == "Effective after review"
    assert data["status"] == "pending"
    assert data["action_type"] == "corrective"
    assert data["responsible_id"] is None
    assert data["finding_id"] == finding_id
    assert data["tenant_id"] == tenant_id


def test_create_action_allows_empty_optional_fields(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Defaults Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id)
    assert created["due_date"] is None
    assert created["completion_date"] is None
    assert created["effectiveness"] is None
    assert created["status"] == "pending"


def test_admin_can_create_without_an_assignee(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Admin Action")
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    created = _create_action(client, admin, finding_id, description="Admin plan")
    assert created["status"] == "pending"
    assert created["finding_id"] == finding_id


@pytest.mark.parametrize("role", ["auditor", "lead_auditor", "qa_manager", "auditee"])
def test_unassigned_roles_cannot_create_action(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id, _creator, finding_id = _open_finding(
        client, rsa_keypair, f"Blocked create {role}"
    )
    actor = _token(rsa_keypair, tenant_id, role=role, sub=f"{role}-sub")
    response = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={"description": "Should fail"},
        headers=_auth(actor),
    )
    assert response.status_code == 403


def test_inactive_assignee_cannot_create_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Inactive Action")
    _assign_auditee(db, tenant_id, finding_id, active=False)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    response = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={"description": "Should fail"},
        headers=_auth(auditee),
    )
    assert response.status_code == 403


def test_create_action_rejects_invalid_payload(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Invalid Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    empty = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={"description": ""},
        headers=_auth(auditee),
    )
    assert empty.status_code == 422
    long_text = client.post(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        json={"description": "Plan", "effectiveness": "x" * 256},
        headers=_auth(auditee),
    )
    assert long_text.status_code == 422


def test_create_action_on_missing_or_foreign_finding_returns_404(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    _tenant_a, creator_a, finding_a = _open_finding(client, rsa_keypair, "Action Tenant A")
    tenant_b, _creator_b, _finding_b = _open_finding(client, rsa_keypair, "Action Tenant B")
    admin_b = _token(rsa_keypair, tenant_b, role="admin", sub="admin-b")
    foreign = client.post(
        f"/api/v1/findings/{finding_a}/corrective-actions",
        json={"description": "Stolen action"},
        headers=_auth(admin_b),
    )
    assert foreign.status_code == 404
    assert "Stolen action" not in foreign.text

    missing = client.post(
        "/api/v1/findings/does-not-exist/corrective-actions",
        json={"description": "Orphan"},
        headers=_auth(creator_a),
    )
    assert missing.status_code == 404


def test_one_finding_can_hold_several_actions(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, finding_id = _open_finding(client, rsa_keypair, "Several Actions")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    audit_id = client.get(
        "/api/v1/findings",
        headers=_auth(creator),
    ).json()["items"][0]["audit_id"]
    other = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json={"title": "Second finding"},
        headers=_auth(creator),
    )
    assert other.status_code == 201
    other_id = other.json()["id"]
    first = db.query(Finding).filter(Finding.id == finding_id).one()
    second = db.query(Finding).filter(Finding.id == other_id).one()
    second.assignee_id = first.assignee_id
    db.commit()
    created_ids = {
        _create_action(client, auditee, finding_id, description=f"Step {index}")["id"]
        for index in range(3)
    }
    _create_action(client, auditee, other_id, description="Belongs elsewhere")

    first = client.get(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        params={"skip": 0, "limit": 2},
        headers=_auth(creator),
    )
    assert first.status_code == 200
    assert first.json()["total"] == 3
    assert len(first.json()["items"]) == 2

    second = client.get(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        params={"skip": 2, "limit": 2},
        headers=_auth(creator),
    )
    assert second.status_code == 200
    seen = {item["id"] for item in first.json()["items"] + second.json()["items"]}
    assert seen == created_ids
    titles = [item["description"] for item in first.json()["items"] + second.json()["items"]]
    assert "Belongs elsewhere" not in titles


def test_get_action_and_reader_role(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Read Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    reader = _token(rsa_keypair, tenant_id, role="qa_manager", sub="reader-sub")
    created = _create_action(client, auditee, finding_id, description="Visible plan")

    own = client.get(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(reader),
    )
    assert own.status_code == 200
    assert own.json()["description"] == "Visible plan"

    listed = client.get(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        headers=_auth(reader),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_other_tenant_cannot_read_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Hidden Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id, description="Secret plan")
    tenant_b = _create_tenant(client, "Reader Tenant B")
    intruder = _token(rsa_keypair, tenant_b, role="admin", sub="admin-b")

    hidden = client.get(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(intruder),
    )
    assert hidden.status_code == 404
    assert "Secret plan" not in hidden.text

    missing_finding = client.get(
        f"/api/v1/findings/{finding_id}/corrective-actions",
        headers=_auth(intruder),
    )
    assert missing_finding.status_code == 404


def test_update_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Edit Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id, description="Original plan")
    response = client.patch(
        f"/api/v1/corrective-actions/{created['id']}",
        json={
            "description": "Updated plan",
            "due_date": "2026-12-01",
            "completion_date": "2026-12-05",
            "effectiveness": "Checked on the line",
            "status": "closed",
            "action_type": "preventive",
            "responsible_id": "lead-1",
            "finding_id": "other-finding",
        },
        headers=_auth(auditee),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated plan"
    assert data["due_date"] == "2026-12-01"
    assert data["completion_date"] == "2026-12-05"
    assert data["effectiveness"] == "Checked on the line"
    assert data["status"] == "pending"
    assert data["action_type"] == "corrective"
    assert data["responsible_id"] is None
    assert data["finding_id"] == finding_id


def test_update_rejects_null_description(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, "Null Description")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id)
    response = client.patch(
        f"/api/v1/corrective-actions/{created['id']}",
        json={"description": None},
        headers=_auth(auditee),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("role", ["auditor", "qa_manager"])
def test_readers_cannot_update_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id, _creator, finding_id = _open_finding(client, rsa_keypair, f"No edit {role}")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    actor = _token(rsa_keypair, tenant_id, role=role, sub=f"{role}-sub")
    created = _create_action(client, auditee, finding_id)
    response = client.patch(
        f"/api/v1/corrective-actions/{created['id']}",
        json={"description": "Changed"},
        headers=_auth(actor),
    )
    assert response.status_code == 403


def test_delete_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, finding_id = _open_finding(client, rsa_keypair, "Delete Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id, description="Remove me")
    deleted = client.delete(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(auditee),
    )
    assert deleted.status_code == 204
    assert deleted.content == b""

    missing = client.get(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(creator),
    )
    assert missing.status_code == 404


def test_other_tenant_cannot_delete_action(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, finding_id = _open_finding(client, rsa_keypair, "Keep Action")
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    created = _create_action(client, auditee, finding_id, description="Stay")
    tenant_b = _create_tenant(client, "Delete Tenant B")
    intruder = _token(rsa_keypair, tenant_b, role="admin", sub="admin-b")
    response = client.delete(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(intruder),
    )
    assert response.status_code == 404

    still_there = client.get(
        f"/api/v1/corrective-actions/{created['id']}",
        headers=_auth(creator),
    )
    assert still_there.status_code == 200
    assert still_there.json()["description"] == "Stay"


def test_list_actions_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/findings/some-id/corrective-actions")
    assert response.status_code == 401
