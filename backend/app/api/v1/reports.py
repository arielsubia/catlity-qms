import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, require_role
from app.models.audit_report import AuditReport
from app.schemas.report import (
    ReportDraftResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportReferenceResponse,
    ReportUpdateRequest,
)
from app.services.normative import UnsupportedIndustry
from app.services.report_generator import (
    AuditNotCompleted,
    AuditNotFound,
    ReportBackend,
    ReportDraftInvalid,
    ReportNotFound,
    ReportSections,
    ReportUpstreamError,
    TenantNotFound,
    generate_report,
    get_report_backend,
    latest_report,
    update_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/reports", tags=["reports"])

REPORT_GENERATOR_ROLES = ["auditor", "lead_auditor", "admin"]


def _required_audit_id(
    audit_id: Annotated[str, Query(min_length=1, max_length=36)],
) -> str:
    stripped = audit_id.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="audit_id is required",
        )
    return stripped


def _draft_response(row: AuditReport) -> ReportDraftResponse:
    return ReportDraftResponse(
        id=row.id,
        audit_id=row.audit_id,
        status=row.status,
        resumen=row.resumen,
        hallazgos=row.hallazgos,
        conclusiones=row.conclusiones,
        recomendaciones=row.recomendaciones,
    )


@router.get("", response_model=ReportDraftResponse)
def read_latest_report(
    audit_id: Annotated[str, Depends(_required_audit_id)],
    current_user: CurrentUser = Depends(require_role(REPORT_GENERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ReportDraftResponse:
    """Return the newest local draft for one audit. This does not call Bedrock."""
    try:
        row = latest_report(db, tenant_id=current_user.tenant_id, audit_id=audit_id)
    except AuditNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found",
        ) from exc
    except ReportNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        ) from exc
    return _draft_response(row)


@router.patch("/{report_id}", response_model=ReportDraftResponse)
def patch_report(
    report_id: Annotated[str, Path(min_length=1, max_length=36)],
    body: ReportUpdateRequest,
    current_user: CurrentUser = Depends(require_role(REPORT_GENERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ReportDraftResponse:
    """Replace the four sections of a draft. This does not call Bedrock."""
    try:
        row = update_report(
            db,
            tenant_id=current_user.tenant_id,
            report_id=report_id,
            sections=ReportSections(
                resumen=body.resumen,
                hallazgos=body.hallazgos,
                conclusiones=body.conclusiones,
                recomendaciones=body.recomendaciones,
            ),
        )
    except ReportNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        ) from exc
    db.commit()
    return _draft_response(row)


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_audit_report(
    body: ReportGenerateRequest,
    current_user: CurrentUser = Depends(require_role(REPORT_GENERATOR_ROLES)),
    db: Session = Depends(get_db),
    backend: ReportBackend = Depends(get_report_backend),
) -> ReportGenerateResponse:
    """Draft a report for a completed audit and store it locally."""
    try:
        result = generate_report(
            db,
            backend,
            tenant_id=current_user.tenant_id,
            user_id=current_user.sub,
            audit_id=body.audit_id,
        )
    except TenantNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        ) from exc
    except AuditNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found",
        ) from exc
    except UnsupportedIndustry as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tenant industry must be automotive or pharmaceutical",
        ) from exc
    except AuditNotCompleted as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only a completed audit can generate a report",
        ) from exc
    except ReportDraftInvalid as exc:
        logger.warning("report draft missing sections: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The draft did not include the four sections",
        ) from exc
    except ReportUpstreamError as exc:
        logger.warning("report generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Report generation failed",
        ) from exc

    db.commit()
    return ReportGenerateResponse(
        id=result.id,
        audit_id=result.audit_id,
        status="draft",
        resumen=result.resumen,
        hallazgos=result.hallazgos,
        conclusiones=result.conclusiones,
        recomendaciones=result.recomendaciones,
        references=[
            ReportReferenceResponse(document=item.document, section=item.section)
            for item in result.references
        ],
    )
