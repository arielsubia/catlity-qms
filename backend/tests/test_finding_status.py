"""Tests for the finding state machine."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.api.v1 import findings as findings_api
from app.core import security
from app.core.config import settings
from app.models.finding import Finding
from app.models.user import User
from tests.test_audits import _auth, _create_audit, _create_tenant
from tests.test_auth import make_token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign finding-status tokens in this module."""
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
    public_jwk["kid"] = "test-key-finding-status"
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
    groups: list[str] | None = None,
) -> str:
    return make_token(
        rsa_keypair, tenant_id=tenant_id, role=role, sub=sub, groups=groups
    )


def _create_finding(client: TestClient, token: str, audit_id: str) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json={"title": "Missing record"},
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def _assign_auditee(
    db: Session,
    tenant_id: str,
    finding_id: str,
    sub: str = "auditee-sub",
    *,
    active: bool = True,
) -> None:
    """Attach the token subject as the auditee responsible for this finding."""
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


def _change_status(
    client: TestClient, token: str, finding_id: str, new_status: str
) -> Any:
    return client.patch(
        f"/api/v1/findings/{finding_id}/status",
        json={"status": new_status},
        headers=_auth(token),
    )


def _open_finding(
    client: TestClient, rsa_keypair: dict[str, Any], name: str
) -> tuple[str, str, str, str]:
    """Create a tenant, an audit, and an open finding. Return ids and the creator token."""
    tenant_id = _create_tenant(client, name)
    creator = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")
    audit_id = _create_audit(client, creator)["id"]
    finding_id = _create_finding(client, creator, audit_id)["id"]
    return tenant_id, creator, audit_id, finding_id


def test_new_finding_has_no_status_timestamp(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    _tenant_id, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Fresh Finding"
    )
    listed = client.get("/api/v1/findings", headers=_auth(creator))
    assert listed.status_code == 200
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == "open"
    assert row["status_changed_at"] is None


def test_assigned_auditee_and_verifier_walk_the_happy_path(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    times = iter(
        [
            datetime(2026, 10, 23, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 23, 13, 0, tzinfo=UTC),
            datetime(2026, 10, 23, 14, 0, tzinfo=UTC),
            datetime(2026, 10, 23, 15, 0, tzinfo=UTC),
        ]
    )
    monkeypatch.setattr(findings_api, "_utcnow", lambda: next(times))

    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Happy Path"
    )
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    verifier = _token(rsa_keypair, tenant_id, role="auditor", sub="auditor-sub")

    started = _change_status(client, auditee, finding_id, "in_progress")
    assert started.status_code == 200
    assert started.json()["status"] == "in_progress"
    assert started.json()["status_changed_at"].startswith("2026-10-23T12:00:00")

    resolved = _change_status(client, auditee, finding_id, "resolved")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["status_changed_at"].startswith("2026-10-23T13:00:00")

    verified = _change_status(client, verifier, finding_id, "verified")
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["status_changed_at"].startswith("2026-10-23T14:00:00")

    closed = _change_status(client, verifier, finding_id, "closed")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["status_changed_at"].startswith("2026-10-23T15:00:00")


def test_admin_can_walk_the_whole_path_without_an_assignee(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Admin Path"
    )
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    for step in ("in_progress", "resolved", "verified", "closed"):
        response = _change_status(client, admin, finding_id, step)
        assert response.status_code == 200
        assert response.json()["status"] == step


@pytest.mark.parametrize("role", ["auditor", "lead_auditor", "admin"])
def test_verifiers_can_reject_and_then_close(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, f"Reject {role}"
    )
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    verifier = _token(rsa_keypair, tenant_id, role=role, sub=f"{role}-sub")
    assert _change_status(client, auditee, finding_id, "in_progress").status_code == 200
    assert _change_status(client, auditee, finding_id, "resolved").status_code == 200

    rejected = _change_status(client, verifier, finding_id, "in_progress")
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "in_progress"

    assert _change_status(client, auditee, finding_id, "resolved").status_code == 200
    assert _change_status(client, verifier, finding_id, "verified").status_code == 200
    closed = _change_status(client, verifier, finding_id, "closed")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"


