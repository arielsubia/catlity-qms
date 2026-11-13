"""Draft an audit report from local findings and the study notes.

The API loads the audit and its findings from the local database, retrieves
passages from the tenant's knowledge bases, and calls the Report Generator
harness. The harness call clears the tool list. The gateway accepts every
corpus, so the model must not be able to open it.

The study notes are English. ``retrieval_query`` is the only text sent to
Retrieve, and it is not translated. A later change can translate that string
to English without touching the harness. A Spanish finding can therefore miss
an English note. The report is still written, and the prompt tells the model
not to invent a citation for that gap.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import boto3
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import Audit
from app.models.finding import Finding
from app.models.tenant import Tenant
from app.services.normative import Passage, document_name, knowledge_base_ids_for

MAX_RETRIEVAL_QUERY_CHARS = 1000
REPORT_INSTRUCTION = (
    "You are Report Generator for Catlity QMS. "
    "Write an audit report from the findings in the user message. "
    "Use these four headings, in this order: Resumen, Hallazgos, "
    "Conclusiones, Recomendaciones. "
    "If the findings are written in Spanish, write the report in Spanish. "
    "If they are written in English, write the report in English. "
    "Cite the file name of each study note you use, exactly as it appears "
    "in the passage. Do not translate file names. "
    "The notes are original study summaries in English. "
    "They are not the official text of ISO 9001, IATF 16949, or GMP. "
    "Do not invent clause numbers or requirements. "
    "If no passage covers a finding, say so in that finding and do not fill "
    "the gap from general knowledge. "
    "A Spanish finding can miss an English note. "
    "Treat a missing passage as no citation."
)


class TenantNotFound(Exception):
    """The token tenant has no row in the local database."""


class AuditNotFound(Exception):
    """No audit with this id belongs to the tenant."""


class ReportUpstreamError(Exception):
    """Bedrock Retrieve or the report harness invocation failed."""


@dataclass(frozen=True)
class ReportReference:
    """One cited study note. The file name fills both fields."""

    document: str
    section: str


@dataclass(frozen=True)
class ReportDraft:
    text: str
    references: list[ReportReference]


class ReportBackend(Protocol):
    """The two AWS calls a draft is allowed to make."""

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        """Return passages from one knowledge base."""

    def complete(self, *, user_id: str, message: str) -> str:
        """Ask the report harness to write from the message."""


def retrieval_query(audit_title: str, findings: list[Finding]) -> str:
    """Build the Retrieve text from the audit title and its findings.

    This string is not translated. The notes are English, so a Spanish
    finding can retrieve a weaker passage. Translating this string is the
    later fix, and it stays inside this function.
    """
    parts = [audit_title.strip()]
    for finding in findings:
        bits = [finding.title, finding.description or "", finding.clause_reference or ""]
        parts.append(" ".join(bit.strip() for bit in bits if bit and bit.strip()))
    text = "\n".join(part for part in parts if part).strip()
    if not text:
        text = "audit findings"
    return text[:MAX_RETRIEVAL_QUERY_CHARS]


def reference_names(passages: list[Passage]) -> list[ReportReference]:
    """One reference per file. The file name fills document and section."""
    seen: dict[str, ReportReference] = {}
    for passage in passages:
        if passage.document not in seen:
            seen[passage.document] = ReportReference(
                document=passage.document,
                section=passage.document,
            )
    return list(seen.values())


def report_message(audit: Audit, findings: list[Finding], passages: list[Passage]) -> str:
    """User message: the audit, every finding, and the passages already chosen."""
    blocks = [f"Audit: {audit.title}", f"Status: {audit.status}"]
    if audit.description:
        blocks.append(f"Description: {audit.description}")
    finding_lines = ["Findings:"]
    if not findings:
        finding_lines.append("None.")
    for index, finding in enumerate(findings, start=1):
        clause = finding.clause_reference or "-"
        finding_lines.append(
            f"{index}. {finding.title} | type: {finding.finding_type} | "
            f"status: {finding.status} | clause: {clause}"
        )
        if finding.description:
            finding_lines.append(finding.description)
    blocks.append("\n".join(finding_lines))
    passage_lines = ["Passages:"]
    if not passages:
        passage_lines.append("None. The English study notes returned no passage for this search.")
    for passage in passages:
        passage_lines.append(f"File: {passage.document}\n{passage.text}")
    blocks.append("\n".join(passage_lines))
    return "\n\n".join(blocks)


def draft_report(
    db: Session,
    backend: ReportBackend,
    *,
    tenant_id: str,
    user_id: str,
    audit_id: str,
) -> ReportDraft:
    """Write one draft for an audit that belongs to the tenant.

    Any audit status is accepted. Restricting the call to completed audits
    belongs to the generate endpoint.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise TenantNotFound(tenant_id)

    audit = (
        db.query(Audit).filter(Audit.id == audit_id, Audit.tenant_id == tenant_id).first()
    )
    if audit is None:
        raise AuditNotFound(audit_id)

    findings = (
        db.query(Finding)
        .filter(Finding.audit_id == audit.id, Finding.tenant_id == tenant_id)
        .order_by(Finding.created_at, Finding.id)
        .all()
    )
    knowledge_base_ids = knowledge_base_ids_for(tenant.industry)
    query = retrieval_query(audit.title, findings)
    passages: list[Passage] = []
    for knowledge_base_id in knowledge_base_ids:
        passages.extend(backend.retrieve(knowledge_base_id, query))

    text = backend.complete(
        user_id=user_id,
        message=report_message(audit, findings, passages),
    )
    return ReportDraft(text=text, references=reference_names(passages))


