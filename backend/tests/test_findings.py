"""Tests for tenant-scoped finding create, list, and update."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk

from app.core import security
from app.core.config import settings
from tests.test_audits import _auth, _create_audit, _create_tenant, _token


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign finding tokens in this module."""
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
    public_jwk["kid"] = "test-key-findings"
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


def _create_finding(
    client: TestClient,
    token: str,
    audit_id: str,
    title: str = "Missing calibration record",
    **extra: Any,
) -> dict[str, Any]:
    payload = {"title": title, **extra}
    response = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json=payload,
        headers=_auth(token),
    )
    assert response.status_code == 201
    return response.json()


def test_create_finding_starts_as_open(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "AutoCorp Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token, title="Process audit")
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={
            "title": "Gauge out of tolerance",
            "description": "Clause 7.1.5",
            "finding_type": "major_nc",
            "severity": "high",
            "clause_reference": "7.1.5",
            "status": "closed",
            "assignee_id": "someone-else",
            "audit_id": "other-audit",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Gauge out of tolerance"
    assert data["description"] == "Clause 7.1.5"
    assert data["finding_type"] == "major_nc"
    assert data["severity"] == "high"
    assert data["clause_reference"] == "7.1.5"
    assert data["status"] == "open"
    assert data["assignee_id"] is None
    assert data["tenant_id"] == tenant_id
    assert data["audit_id"] == audit["id"]


def test_create_finding_uses_column_defaults(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Defaults Org")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    created = _create_finding(client, token, audit["id"], title="Note only")
    assert created["finding_type"] == "minor_nc"
    assert created["severity"] == "medium"
    assert created["description"] is None
    assert created["clause_reference"] is None
    assert created["status"] == "open"


@pytest.mark.parametrize("role", ["auditor", "admin", "lead_auditor"])
def test_create_finding_allowed_roles(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"Finding org {role}")
    token = _token(rsa_keypair, tenant_id, role=role)
    audit = _create_audit(client, token, title=f"Audit by {role}")
    created = _create_finding(client, token, audit["id"], title=f"Finding by {role}")
    assert created["status"] == "open"


@pytest.mark.parametrize("role", ["qa_manager", "auditee"])
def test_consulting_roles_cannot_create_finding(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"Consult {role}")
    owner = _token(rsa_keypair, tenant_id, role="auditor")
    audit = _create_audit(client, owner)
    token = _token(rsa_keypair, tenant_id, role=role)
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Should fail"},
        headers=_auth(token),
    )
    assert response.status_code == 403


def test_create_finding_requires_token(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "No Token Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "No token"},
    )
    assert response.status_code == 401


def test_create_finding_rejects_invalid_payload(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Validation Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    empty_title = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": ""},
        headers=_auth(token),
    )
    assert empty_title.status_code == 422

    bad_type = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Bad type", "finding_type": "critical"},
        headers=_auth(token),
    )
    assert bad_type.status_code == 422

    long_severity = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Long severity", "severity": "x" * 51},
        headers=_auth(token),
    )
    assert long_severity.status_code == 422


