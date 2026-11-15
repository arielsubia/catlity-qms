"""Report routes: generate a draft, read the latest row, and save edits."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jose import jwk
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.main import app
from app.models.audit import Audit
from app.models.audit_report import AuditReport
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.services.normative import Passage
from app.services.report_generator import (
    ReportDraftInvalid,
    ReportUpstreamError,
    get_report_backend,
    parse_report_sections,
)
from tests.test_auth import make_token

FILE_NAME = "iso9001-context-leadership.txt"
SPANISH_DRAFT = """Resumen
La auditoría encontró una política que el personal no puede describir.

Hallazgos
Falta la política de la calidad. El archivo citado es iso9001-context-leadership.txt.

Conclusiones
La política no está disponible para el personal.

Recomendaciones
Publicar la política y explicarla al personal.
"""
RETRIEVAL_QUERY = (
    "Auditoría de línea\n" "Falta la política de la calidad El personal no puede describirla. 5.2"
)


@pytest.fixture(scope="module")
def rsa_keypair() -> dict[str, Any]:
    """RSA keypair used to sign report tokens in this module."""
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
    public_jwk["kid"] = "test-key-reports"
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
    """Records Retrieve and the harness message without calling AWS."""

    def __init__(self) -> None:
        self.retrieved: list[tuple[str, str]] = []
        self.messages: list[str] = []
        self.passages: list[Passage] = []
        self.draft = SPANISH_DRAFT
        self.fail_retrieve = False

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        self.retrieved.append((knowledge_base_id, query))
        if self.fail_retrieve:
            raise ReportUpstreamError("RetrieveFailed")
        return list(self.passages)

    def complete(self, *, user_id: str, message: str) -> str:
        self.messages.append(message)
        return self.draft


@pytest.fixture(autouse=True)
def fake_backend() -> Any:
    """Keep every test off the real Bedrock clients."""
    fake = FakeBackend()
    app.dependency_overrides[get_report_backend] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_report_backend, None)


def _token(rsa_keypair: dict[str, Any], tenant_id: str, role: str = "auditor") -> str:
    return make_token(rsa_keypair, tenant_id=tenant_id, role=role)


def _audit(
    db: Session,
    *,
    industry: str = "automotive",
    status: str = "completed",
    title: str = "Auditoría de línea",
    with_finding: bool = True,
) -> tuple[Tenant, Audit]:
    tenant = Tenant(name="Acme", industry=industry)
    db.add(tenant)
    db.flush()
    audit = Audit(tenant_id=tenant.id, title=title, status=status)
    db.add(audit)
    db.flush()
    if with_finding:
        db.add(
            Finding(
                tenant_id=tenant.id,
                audit_id=audit.id,
                title="Falta la política de la calidad",
                description="El personal no puede describirla.",
                clause_reference="5.2",
            )
        )
    db.commit()
    return tenant, audit


def _generate(
    client: TestClient,
    token: str,
    audit_id: str,
) -> Any:
    return client.post(
        "/api/v1/ai/reports/generate",
        headers={"Authorization": f"Bearer {token}"},
        json={"audit_id": audit_id},
    )


def _report(
    db: Session,
    tenant: Tenant,
    audit: Audit,
    *,
    created_at: datetime | None = None,
    resumen: str = "Resumen inicial",
) -> AuditReport:
    row = AuditReport(
        tenant_id=tenant.id,
        audit_id=audit.id,
        status="draft",
        resumen=resumen,
        hallazgos="Hallazgos iniciales",
        conclusiones="Conclusiones iniciales",
        recomendaciones="Recomendaciones iniciales",
    )
    db.add(row)
    db.commit()
    if created_at is not None:
        row.created_at = created_at
        db.commit()
    db.refresh(row)
    return row


def _sections(resumen: str = "Resumen editado") -> dict[str, str]:
    return {
        "resumen": resumen,
        "hallazgos": "Hallazgos editados",
        "conclusiones": "Conclusiones editadas",
        "recomendaciones": "Recomendaciones editadas",
    }


def test_completed_audit_returns_spanish_sections_and_stores_a_draft(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    tenant, audit = _audit(db)
    fake_backend.passages = [
        Passage(text="Leadership shows up in a quality policy.", document=FILE_NAME)
    ]

    response = _generate(client, _token(rsa_keypair, tenant.id), audit.id)

    assert response.status_code == 201
    body = response.json()
    assert body["audit_id"] == audit.id
    assert body["status"] == "draft"
    assert body["resumen"] == (
        "La auditoría encontró una política que el personal no puede describir."
    )
    assert body["hallazgos"] == (
        "Falta la política de la calidad. " "El archivo citado es iso9001-context-leadership.txt."
    )
    assert body["conclusiones"] == "La política no está disponible para el personal."
    assert body["recomendaciones"] == "Publicar la política y explicarla al personal."
    assert body["references"] == [{"document": FILE_NAME, "section": FILE_NAME}]
    assert fake_backend.retrieved[0][1] == RETRIEVAL_QUERY
    assert "quality policy" not in fake_backend.retrieved[0][1]
    assert FILE_NAME in fake_backend.messages[0]
    assert "Falta la política de la calidad" in fake_backend.messages[0]
    queried = [knowledge_base_id for knowledge_base_id, _query in fake_backend.retrieved]
    assert queried == [
        settings.normative_kb_common_id,
        settings.normative_kb_automotive_id,
    ]

    stored = db.query(AuditReport).filter(AuditReport.id == body["id"]).one()
    assert stored.tenant_id == tenant.id
    assert stored.audit_id == audit.id
    assert stored.status == "draft"
    assert stored.resumen == body["resumen"]
    assert stored.hallazgos == body["hallazgos"]
    assert stored.conclusiones == body["conclusiones"]
    assert stored.recomendaciones == body["recomendaciones"]

    again = _generate(client, _token(rsa_keypair, tenant.id, role="admin"), audit.id)
    assert again.status_code == 201
    assert again.json()["id"] != body["id"]
    assert db.query(AuditReport).count() == 2


@pytest.mark.parametrize("role", ["auditor", "lead_auditor", "admin"])
def test_report_roles_can_generate(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    role: str,
) -> None:
    tenant, audit = _audit(db)

    response = _generate(client, _token(rsa_keypair, tenant.id, role=role), audit.id)

    assert response.status_code == 201
    assert response.json()["status"] == "draft"


@pytest.mark.parametrize("role", ["qa_manager", "auditee"])
def test_other_roles_cannot_generate(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
    role: str,
) -> None:
    tenant, audit = _audit(db)

    response = _generate(client, _token(rsa_keypair, tenant.id, role=role), audit.id)

    assert response.status_code == 403
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []
    assert db.query(AuditReport).count() == 0


@pytest.mark.parametrize("status_name", ["planned", "in_progress", "closed"])
def test_only_a_completed_audit_can_generate(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
    status_name: str,
) -> None:
    tenant, audit = _audit(db, status=status_name)

    response = _generate(client, _token(rsa_keypair, tenant.id), audit.id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Only a completed audit can generate a report"
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []
    assert db.query(AuditReport).count() == 0


def test_another_tenant_audit_is_not_found(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    _owner, audit = _audit(db)
    other = Tenant(name="Other", industry="pharmaceutical")
    db.add(other)
    db.commit()

    response = _generate(client, _token(rsa_keypair, other.id), audit.id)

    assert response.status_code == 404
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []
    assert db.query(AuditReport).count() == 0


def test_unknown_industry_does_not_call_bedrock(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    tenant, audit = _audit(db, industry="food")

    response = _generate(client, _token(rsa_keypair, tenant.id), audit.id)

    assert response.status_code == 422
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []
    assert db.query(AuditReport).count() == 0


def test_upstream_failure_and_missing_sections_are_not_stored(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    tenant, audit = _audit(db)
    fake_backend.fail_retrieve = True

    failed = _generate(client, _token(rsa_keypair, tenant.id), audit.id)

    assert failed.status_code == 502
    assert db.query(AuditReport).count() == 0

    fake_backend.fail_retrieve = False
    fake_backend.draft = "Sin las cuatro secciones."
    invalid = _generate(client, _token(rsa_keypair, tenant.id), audit.id)

    assert invalid.status_code == 502
    assert invalid.json()["detail"] == "The draft did not include the four sections"
    assert db.query(AuditReport).count() == 0


def test_generate_requires_a_token_and_rejects_a_blank_audit_id(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    tenant, audit = _audit(db)

    missing = client.post(
        "/api/v1/ai/reports/generate",
        json={"audit_id": audit.id},
    )
    blank = client.post(
        "/api/v1/ai/reports/generate",
        headers={"Authorization": f"Bearer {_token(rsa_keypair, tenant.id)}"},
        json={"audit_id": "   "},
    )

    assert missing.status_code == 401
    assert blank.status_code == 422
    assert db.query(AuditReport).count() == 0


def test_parse_keeps_markdown_headings_and_the_file_name() -> None:
    sections = parse_report_sections(
        "## Resumen\n"
        "Texto.\n\n"
        "## Hallazgos:\n"
        "El archivo es iso9001-context-leadership.txt.\n\n"
        "## Conclusiones\n"
        "Cierre.\n\n"
        "## Recomendaciones\n"
        "Acción.\n"
    )

    assert sections.resumen == "Texto."
    assert sections.hallazgos == "El archivo es iso9001-context-leadership.txt."
    assert sections.conclusiones == "Cierre."
    assert sections.recomendaciones == "Acción."


def test_parse_rejects_a_missing_heading() -> None:
    with pytest.raises(ReportDraftInvalid):
        parse_report_sections("Resumen\nSolo un título.\n")


def test_latest_report_is_the_newest_row_and_does_not_call_bedrock(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
) -> None:
    tenant, audit = _audit(db)
    _report(
        db,
        tenant,
        audit,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        resumen="Nuevo",
    )
    _report(
        db,
        tenant,
        audit,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        resumen="Viejo",
    )

    response = client.get(
        "/api/v1/ai/reports",
        headers={"Authorization": f"Bearer {_token(rsa_keypair, tenant.id)}"},
        params={"audit_id": audit.id},
    )

    assert response.status_code == 200
    assert response.json()["resumen"] == "Nuevo"
    assert response.json()["status"] == "draft"
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []


def test_missing_report_is_not_found(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    tenant, audit = _audit(db)

    response = client.get(
        "/api/v1/ai/reports",
        headers={"Authorization": f"Bearer {_token(rsa_keypair, tenant.id)}"},
        params={"audit_id": audit.id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Report not found"


@pytest.mark.parametrize("role", ["auditor", "lead_auditor", "admin"])
def test_report_roles_can_read_and_update(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    fake_backend: FakeBackend,
    role: str,
) -> None:
    tenant, audit = _audit(db)
    row = _report(db, tenant, audit)
    token = _token(rsa_keypair, tenant.id, role=role)

    updated = client.patch(
        f"/api/v1/ai/reports/{row.id}",
        headers={"Authorization": f"Bearer {token}"},
        json=_sections(),
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["id"] == row.id
    assert body["status"] == "draft"
    assert body["resumen"] == "Resumen editado"
    db.refresh(row)
    assert row.resumen == "Resumen editado"
    assert row.status == "draft"
    assert fake_backend.retrieved == []
    assert fake_backend.messages == []


@pytest.mark.parametrize("role", ["qa_manager", "auditee"])
def test_other_roles_cannot_read_or_update(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
    role: str,
) -> None:
    tenant, audit = _audit(db)
    row = _report(db, tenant, audit)
    token = _token(rsa_keypair, tenant.id, role=role)

    read = client.get(
        "/api/v1/ai/reports",
        headers={"Authorization": f"Bearer {token}"},
        params={"audit_id": audit.id},
    )
    updated = client.patch(
        f"/api/v1/ai/reports/{row.id}",
        headers={"Authorization": f"Bearer {token}"},
        json=_sections(),
    )

    assert read.status_code == 403
    assert updated.status_code == 403
    db.refresh(row)
    assert row.resumen == "Resumen inicial"


def test_another_tenant_cannot_read_or_update_a_report(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    owner, audit = _audit(db)
    row = _report(db, owner, audit)
    other = Tenant(name="Other", industry="pharmaceutical")
    db.add(other)
    db.commit()
    token = _token(rsa_keypair, other.id)

    read = client.get(
        "/api/v1/ai/reports",
        headers={"Authorization": f"Bearer {token}"},
        params={"audit_id": audit.id},
    )
    updated = client.patch(
        f"/api/v1/ai/reports/{row.id}",
        headers={"Authorization": f"Bearer {token}"},
        json=_sections(),
    )

    assert read.status_code == 404
    assert read.json()["detail"] == "Audit not found"
    assert updated.status_code == 404
    assert updated.json()["detail"] == "Report not found"
    db.refresh(row)
    assert row.resumen == "Resumen inicial"


def test_patch_keeps_bold_and_rejects_an_empty_section(
    client: TestClient,
    db: Session,
    rsa_keypair: dict[str, Any],
) -> None:
    tenant, audit = _audit(db)
    row = _report(db, tenant, audit)
    token = _token(rsa_keypair, tenant.id)
    headers = {"Authorization": f"Bearer {token}"}

    emptied = client.patch(
        f"/api/v1/ai/reports/{row.id}",
        headers=headers,
        json=_sections("<script>alert(1)</script>"),
    )
    saved = client.patch(
        f"/api/v1/ai/reports/{row.id}",
        headers=headers,
        json=_sections('<b onclick="x">Listo</b>'),
    )

    assert emptied.status_code == 422
    assert "section text is required" in emptied.text
    assert saved.status_code == 200
    assert saved.json()["resumen"] == "<b>Listo</b>"
    db.refresh(row)
    assert row.resumen == "<b>Listo</b>"
    assert "<script>" not in row.resumen


def test_read_and_update_require_a_token(
    client: TestClient,
    db: Session,
) -> None:
    tenant, audit = _audit(db)
    row = _report(db, tenant, audit)

    read = client.get("/api/v1/ai/reports", params={"audit_id": audit.id})
    updated = client.patch(f"/api/v1/ai/reports/{row.id}", json=_sections())

    assert read.status_code == 401
    assert updated.status_code == 401