def test_lead_auditor_group_can_verify(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Group Verifier"
    )
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    grouped = _token(
        rsa_keypair,
        tenant_id,
        role="qa_manager",
        sub="grouped-sub",
        groups=["lead_auditor"],
    )
    assert _change_status(client, auditee, finding_id, "in_progress").status_code == 200
    assert _change_status(client, auditee, finding_id, "resolved").status_code == 200
    verified = _change_status(client, grouped, finding_id, "verified")
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"


def test_assigned_auditee_cannot_verify_reject_or_close(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "No Self Verify"
    )
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    assert _change_status(client, auditee, finding_id, "in_progress").status_code == 200
    assert _change_status(client, auditee, finding_id, "resolved").status_code == 200

    for target in ("verified", "in_progress", "closed"):
        response = _change_status(client, auditee, finding_id, target)
        assert response.status_code == 403

    listed = client.get("/api/v1/findings", headers=_auth(creator))
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == "resolved"


def test_verifier_cannot_move_the_work_steps(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Verifier Work"
    )
    auditor = _token(rsa_keypair, tenant_id, role="auditor", sub="other-auditor")
    response = _change_status(client, auditor, finding_id, "in_progress")
    assert response.status_code == 403

    listed = client.get("/api/v1/findings", headers=_auth(creator))
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == "open"
    assert row["status_changed_at"] is None


@pytest.mark.parametrize("role", ["qa_manager", "auditee", "lead_auditor"])
def test_unassigned_roles_cannot_start_work(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, f"Blocked {role}"
    )
    actor = _token(rsa_keypair, tenant_id, role=role, sub=f"{role}-sub")
    response = _change_status(client, actor, finding_id, "in_progress")
    assert response.status_code == 403

    listed = client.get("/api/v1/findings", headers=_auth(creator))
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == "open"


def test_inactive_assignee_cannot_change_status(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Inactive Auditee"
    )
    _assign_auditee(db, tenant_id, finding_id, active=False)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    response = _change_status(client, auditee, finding_id, "in_progress")
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("open", "resolved"),
        ("open", "verified"),
        ("open", "closed"),
        ("open", "open"),
        ("in_progress", "open"),
        ("in_progress", "verified"),
        ("resolved", "closed"),
        ("resolved", "resolved"),
        ("verified", "resolved"),
        ("closed", "open"),
    ],
)
def test_invalid_transition_returns_422(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    current: str,
    target: str,
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, f"Invalid {current} {target}"
    )
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    for step in ("in_progress", "resolved", "verified", "closed"):
        if current == "open":
            break
        moved = _change_status(client, admin, finding_id, step)
        assert moved.status_code == 200
        if step == current:
            break

    response = _change_status(client, admin, finding_id, target)
    assert response.status_code == 422

    listed = client.get("/api/v1/findings", headers=_auth(admin))
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == current


def test_unknown_status_returns_422(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, _creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Unknown Status"
    )
    admin = _token(rsa_keypair, tenant_id, role="admin", sub="admin-sub")
    response = _change_status(client, admin, finding_id, "cancelled")
    assert response.status_code == 422


def test_other_tenant_cannot_change_status(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    _tenant_a, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Tenant A Finding"
    )
    tenant_b = _create_tenant(client, "Tenant B Finding")
    intruder = _token(rsa_keypair, tenant_b, role="admin", sub="admin-b")
    response = _change_status(client, intruder, finding_id, "in_progress")
    assert response.status_code == 404

    listed = client.get("/api/v1/findings", headers=_auth(creator))
    row = next(item for item in listed.json()["items"] if item["id"] == finding_id)
    assert row["status"] == "open"
    assert row["status_changed_at"] is None


def test_status_change_requires_token(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/findings/some-id/status",
        json={"status": "in_progress"},
    )
    assert response.status_code == 401


def test_descriptive_patch_does_not_change_status(
    client: TestClient, db: Session, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id, creator, _audit_id, finding_id = _open_finding(
        client, rsa_keypair, "Descriptive Patch"
    )
    _assign_auditee(db, tenant_id, finding_id)
    auditee = _token(rsa_keypair, tenant_id, role="auditee", sub="auditee-sub")
    assert _change_status(client, auditee, finding_id, "in_progress").status_code == 200

    edited = client.patch(
        f"/api/v1/findings/{finding_id}",
        json={"title": "Renamed", "status": "closed"},
        headers=_auth(creator),
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "Renamed"
    assert edited.json()["status"] == "in_progress"
    assert edited.json()["status_changed_at"].startswith("20")