def test_create_finding_unknown_audit_returns_404(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Missing Audit Org")
    token = _token(rsa_keypair, tenant_id)
    response = client.post(
        "/api/v1/audits/does-not-exist/findings",
        json={"title": "Orphan"},
        headers=_auth(token),
    )
    assert response.status_code == 404


def test_create_finding_on_another_tenants_audit_returns_404(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Finding Tenant A")
    tenant_b = _create_tenant(client, "Finding Tenant B")
    token_a = _token(rsa_keypair, tenant_a)
    token_b = _token(rsa_keypair, tenant_b)
    audit = _create_audit(client, token_a, title="Secret audit")

    response = client.post(
        f"/api/v1/audits/{audit['id']}/findings",
        json={"title": "Stolen finding"},
        headers=_auth(token_b),
    )
    assert response.status_code == 404
    assert "Stolen finding" not in response.text

    listed = client.get(
        f"/api/v1/audits/{audit['id']}/findings",
        headers=_auth(token_a),
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 0


def test_list_findings_by_audit_is_paginated(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Paged Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    other = _create_audit(client, token, title="Other audit")
    created_ids = {
        _create_finding(client, token, audit["id"], title=f"Finding {index}")["id"]
        for index in range(3)
    }
    _create_finding(client, token, other["id"], title="Belongs elsewhere")

    first = client.get(
        f"/api/v1/audits/{audit['id']}/findings",
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
        f"/api/v1/audits/{audit['id']}/findings",
        params={"skip": 2, "limit": 2},
        headers=_auth(token),
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["total"] == 3
    assert len(second_body["items"]) == 1

    seen = {item["id"] for item in first_body["items"] + second_body["items"]}
    assert seen == created_ids
    titles = [item["title"] for item in first_body["items"] + second_body["items"]]
    assert "Belongs elsewhere" not in titles


def test_list_findings_by_audit_hides_other_tenants(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "List A")
    tenant_b = _create_tenant(client, "List B")
    token_a = _token(rsa_keypair, tenant_a)
    token_b = _token(rsa_keypair, tenant_b)
    audit = _create_audit(client, token_a, title="Only A")
    _create_finding(client, token_a, audit["id"], title="Hidden finding")

    missing = client.get(
        f"/api/v1/audits/{audit['id']}/findings",
        headers=_auth(token_b),
    )
    assert missing.status_code == 404
    assert "Hidden finding" not in missing.text

    unknown = client.get(
        "/api/v1/audits/does-not-exist/findings",
        headers=_auth(token_a),
    )
    assert unknown.status_code == 404


def test_list_all_findings_filters(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Filter Findings")
    token = _token(rsa_keypair, tenant_id)
    first_audit = _create_audit(client, token, title="Line audit")
    second_audit = _create_audit(client, token, title="Supplier audit")
    major = _create_finding(
        client,
        token,
        first_audit["id"],
        title="Major gap",
        finding_type="major_nc",
    )
    _create_finding(
        client,
        token,
        second_audit["id"],
        title="Observation",
        finding_type="observation",
    )

    by_type = client.get(
        "/api/v1/findings",
        params={"finding_type": "major_nc"},
        headers=_auth(token),
    )
    assert by_type.status_code == 200
    assert by_type.json()["total"] == 1
    assert by_type.json()["items"][0]["id"] == major["id"]

    by_audit = client.get(
        "/api/v1/findings",
        params={"audit_id": second_audit["id"]},
        headers=_auth(token),
    )
    assert by_audit.status_code == 200
    assert by_audit.json()["total"] == 1
    assert by_audit.json()["items"][0]["title"] == "Observation"

    by_status = client.get(
        "/api/v1/findings",
        params={"status": "open"},
        headers=_auth(token),
    )
    assert by_status.status_code == 200
    assert by_status.json()["total"] == 2

    other_status = client.get(
        "/api/v1/findings",
        params={"status": "closed"},
        headers=_auth(token),
    )
    assert other_status.status_code == 200
    assert other_status.json()["total"] == 0
    assert other_status.json()["items"] == []


def test_list_findings_rejects_invalid_query(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Query Findings")
    token = _token(rsa_keypair, tenant_id)
    bad_page = client.get(
        "/api/v1/findings",
        params={"limit": 0},
        headers=_auth(token),
    )
    assert bad_page.status_code == 422

    bad_type = client.get(
        "/api/v1/findings",
        params={"finding_type": "critical"},
        headers=_auth(token),
    )
    assert bad_type.status_code == 422


def test_consulting_role_can_list_findings(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Reader Org")
    owner = _token(rsa_keypair, tenant_id, role="auditor")
    reader = _token(rsa_keypair, tenant_id, role="qa_manager")
    audit = _create_audit(client, owner)
    created = _create_finding(client, owner, audit["id"], title="Visible")

    listed = client.get("/api/v1/findings", headers=_auth(reader))
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == created["id"]


def test_list_findings_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/findings")
    assert response.status_code == 401


def test_update_finding(client: TestClient, rsa_keypair: dict[str, Any]) -> None:
    tenant_id = _create_tenant(client, "Edit Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    other = _create_audit(client, token, title="Not the parent")
    created = _create_finding(
        client,
        token,
        audit["id"],
        title="Original",
        description="Keep me",
        finding_type="minor_nc",
    )
    response = client.patch(
        f"/api/v1/findings/{created['id']}",
        json={
            "title": "Updated title",
            "finding_type": "improvement_opportunity",
            "severity": "low",
            "clause_reference": "10.2",
            "status": "closed",
            "assignee_id": "lead-1",
            "audit_id": other["id"],
        },
        headers=_auth(token),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["description"] == "Keep me"
    assert data["finding_type"] == "improvement_opportunity"
    assert data["severity"] == "low"
    assert data["clause_reference"] == "10.2"
    assert data["status"] == "open"
    assert data["assignee_id"] is None
    assert data["audit_id"] == audit["id"]


def test_update_finding_rejects_null_title(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "Null Title Org")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    created = _create_finding(client, token, audit["id"])
    response = client.patch(
        f"/api/v1/findings/{created['id']}",
        json={"title": None},
        headers=_auth(token),
    )
    assert response.status_code == 422


@pytest.mark.parametrize("role", ["qa_manager", "auditee"])
def test_consulting_roles_cannot_update_finding(
    client: TestClient, rsa_keypair: dict[str, Any], role: str
) -> None:
    tenant_id = _create_tenant(client, f"No edit {role}")
    owner = _token(rsa_keypair, tenant_id, role="admin")
    token = _token(rsa_keypair, tenant_id, role=role)
    audit = _create_audit(client, owner)
    created = _create_finding(client, owner, audit["id"])
    response = client.patch(
        f"/api/v1/findings/{created['id']}",
        json={"title": "Changed"},
        headers=_auth(token),
    )
    assert response.status_code == 403


def test_tenant_cannot_see_another_tenants_findings(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_a = _create_tenant(client, "Iso A")
    tenant_b = _create_tenant(client, "Iso B")
    token_a = _token(rsa_keypair, tenant_a)
    token_b = _token(rsa_keypair, tenant_b)
    audit_a = _create_audit(client, token_a, title="Audit A")
    audit_b = _create_audit(client, token_b, title="Audit B")
    own = _create_finding(client, token_a, audit_a["id"], title="Secret finding A")
    _create_finding(client, token_b, audit_b["id"], title="Finding B")

    listed = client.get("/api/v1/findings", headers=_auth(token_b))
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.json()["items"]]
    assert titles == ["Finding B"]
    assert listed.json()["total"] == 1
    assert "Secret finding A" not in listed.text

    filtered = client.get(
        "/api/v1/findings",
        params={"audit_id": audit_a["id"]},
        headers=_auth(token_b),
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 0

    patched = client.patch(
        f"/api/v1/findings/{own['id']}",
        json={"title": "Stolen"},
        headers=_auth(token_b),
    )
    assert patched.status_code == 404

    still_owned = client.get("/api/v1/findings", headers=_auth(token_a))
    assert still_owned.status_code == 200
    assert still_owned.json()["items"][0]["title"] == "Secret finding A"
    assert still_owned.json()["items"][0]["tenant_id"] == tenant_a


def test_delete_finding_is_not_available(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    tenant_id = _create_tenant(client, "No Delete Findings")
    token = _token(rsa_keypair, tenant_id)
    audit = _create_audit(client, token)
    created = _create_finding(client, token, audit["id"])
    response = client.delete(
        f"/api/v1/findings/{created['id']}",
        headers=_auth(token),
    )
    assert response.status_code == 405
