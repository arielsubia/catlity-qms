"""Normative query route: industry isolation, citations, and the per-user limit."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient
from jose import jwk, jwt
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.main import app
from app.models.tenant import Tenant
from app.schemas.normative import MAX_QUESTION_LENGTH
from app.services.normative import (
    BotoNormativeBackend,
    NormativeUpstreamError,
    Passage,
    collect_harness_text,
    get_normative_backend,
    rate_limiter,
)

COMMON = "s3://catlity-qms-dev-knowledge-base/knowledge-base/common/iso9001-context-leadership.txt"
QUESTION = "What does the auditor look for in a quality policy?"


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
def configure_cognito(rsa_keypair: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Point settings at a fake pool and preload the JWKS cache."""
    monkeypatch.setattr(settings, "cognito_user_pool_id", "us-east-1_test", raising=False)
    monkeypatch.setattr(settings, "cognito_app_client_id", "test-client-id", raising=False)
    monkeypatch.setattr(settings, "aws_region", "us-east-1", raising=False)
    kid = rsa_keypair["public_jwk"]["kid"]
    security._jwks_cache._keys = {kid: rsa_keypair["public_jwk"]}
    security._jwks_cache._fetched_at = time.monotonic()


class FakeBackend:
    """Records which knowledge bases a query tried to read."""

    def __init__(self) -> None:
        self.retrieved: list[str] = []
        self.invocations: list[str] = []
        self.by_kb: dict[str, list[Passage]] = {}
        self.answer = "The auditor looks for a quality policy people can describe."
        self.fail = False

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        if self.fail:
            raise NormativeUpstreamError("retrieve failed")
        self.retrieved.append(knowledge_base_id)
        return list(self.by_kb.get(knowledge_base_id, []))

    def complete(self, *, user_id: str, question: str, passages: list[Passage]) -> str:
        self.invocations.append(user_id)
        return self.answer


@pytest.fixture(autouse=True)
def fake_backend() -> Any:
    """Keep every test off the real Bedrock clients."""
    fake = FakeBackend()
    app.dependency_overrides[get_normative_backend] = lambda: fake
    rate_limiter.reset()
    yield fake
    app.dependency_overrides.pop(get_normative_backend, None)
    rate_limiter.reset()


def _token(
    rsa_keypair: dict[str, Any],
    *,
    tenant_id: str | None = "tenant-001",
    role: str = "auditor",
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


def _tenant(db: Session, industry: str, tenant_id: str = "tenant-001") -> None:
    db.add(Tenant(id=tenant_id, name="Acme", industry=industry))
    db.commit()


def _ask(
    client: TestClient,
    token: str,
    question: str = QUESTION,
) -> Any:
    return client.post(
        "/api/v1/ai/normative/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": question},
    )


def _with_notes(fake_backend: FakeBackend, *knowledge_base_ids: str) -> None:
    for knowledge_base_id in knowledge_base_ids:
        fake_backend.by_kb[knowledge_base_id] = [
            Passage(text="Leadership shows up in a quality policy.", document="note.txt"),
        ]


def test_query_requires_a_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/ai/normative/query",
        json={"question": QUESTION},
    )
    assert response.status_code == 401


def test_query_returns_answer_and_file_references(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "automotive")
    fake_backend.by_kb[settings.normative_kb_common_id] = [
        Passage(
            text="Leadership shows up in a quality policy.",
            document="iso9001-context-leadership.txt",
        ),
        Passage(
            text="The policy is available as documented information.",
            document="iso9001-context-leadership.txt",
        ),
    ]
    fake_backend.by_kb[settings.normative_kb_automotive_id] = [
        Passage(
            text="Internal audits sample the process owner.",
            document="iatf16949-internal-audit.txt",
        ),
    ]

    response = _ask(client, _token(rsa_keypair, role="auditee"))

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == fake_backend.answer
    assert body["references"] == [
        {
            "document": "iso9001-context-leadership.txt",
            "section": "iso9001-context-leadership.txt",
        },
        {
            "document": "iatf16949-internal-audit.txt",
            "section": "iatf16949-internal-audit.txt",
        },
    ]


def test_automotive_tenant_does_not_read_pharmaceutical_notes(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "Automotive")
    _with_notes(
        fake_backend,
        settings.normative_kb_common_id,
        settings.normative_kb_automotive_id,
    )

    response = _ask(client, _token(rsa_keypair))

    assert response.status_code == 200
    assert fake_backend.retrieved == [
        settings.normative_kb_common_id,
        settings.normative_kb_automotive_id,
    ]
    assert settings.normative_kb_pharmaceutical_id not in fake_backend.retrieved


def test_pharmaceutical_tenant_does_not_read_automotive_notes(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "pharmaceutical")
    _with_notes(
        fake_backend,
        settings.normative_kb_common_id,
        settings.normative_kb_pharmaceutical_id,
    )

    response = _ask(client, _token(rsa_keypair))

    assert response.status_code == 200
    assert fake_backend.retrieved == [
        settings.normative_kb_common_id,
        settings.normative_kb_pharmaceutical_id,
    ]
    assert settings.normative_kb_automotive_id not in fake_backend.retrieved


