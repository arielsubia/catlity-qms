import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, require_role
from app.schemas.report import (
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportReferenceResponse,
)
from app.services.normative import UnsupportedIndustry
from app.services.report_generator import (
    AuditNotCompleted,
    AuditNotFound,
    ReportBackend,
    ReportDraftInvalid,
    ReportUpstreamError,
    TenantNotFound,
    generate_report,
    get_report_backend,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/reports", tags=["reports"])

REPORT_GENERATOR_ROLES = ["auditor", "lead_auditor", "admin"]


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