def collect_harness_text(events: Iterable[dict[str, Any]]) -> str:
    """Join the text deltas of one harness stream."""
    parts: list[str] = []
    for event in events:
        if "contentBlockDelta" in event:
            text = event["contentBlockDelta"].get("delta", {}).get("text")
            if text:
                parts.append(text)
            continue
        for key in ("runtimeClientError", "validationException", "internalServerException"):
            if key in event:
                message = event[key].get("message", key)
                raise ReportUpstreamError(message)
    answer = "".join(parts).strip()
    if not answer:
        raise ReportUpstreamError("The harness returned an empty draft")
    return answer


class BotoReportBackend:
    """Retrieve with the agent runtime, then invoke the report harness."""

    def __init__(self, runtime: Any | None = None, harness: Any | None = None) -> None:
        self._runtime = runtime or boto3.client(
            "bedrock-agent-runtime",
            region_name=settings.aws_region,
        )
        self._harness = harness or boto3.client(
            "bedrock-agentcore",
            region_name=settings.aws_region,
        )

    def retrieve(self, knowledge_base_id: str, query: str) -> list[Passage]:
        try:
            response = self._runtime.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={
                    "vectorSearchConfiguration": {"numberOfResults": 4}
                },
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "RetrieveFailed")
            raise ReportUpstreamError(code) from exc

        passages: list[Passage] = []
        for item in response.get("retrievalResults", []):
            text = item.get("content", {}).get("text", "").strip()
            if not text:
                continue
            uri = item.get("location", {}).get("s3Location", {}).get("uri", "")
            passages.append(Passage(text=text, document=document_name(uri)))
        return passages

    def complete(self, *, user_id: str, message: str) -> str:
        try:
            response = self._harness.invoke_harness(
                harnessArn=settings.report_harness_arn,
                runtimeSessionId=str(uuid.uuid4()),
                runtimeUserId=user_id or "catlity-user",
                messages=[{"role": "user", "content": [{"text": message}]}],
                systemPrompt=[{"text": REPORT_INSTRUCTION}],
                tools=[],
                allowedTools=[],
                maxIterations=1,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "InvokeHarnessFailed")
            raise ReportUpstreamError(code) from exc
        return collect_harness_text(_stream_events(response))


def _stream_events(response: dict[str, Any]) -> Iterator[dict[str, Any]]:
    stream = response.get("stream", ())
    yield from stream


_backend: BotoReportBackend | None = None


def get_report_backend() -> BotoReportBackend:
    """FastAPI dependency. Clients are created on first use."""
    global _backend
    if _backend is None:
        _backend = BotoReportBackend()
    return _backend


# Re-exported so callers can catch the industry error without importing normative.
__all__ = [
    "AuditNotFound",
    "BotoReportBackend",
    "REPORT_INSTRUCTION",
    "ReportDraft",
    "ReportUpstreamError",
    "TenantNotFound",
    "draft_report",
    "get_report_backend",
    "retrieval_query",
]