def test_empty_retrieve_skips_the_harness(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "automotive")

    response = _ask(client, _token(rsa_keypair))

    assert response.status_code == 200
    assert response.json() == {
        "answer": "The study notes do not cover this question.",
        "references": [],
    }
    assert fake_backend.invocations == []


def test_eleventh_query_in_a_minute_is_rejected(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "automotive")
    _with_notes(
        fake_backend,
        settings.normative_kb_common_id,
        settings.normative_kb_automotive_id,
    )
    token = _token(rsa_keypair, sub="user-a")

    statuses = [_ask(client, token).status_code for _ in range(10)]
    limited = _ask(client, token)
    other = _ask(client, _token(rsa_keypair, sub="user-b"))

    assert statuses == [200] * 10
    assert limited.status_code == 429
    assert other.status_code == 200
    assert len(fake_backend.retrieved) == 22


def test_missing_tenant_returns_404(
    client: TestClient,
    rsa_keypair: dict[str, Any],
) -> None:
    response = _ask(client, _token(rsa_keypair))
    assert response.status_code == 404


def test_unknown_industry_returns_422(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    _tenant(db, "food")
    response = _ask(client, _token(rsa_keypair))
    assert response.status_code == 422


def test_blank_question_returns_422(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    _tenant(db, "automotive")
    response = _ask(client, _token(rsa_keypair), question="   ")
    assert response.status_code == 422


def test_long_question_returns_422(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    _tenant(db, "automotive")
    response = _ask(client, _token(rsa_keypair), question="a" * (MAX_QUESTION_LENGTH + 1))
    assert response.status_code == 422


def test_upstream_failure_returns_502(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _tenant(db, "automotive")
    fake_backend.fail = True
    response = _ask(client, _token(rsa_keypair))
    assert response.status_code == 502


def test_retrieve_uses_the_file_name_from_the_uri() -> None:
    runtime = MagicMock()
    runtime.retrieve.return_value = {
        "retrievalResults": [
            {
                "content": {"text": "Leadership shows up in a quality policy."},
                "location": {"s3Location": {"uri": COMMON}},
            },
            {
                "content": {"text": "   "},
                "location": {
                    "s3Location": {
                        "uri": (
                            "s3://catlity-qms-dev-knowledge-base/knowledge-base/"
                            "automotive/iatf16949-internal-audit.txt"
                        )
                    }
                },
            },
        ]
    }
    backend = BotoNormativeBackend(runtime=runtime, harness=MagicMock())

    passages = backend.retrieve(settings.normative_kb_common_id, QUESTION)

    assert passages == [
        Passage(
            text="Leadership shows up in a quality policy.",
            document="iso9001-context-leadership.txt",
        )
    ]
    assert runtime.retrieve.call_args.kwargs["knowledgeBaseId"] == settings.normative_kb_common_id
    assert (
        runtime.retrieve.call_args.kwargs["retrievalConfiguration"]["vectorSearchConfiguration"][
            "numberOfResults"
        ]
        == 4
    )


def test_retrieve_failure_is_an_upstream_error() -> None:
    runtime = MagicMock()
    runtime.retrieve.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
        "Retrieve",
    )
    backend = BotoNormativeBackend(runtime=runtime, harness=MagicMock())

    with pytest.raises(NormativeUpstreamError):
        backend.retrieve(settings.normative_kb_common_id, QUESTION)


def test_harness_call_clears_the_tool_list() -> None:
    harness = MagicMock()
    harness.invoke_harness.return_value = {
        "stream": [
            {"contentBlockDelta": {"delta": {"text": "A quality policy "}}},
            {"contentBlockDelta": {"delta": {"text": "is documented."}}},
        ]
    }
    backend = BotoNormativeBackend(runtime=MagicMock(), harness=harness)
    passages = [
        Passage(text="The policy is documented.", document="iso9001-context-leadership.txt")
    ]

    answer = backend.complete(user_id="user-1", question=QUESTION, passages=passages)

    assert answer == "A quality policy is documented."
    kwargs = harness.invoke_harness.call_args.kwargs
    assert kwargs["harnessArn"] == settings.normative_harness_arn
    assert kwargs["tools"] == []
    assert kwargs["allowedTools"] == []
    assert kwargs["maxIterations"] == 1
    assert len(kwargs["runtimeSessionId"]) >= 33
    message = kwargs["messages"][0]["content"][0]["text"]
    assert "iso9001-context-leadership.txt" in message
    assert QUESTION in message


def test_harness_stream_error_is_an_upstream_error() -> None:
    with pytest.raises(NormativeUpstreamError):
        collect_harness_text([{"validationException": {"message": "bad request"}}])
