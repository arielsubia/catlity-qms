"""Presigned evidence upload URLs and the DynamoDB confirm step."""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.core import security
from app.core.config import settings
from app.schemas.evidence import MAX_FILE_BYTES
from app.services.evidence import (
    STORAGE_CLASS,
    UPLOAD_EXPIRES_IN,
    BotoEvidenceStore,
    ObjectHead,
)

PDF = "application/pdf"
PNG = "image/png"
JPEG = "image/jpeg"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


def _token(
    rsa_keypair: dict[str, Any],
    *,
    tenant_id: str | None = "tenant-001",
    role: str = "auditee",
    sub: str = "user-sub-123",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": sub,
        "email": "user@example.com",
        "aud": "test-client-id",
        "iss": settings.cognito_issuer,
        "iat": now,
        "exp": now + 3600,
        "custom:role": role,
    }
    if tenant_id is not None:
        claims["custom:tenant_id"] = tenant_id
    return jwt.encode(
        claims,
        rsa_keypair["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_keypair["public_jwk"]["kid"]},
    )


class MemoryStore:
    """In-memory stand-in for S3 and DynamoDB."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], dict[str, Any]] = {}
        self.objects: dict[str, ObjectHead] = {}
        self.signed: list[dict[str, Any]] = []

    def put_pending(self, item: dict[str, Any]) -> None:
        self.items[(item["tenant_id"], item["evidence_id"])] = dict(item)

    def get(self, tenant_id: str, evidence_id: str) -> dict[str, Any] | None:
        item = self.items.get((tenant_id, evidence_id))
        return None if item is None else dict(item)

    def mark_uploaded(
        self, tenant_id: str, evidence_id: str, uploaded_at: str
    ) -> dict[str, Any]:
        item = self.items[(tenant_id, evidence_id)]
        item["status"] = "uploaded"
        item["uploaded_at"] = uploaded_at
        return dict(item)

    def presign_put(self, *, key: str, content_type: str, file_size: int) -> str:
        self.signed.append(
            {"key": key, "content_type": content_type, "file_size": file_size}
        )
        return f"https://signed.example/{key}"

    def head(self, key: str) -> ObjectHead | None:
        return self.objects.get(key)


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    """Replace the AWS store for the duration of one test."""
    memory = MemoryStore()
    monkeypatch.setattr("app.api.v1.evidence.get_store", lambda: memory)
    return memory


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_upload_url_requires_a_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/evidence/upload-url",
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 12},
    )
    assert response.status_code == 401


def test_upload_url_requires_a_tenant(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair, tenant_id=None)
    response = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 12},
    )
    assert response.status_code == 403
    assert store.items == {}


@pytest.mark.parametrize(
    ("file_name", "content_type"),
    [
        ("note.pdf", PDF),
        ("photo.png", PNG),
        ("photo.jpg", JPEG),
        ("photo.jpeg", JPEG),
        ("clause.docx", DOCX),
    ],
)
def test_upload_url_signs_an_accepted_file(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    store: MemoryStore,
    file_name: str,
    content_type: str,
) -> None:
    token = _token(rsa_keypair, role="auditee", sub="auditee-1")
    response = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": file_name, "content_type": content_type, "file_size": 128},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["expires_in"] == UPLOAD_EXPIRES_IN
    assert body["headers"]["Content-Type"] == content_type
    assert body["headers"]["Content-Length"] == "128"
    assert body["headers"]["x-amz-storage-class"] == STORAGE_CLASS
    assert body["s3_key"] == f"tenant-001/{body['evidence_id']}/{file_name}"
    assert body["upload_url"] == f"https://signed.example/{body['s3_key']}"
    saved = store.items[("tenant-001", body["evidence_id"])]
    assert saved["status"] == "pending"
    assert saved["uploaded_by"] == "auditee-1"
    assert store.signed == [
        {"key": body["s3_key"], "content_type": content_type, "file_size": 128}
    ]


def test_upload_url_accepts_the_25_mb_limit(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair)
    response = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": MAX_FILE_BYTES},
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "payload",
    [
        {"file_name": "note.pdf", "content_type": PDF, "file_size": MAX_FILE_BYTES + 1},
        {"file_name": "note.pdf", "content_type": "text/plain", "file_size": 12},
        {"file_name": "note.exe", "content_type": PDF, "file_size": 12},
        {"file_name": "nested/note.pdf", "content_type": PDF, "file_size": 12},
        {"file_name": "note.pdf", "content_type": PDF, "file_size": 0},
    ],
)
def test_upload_url_rejects_invalid_files(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    store: MemoryStore,
    payload: dict[str, Any],
) -> None:
    token = _token(rsa_keypair)
    response = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 422
    assert store.items == {}


def test_confirm_records_metadata_after_the_object_is_present(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair, sub="auditor-9", role="auditor")
    created = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 20},
    )
    body = created.json()
    store.objects[body["s3_key"]] = ObjectHead(content_type=PDF, content_length=20)

    confirmed = client.post(
        f"/api/v1/evidence/{body['evidence_id']}/confirm",
        headers=_auth(token),
    )
    assert confirmed.status_code == 200
    metadata = confirmed.json()
    assert metadata["status"] == "uploaded"
    assert metadata["tenant_id"] == "tenant-001"
    assert metadata["file_size"] == 20
    assert metadata["uploaded_by"] == "auditor-9"
    assert metadata["uploaded_at"]


def test_confirm_is_idempotent_when_already_uploaded(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair)
    created = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 20},
    )
    evidence_id = created.json()["evidence_id"]
    store.objects[created.json()["s3_key"]] = ObjectHead(content_type=PDF, content_length=20)
    first = client.post(f"/api/v1/evidence/{evidence_id}/confirm", headers=_auth(token))
    second = client.post(f"/api/v1/evidence/{evidence_id}/confirm", headers=_auth(token))
    assert second.status_code == 200
    assert second.json()["uploaded_at"] == first.json()["uploaded_at"]


def test_confirm_waits_until_the_object_exists(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair)
    created = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 20},
    )
    response = client.post(
        f"/api/v1/evidence/{created.json()['evidence_id']}/confirm",
        headers=_auth(token),
    )
    assert response.status_code == 409


def test_confirm_rejects_an_object_that_does_not_match_the_signature(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    token = _token(rsa_keypair)
    created = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(token),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 20},
    )
    store.objects[created.json()["s3_key"]] = ObjectHead(content_type=PDF, content_length=21)
    response = client.post(
        f"/api/v1/evidence/{created.json()['evidence_id']}/confirm",
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_confirm_hides_another_tenants_upload(
    client: TestClient, rsa_keypair: dict[str, Any], store: MemoryStore
) -> None:
    owner = _token(rsa_keypair, tenant_id="tenant-a")
    other = _token(rsa_keypair, tenant_id="tenant-b")
    created = client.post(
        "/api/v1/evidence/upload-url",
        headers=_auth(owner),
        json={"file_name": "note.pdf", "content_type": PDF, "file_size": 20},
    )
    response = client.post(
        f"/api/v1/evidence/{created.json()['evidence_id']}/confirm",
        headers=_auth(other),
    )
    assert response.status_code == 404


def test_presign_requests_a_15_minute_intelligent_tiering_put() -> None:
    class RecordingS3:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
            self.calls.append({"operation": operation, **kwargs})
            return "https://bucket.example/signed"

    s3 = RecordingS3()
    store = BotoEvidenceStore(
        bucket="catlity-qms-dev-evidence",
        table="catlity-qms-dev-evidence",
        region="us-east-1",
        s3_client=s3,
        dynamodb_client=object(),
    )
    url = store.presign_put(key="tenant/id/note.pdf", content_type=PDF, file_size=40)
    assert url == "https://bucket.example/signed"
    assert s3.calls == [
        {
            "operation": "put_object",
            "Params": {
                "Bucket": "catlity-qms-dev-evidence",
                "Key": "tenant/id/note.pdf",
                "ContentType": PDF,
                "ContentLength": 40,
                "StorageClass": STORAGE_CLASS,
            },
            "ExpiresIn": UPLOAD_EXPIRES_IN,
        }
    ]
