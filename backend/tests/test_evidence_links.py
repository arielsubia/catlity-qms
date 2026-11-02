"""Link an uploaded evidence item to one or more findings of the same tenant."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.models.evidence import Evidence
from app.models.finding_evidence import FindingEvidence
from tests.test_audits import _auth, _create_audit
from tests.test_auth import make_token
from tests.test_corrective_actions import _open_finding


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign finding-evidence tokens in this module."""
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
    public_jwk["kid"] = "test-key-finding-evidence"
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


class MemoryMetadata:
    """In-memory stand-in for the evidence DynamoDB table."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}

    def get(self, tenant_id: str, evidence_id: str) -> dict[str, Any] | None:
        item = self.items.get((tenant_id, evidence_id))
        return None if item is None else dict(item)


@pytest.fixture()
def metadata(monkeypatch: pytest.MonkeyPatch) -> MemoryMetadata:
    """Replace the DynamoDB store used by the link routes."""
    memory = MemoryMetadata()
    monkeypatch.setattr("app.api.v1.finding_evidence.get_store", lambda: memory)
    return memory


def _token(
    rsa_keypair: dict[str, Any],
    tenant_id: str,
    role: str = "auditor",
    sub: str = "auditor-sub",
) -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role, sub=sub)


def _remember(
    metadata: MemoryMetadata,
    tenant_id: str,
    evidence_id: str,
    *,
    status: str = "uploaded",
    file_name: str = "gauge.pdf",
) -> None:
    metadata.items[(tenant_id, evidence_id)] = {
        "tenant_id": tenant_id,
        "evidence_id": evidence_id,
        "file_name": file_name,
        "content_type": "application/pdf",
        "file_size": 1200,
        "s3_key": f"{tenant_id}/{evidence_id}/{file_name}",
        "status": status,
        "uploaded_by": "uploader-sub",
        "uploaded_at": "2026-11-01T12:00:00+00:00",
    }


def _link(
    client: TestClient, token: str, finding_id: str, evidence_id: str
) -> Any:
    return client.post(
        f"/api/v1/findings/{finding_id}/evidence",
        json={"evidence_id": evidence_id},
        headers=_auth(token),
    )


def test_post_links_uploaded_evidence(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    metadata: MemoryMetadata,
) -> None:
    tenant_id, token, finding_id = _open_finding(client, rsa_keypair, "Link Evidence")
    evidence_id = "11111111-1111-1111-1111-111111111111"
    _remember(metadata, tenant_id, evidence_id)

    response = _link(client, token, finding_id, evidence_id)

    assert response.status_code == 201
    body = response.json()
    assert body["finding_id"] == finding_id
    assert body["evidence_id"] == evidence_id
    assert body["file_name"] == "gauge.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["file_size"] == 1200
    assert body["s3_key"] == f"{tenant_id}/{evidence_id}/gauge.pdf"
    assert body["status"] == "uploaded"
    assert body["linked_by"] == "auditor-sub"
    row = db.query(FindingEvidence).one()
    assert row.tenant_id == tenant_id
    assert row.finding_id == finding_id
    assert row.evidence_id == evidence_id
    assert "file_name" not in FindingEvidence.__table__.columns
    assert db.query(Evidence).count() == 0


def test_get_lists_finding_evidence(
    client: TestClient, rsa_keypair: dict[str, Any], metadata: MemoryMetadata
) -> None:
    tenant_id, token, finding_id = _open_finding(client, rsa_keypair, "List Evidence")
    empty = client.get(
        f"/api/v1/findings/{finding_id}/evidence",
        headers=_auth(token),
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    evidence_id = "22222222-2222-2222-2222-222222222222"
    _remember(metadata, tenant_id, evidence_id, file_name="photo.png")
    assert _link(client, token, finding_id, evidence_id).status_code == 201

    listed = client.get(
        f"/api/v1/findings/{finding_id}/evidence",
        headers=_auth(token),
    )
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["evidence_id"] == evidence_id
    assert items[0]["file_name"] == "photo.png"
    assert items[0]["finding_id"] == finding_id


def test_one_file_links_to_several_findings(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    metadata: MemoryMetadata,
) -> None:
    tenant_id, token, first_id = _open_finding(client, rsa_keypair, "Shared File")
    audit_id = _create_audit(client, token)["id"]
    second = client.post(
        f"/api/v1/audits/{audit_id}/findings",
        json={"title": "Second finding"},
        headers=_auth(token),
    )
    assert second.status_code == 201
    second_id = second.json()["id"]
    evidence_id = "33333333-3333-3333-3333-333333333333"
    _remember(metadata, tenant_id, evidence_id)

    assert _link(client, token, first_id, evidence_id).status_code == 201
    assert _link(client, token, second_id, evidence_id).status_code == 201

    rows = (
        db.query(FindingEvidence)
        .filter(FindingEvidence.evidence_id == evidence_id)
        .all()
    )
    assert {row.finding_id for row in rows} == {first_id, second_id}
    for finding_id in (first_id, second_id):
        listed = client.get(
            f"/api/v1/findings/{finding_id}/evidence",
            headers=_auth(token),
        )
        assert listed.status_code == 200
        assert [item["evidence_id"] for item in listed.json()["items"]] == [evidence_id]


def test_other_tenant_cannot_link_or_list(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    metadata: MemoryMetadata,
) -> None:
    tenant_id, token, finding_id = _open_finding(client, rsa_keypair, "Tenant A Evidence")
    evidence_id = "44444444-4444-4444-4444-444444444444"
    _remember(metadata, tenant_id, evidence_id)
    other_tenant, other_token, other_finding = _open_finding(
        client, rsa_keypair, "Tenant B Evidence"
    )
    foreign_evidence = "55555555-5555-5555-5555-555555555555"
    _remember(metadata, other_tenant, foreign_evidence)

    hidden_finding = _link(client, other_token, finding_id, evidence_id)
    assert hidden_finding.status_code == 404
    hidden_file = _link(client, token, finding_id, foreign_evidence)
    assert hidden_file.status_code == 404
    assert db.query(FindingEvidence).count() == 0

    assert _link(client, token, finding_id, evidence_id).status_code == 201
    hidden_list = client.get(
        f"/api/v1/findings/{finding_id}/evidence",
        headers=_auth(other_token),
    )
    assert hidden_list.status_code == 404
    own_list = client.get(
        f"/api/v1/findings/{finding_id}/evidence",
        headers=_auth(token),
    )
    assert own_list.status_code == 200
    assert len(own_list.json()["items"]) == 1
    assert db.query(FindingEvidence).filter(FindingEvidence.finding_id == other_finding).count() == 0


def test_pending_evidence_returns_422(
    client: TestClient, rsa_keypair: dict[str, Any], metadata: MemoryMetadata
) -> None:
    tenant_id, token, finding_id = _open_finding(client, rsa_keypair, "Pending Evidence")
    evidence_id = "66666666-6666-6666-6666-666666666666"
    _remember(metadata, tenant_id, evidence_id, status="pending")

    response = _link(client, token, finding_id, evidence_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Evidence is not uploaded yet"


def test_duplicate_link_returns_409(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    metadata: MemoryMetadata,
) -> None:
    tenant_id, token, finding_id = _open_finding(client, rsa_keypair, "Duplicate Link")
    evidence_id = "77777777-7777-7777-7777-777777777777"
    _remember(metadata, tenant_id, evidence_id)
    assert _link(client, token, finding_id, evidence_id).status_code == 201

    again = _link(client, token, finding_id, evidence_id)

    assert again.status_code == 409
    assert db.query(FindingEvidence).count() == 1


def test_any_role_of_the_tenant_can_link(
    client: TestClient, rsa_keypair: dict[str, Any], metadata: MemoryMetadata
) -> None:
    tenant_id, _auditor, finding_id = _open_finding(client, rsa_keypair, "Any Role")
    evidence_id = "88888888-8888-8888-8888-888888888888"
    _remember(metadata, tenant_id, evidence_id)
    qa_manager = _token(rsa_keypair, tenant_id, role="qa_manager", sub="qa-sub")

    response = _link(client, qa_manager, finding_id, evidence_id)

    assert response.status_code == 201
    assert response.json()["linked_by"] == "qa-sub"


def test_link_requires_a_token(
    client: TestClient, rsa_keypair: dict[str, Any]
) -> None:
    _tenant_id, _token_value, finding_id = _open_finding(
        client, rsa_keypair, "Auth Evidence"
    )
    response = client.post(
        f"/api/v1/findings/{finding_id}/evidence",
        json={"evidence_id": "99999999-9999-9999-9999-999999999999"},
    )
    assert response.status_code == 401
