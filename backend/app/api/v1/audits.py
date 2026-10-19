from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_tenant_id, require_role
from app.models.audit import Audit
from app.schemas.audit import (
    AuditCreate,
    AuditListResponse,
    AuditResponse,
    AuditStatusUpdate,
    AuditUpdate,
)

router = APIRouter(prefix="/audits", tags=["audits"])

# Creating an audit is limited to these roles. Listing and editing stay
# available to any authenticated member of the tenant.
AUDIT_CREATOR_ROLES = ["auditor", "admin", "qa_manager"]
AUDIT_STATUS_ROLES = ["auditor", "admin"]
AUDIT_TRANSITIONS = {
    "planned": "in_progress",
    "in_progress": "completed",
    "completed": "closed",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _get_tenant_audit(db: Session, audit_id: str, tenant_id: str) -> Audit:
    """Return the audit when it belongs to the caller, otherwise 404.

    A missing row and a row owned by another tenant share the same response
    so the API does not reveal that the other tenant's audit exists.
    """
    audit = (
        db.query(Audit)
        .filter(Audit.id == audit_id, Audit.tenant_id == tenant_id)
        .first()
    )
    if audit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audit not found",
        )
    return audit


@router.post("/", response_model=AuditResponse, status_code=status.HTTP_201_CREATED)
def create_audit(
    audit_in: AuditCreate,
    current_user: CurrentUser = Depends(require_role(AUDIT_CREATOR_ROLES)),
    db: Session = Depends(get_db),
) -> Audit:
    """Create an audit for the tenant in the caller's JWT.

    The new row always starts as ``planned``. The client cannot choose a
    status or assign an auditor on this route.
    """
    audit = Audit(
        tenant_id=current_user.tenant_id,
        title=audit_in.title,
        description=audit_in.description,
        audit_type=audit_in.audit_type,
        planned_date=audit_in.planned_date,
        status="planned",
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


@router.get("/", response_model=AuditListResponse)
def list_audits(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    audit_status: Annotated[str | None, Query(alias="status", max_length=50)] = None,
    audit_type: Annotated[str | None, Query(max_length=50)] = None,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> AuditListResponse:
    """List audits for the tenant claim ``custom:tenant_id``.

    ``skip`` and ``limit`` page the result. ``status`` and ``audit_type`` are
    optional read filters. They do not change an audit's state.
    """
    query = db.query(Audit).filter(Audit.tenant_id == current_tenant_id)
    if audit_status:
        query = query.filter(Audit.status == audit_status)
    if audit_type:
        query = query.filter(Audit.audit_type == audit_type)

    total = query.count()
    items = (
        query.order_by(Audit.created_at.desc(), Audit.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return AuditListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/{audit_id}", response_model=AuditResponse)
def get_audit(
    audit_id: str,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> Audit:
    """Return one audit when it belongs to the authenticated tenant."""
    return _get_tenant_audit(db, audit_id, current_tenant_id)


@router.patch("/{audit_id}", response_model=AuditResponse)
def update_audit(
    audit_id: str,
    audit_in: AuditUpdate,
    current_tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
) -> Audit:
    """Update descriptive fields of an audit in the caller's tenant.

    Status transitions and auditor assignment are not applied here.
    """
    audit = _get_tenant_audit(db, audit_id, current_tenant_id)
    update_data = audit_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(audit, field, value)
    db.commit()
    db.refresh(audit)
    return audit


@router.patch("/{audit_id}/status", response_model=AuditResponse)
def update_audit_status(
    audit_id: str,
    status_in: AuditStatusUpdate,
    current_user: CurrentUser = Depends(require_role(AUDIT_STATUS_ROLES)),
    db: Session = Depends(get_db),
) -> Audit:
    """Move an audit one step forward and record the transition time.

    Allowed path: planned, in_progress, completed, closed. Any other change
    returns 422. Only an auditor or an admin of the owning tenant can call
    this route.
    """
    audit = _get_tenant_audit(db, audit_id, current_user.tenant_id)
    allowed = AUDIT_TRANSITIONS.get(audit.status)
    if allowed != status_in.status:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot change status from {audit.status} to {status_in.status}",
        )
    audit.status = status_in.status
    audit.status_changed_at = _utcnow()
    db.commit()
    db.refresh(audit)
    return audit
