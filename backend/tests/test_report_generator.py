"""Report drafts: tenant findings, industry knowledge bases, and the harness call."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import Audit
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.services.normative import Passage, UnsupportedIndustry
from app.services.report_generator import (
    REPORT_INSTRUCTION,
    AuditNotFound,
    BotoReportBackend,
    ReportUpstreamError,
    TenantNotFound,
    draft_report,
    retrieval_query,
)

COMMON = "s3://catlity-qms-dev-knowledge-base/knowledge-base/common/iso9001-context-leadership.txt"
REPORT_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:265751834002:harness/Report_Generator-test"
)


@pytest.fixture(autouse=True)
def report_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "report_harness_arn", REPORT_ARN, raising=False)


class FakeBackend:
    """Records Retrieve and the harness message without calling AWS."""

    def __init__(self) -> None:
        self.retrieved: list[tuple[str, str]] = []
        self.messages: list[str] = []
        self.passages: list[Passage] = []
        self.draft = "Resumen\nSin hallazgos."
        self.fail_retrieve = False

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        self.retrieved.append((knowledge_base_id, query))
        if self.fail_retrieve:
            raise ReportUpstreamError("RetrieveFailed")
        return list(self.passages)

    def complete(self, *, user_id: str, message: str) -> str:
        self.messages.append(message)
        return self.draft


def _tenant(db: Session, industry: str, name: str = "Acme") -> Tenant:
    tenant = Tenant(name=name, industry=industry)
    db.add(tenant)
    db.flush()
    return tenant


def _audit(db: Session, tenant: Tenant, title: str, status: str = "planned") -> Audit:
    audit = Audit(tenant_id=tenant.id, title=title, status=status)
    db.add(audit)
    db.flush()
    return audit


def _finding(
    db: Session,
    tenant: Tenant,
    audit: Audit,
    title: str,
    description: str | None = None,
    clause_reference: str | None = None,
) -> Finding:
    finding = Finding(
        tenant_id=tenant.id,
        audit_id=audit.id,
        title=title,
        description=description,
        clause_reference=clause_reference,
    )
    db.add(finding)
    db.flush()
    return finding


def test_draft_reads_only_that_audit_and_the_tenant_corpora(db: Session) -> None:
    tenant = _tenant(db, "automotive")
    other = _tenant(db, "pharmaceutical", name="Other")
    audit = _audit(db, tenant, "Auditoría de línea")
    other_audit = _audit(db, tenant, "Otra auditoría")
    _finding(
        db,
        tenant,
        audit,
        "Falta la política de la calidad",
        description="El personal no puede describirla.",
        clause_reference="5.2",
    )
    _finding(db, tenant, other_audit, "Hallazgo de otra auditoría")
    _finding(db, other, _audit(db, other, "Auditoría ajena"), "Hallazgo ajeno")
    backend = FakeBackend()
    backend.passages = [
        Passage(text="Leadership shows up in a quality policy.", document="iso9001-context-leadership.txt")
    ]

    draft = draft_report(
        db,
        backend,
        tenant_id=tenant.id,
        user_id="user-1",
        audit_id=audit.id,
    )

    assert draft.text == "Resumen\nSin hallazgos."
    assert draft.references[0].document == "iso9001-context-leadership.txt"
    assert draft.references[0].section == "iso9001-context-leadership.txt"
    queried = [knowledge_base_id for knowledge_base_id, _query in backend.retrieved]
    assert queried == [
        settings.normative_kb_common_id,
        settings.normative_kb_automotive_id,
    ]
    query = backend.retrieved[0][1]
    assert "Falta la política de la calidad" in query
    assert "Hallazgo de otra auditoría" not in query
    assert "Hallazgo ajeno" not in query
    message = backend.messages[0]
    assert "Falta la política de la calidad" in message
    assert "iso9001-context-leadership.txt" in message
    assert "Hallazgo de otra auditoría" not in message
    assert "Status: planned" in message


def test_spanish_finding_is_sent_to_retrieve_without_translation(db: Session) -> None:
    tenant = _tenant(db, "pharmaceutical")
    audit = _audit(db, tenant, "Auditoría GMP")
    _finding(db, tenant, audit, "Falta el registro de limpieza")
    backend = FakeBackend()

    draft_report(db, backend, tenant_id=tenant.id, user_id="user-1", audit_id=audit.id)

    query = backend.retrieved[0][1]
    assert query == "Auditoría GMP\nFalta el registro de limpieza"
    assert settings.normative_kb_pharmaceutical_id in [
        knowledge_base_id for knowledge_base_id, _query in backend.retrieved
    ]


def test_empty_passages_still_call_the_harness(db: Session) -> None:
    tenant = _tenant(db, "automotive")
    audit = _audit(db, tenant, "Line audit", status="in_progress")
    backend = FakeBackend()

    draft = draft_report(
        db, backend, tenant_id=tenant.id, user_id="user-1", audit_id=audit.id
    )

    assert draft.references == []
    assert "None. The English study notes returned no passage" in backend.messages[0]
    assert "Findings:\nNone." in backend.messages[0]


def test_missing_audit_and_unknown_industry(db: Session) -> None:
    tenant = _tenant(db, "food")
    other = _tenant(db, "automotive", name="Plant")
    audit = _audit(db, other, "Plant audit")
    backend = FakeBackend()

    with pytest.raises(AuditNotFound):
        draft_report(
            db, backend, tenant_id=tenant.id, user_id="user-1", audit_id=audit.id
        )
    with pytest.raises(TenantNotFound):
        draft_report(
            db, backend, tenant_id="missing-tenant", user_id="user-1", audit_id=audit.id
        )

    owned = _audit(db, tenant, "Food audit")
    with pytest.raises(UnsupportedIndustry):
        draft_report(
            db, backend, tenant_id=tenant.id, user_id="user-1", audit_id=owned.id
        )
    assert backend.retrieved == []
    assert backend.messages == []


def test_retrieval_query_keeps_the_first_thousand_characters() -> None:
    audit_title = "Alcance"
    finding = Finding(
        tenant_id="t",
        audit_id="a",
        title="Título",
        description="á" * 1200,
        clause_reference="4.1",
    )

    query = retrieval_query(audit_title, [finding])

    assert len(query) == 1000
    assert query.startswith("Alcance\nTítulo")
    assert "4.1" not in query


def test_instruction_asks_for_spanish_sections_and_original_file_names() -> None:
    assert "Resumen, Hallazgos, Conclusiones, Recomendaciones" in REPORT_INSTRUCTION
    assert "write the report in Spanish" in REPORT_INSTRUCTION
    assert "Do not translate file names." in REPORT_INSTRUCTION
    assert "A Spanish finding can miss an English note." in REPORT_INSTRUCTION


def test_harness_call_clears_the_tool_list() -> None:
    harness = MagicMock()
    harness.invoke_harness.return_value = {
        "stream": [
            {"contentBlockDelta": {"delta": {"text": "Resumen\n"}}},
            {"contentBlockDelta": {"delta": {"text": "La política no está descrita."}}},
        ]
    }
    backend = BotoReportBackend(runtime=MagicMock(), harness=harness)

    draft = backend.complete(user_id="user-1", message="Audit: Línea")

    assert draft == "Resumen\nLa política no está descrita."
    kwargs = harness.invoke_harness.call_args.kwargs
    assert kwargs["harnessArn"] == REPORT_ARN
    assert kwargs["tools"] == []
    assert kwargs["allowedTools"] == []
    assert kwargs["maxIterations"] == 1
    assert kwargs["systemPrompt"] == [{"text": REPORT_INSTRUCTION}]
    assert len(kwargs["runtimeSessionId"]) >= 33


def test_retrieve_failure_is_an_upstream_error() -> None:
    runtime = MagicMock()
    runtime.retrieve.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
        "Retrieve",
    )
    backend = BotoReportBackend(runtime=runtime, harness=MagicMock())

    with pytest.raises(ReportUpstreamError):
        backend.retrieve(settings.normative_kb_common_id, "política de la calidad")
