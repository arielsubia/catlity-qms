"""Embed URL route: registered Reader, 15-minute session, admin and qa_manager."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from jose import jwk, jwt

from app.core import security
from app.core.config import settings
from app.main import app
from app.services.quicksight_embed import get_quicksight_client

EMBED_URL = "https://quicksight.aws.amazon.com/embed/example"
READER_ARN = "arn:aws:quicksight:us-east-1:265751834002:user/default/user@example.com"


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign test tokens."""
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
def configure_quicksight(rsa_keypair: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Point settings at a fake pool and the unapplied dashboard ids."""
    monkeypatch.setattr(settings, "cognito_user_pool_id", "us-east-1_test", raising=False)
    monkeypatch.setattr(settings, "cognito_app_client_id", "test-client-id", raising=False)
    monkeypatch.setattr(settings, "aws_region", "us-east-1", raising=False)
    monkeypatch.setattr(settings, "quicksight_aws_account_id", "265751834002", raising=False)
    monkeypatch.setattr(settings, "quicksight_dashboard_id", "catlity-qms-dev-kpis", raising=False)
    monkeypatch.setattr(settings, "quicksight_namespace", "default", raising=False)
    monkeypatch.setattr(settings, "app_public_url", "http://localhost:5173", raising=False)
    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


@pytest.fixture
def quicksight_client(client: TestClient) -> MagicMock:
    """Keep the route off the real QuickSight API."""
    fake = MagicMock()
    fake.generate_embed_url_for_registered_user.return_value = {
        "EmbedUrl": EMBED_URL,
        "Status": 200,
    }
    app.dependency_overrides[get_quicksight_client] = lambda: fake
    return fake


def _token(
    rsa_keypair: dict[str, Any],
    *,
    role: str = "admin",
    email: str | None = "user@example.com",
) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-sub-123",
        "aud": "test-client-id",
        "iss": settings.cognito_issuer,
        "iat": now,
        "exp": now + 3600,
        "custom:role": role,
        "custom:tenant_id": "tenant-001",
    }
    if email is not None:
        claims["email"] = email
    return jwt.encode(
        claims,
        rsa_keypair["private_pem"],
        algorithm="RS256",
        headers={"kid": rsa_keypair["public_jwk"]["kid"]},
    )


def _get(client: TestClient, token: str) -> Any:
    return client.get(
        "/api/v1/quicksight/embed-url",
        headers={"Authorization": f"Bearer {token}"},
    )


def test_admin_receives_a_temporary_embed_url(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
) -> None:
    response = _get(client, _token(rsa_keypair, role="admin"))

    assert response.status_code == 200
    body = response.json()
    assert body["embed_url"] == EMBED_URL
    remaining = datetime.fromisoformat(body["expires_at"]) - datetime.now(UTC)
    assert timedelta(minutes=14) < remaining < timedelta(minutes=16)
    kwargs = quicksight_client.generate_embed_url_for_registered_user.call_args.kwargs
    assert kwargs == {
        "AwsAccountId": "265751834002",
        "UserArn": READER_ARN,
        "SessionLifetimeInMinutes": 15,
        "ExperienceConfiguration": {
            "Dashboard": {"InitialDashboardId": "catlity-qms-dev-kpis"},
        },
        "AllowedDomains": ["http://localhost:5173"],
    }


def test_qa_manager_receives_a_temporary_embed_url(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
) -> None:
    response = _get(client, _token(rsa_keypair, role="qa_manager"))

    assert response.status_code == 200
    assert response.json()["embed_url"] == EMBED_URL


@pytest.mark.parametrize("role", ["auditor", "lead_auditor", "auditee"])
def test_other_roles_cannot_request_an_embed_url(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
    role: str,
) -> None:
    response = _get(client, _token(rsa_keypair, role=role))

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient role for this operation"
    quicksight_client.generate_embed_url_for_registered_user.assert_not_called()


def test_missing_reader_returns_unavailable(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
) -> None:
    quicksight_client.generate_embed_url_for_registered_user.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "not found"}},
        "GenerateEmbedUrlForRegisteredUser",
    )

    response = _get(client, _token(rsa_keypair))

    assert response.status_code == 503
    assert response.json()["detail"] == "Dashboard is not available yet."


def test_blank_embed_url_returns_unavailable(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
) -> None:
    quicksight_client.generate_embed_url_for_registered_user.return_value = {"Status": 200}

    response = _get(client, _token(rsa_keypair))

    assert response.status_code == 503
    assert response.json()["detail"] == "Dashboard is not available yet."


def test_missing_email_does_not_call_quicksight(
    client: TestClient,
    rsa_keypair: dict[str, Any],
    quicksight_client: MagicMock,
) -> None:
    response = _get(client, _token(rsa_keypair, email=None))

    assert response.status_code == 503
    assert response.json()["detail"] == "Dashboard is not available yet."
    quicksight_client.generate_embed_url_for_registered_user.assert_not_called()
