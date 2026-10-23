from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Query as SqlQuery
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user, require_role
from app.models.audit import Audit
from app.models.finding import Finding
from app.schemas.finding import (
    FindingCreate,
    FindingListResponse,
    FindingResponse,
    FindingType,
    FindingUpdate,
)

router = APIRouter(tags=["findings"])

# The QA manager and the auditee consult findings and do not record them.
FINDING_EDITOR_ROLES = ["auditor", "admin", "lead_auditor"]


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


def _get_tenant_finding(db: Session, finding_id: str, tenant_id: str) -> Finding:
    """Return the finding when it belongs to the caller, otherwise 404."""
    finding = (
        db.query(Finding)
        .filter(Finding.id == finding_id, Finding.tenant_id == tenant_id)
        .first()
    )
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )
    return finding


def _page_findings(query: SqlQuery, skip: int, limit: int) -> FindingListResponse:
    """Return one page of an already tenant-scoped finding query."""
    total = query.count()
    items = (
        query.order_by(Finding.created_at.desc(), Finding.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return FindingListResponse(items=items, total=total, skip=skip, limit=limit)


@router.post(
    "/audits/{audit_id}/findings",
    response_model=FindingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_finding(
    audit_id: str,
    finding_in: FindingCreate,
    current_user: CurrentUser = Depends(require_role(FINDING_EDITOR_ROLES)),
    db: Session = Depends(get_db),
) -> Finding:
    """Create a finding on an audit that belongs to the caller's tenant.

    The new row always starts as ``open`` with no assignee. The client
    cannot choose a status on this route.
    """
    _get_tenant_audit(db, audit_id, current_user.tenant_id)
    finding = Finding(
        tenant_id=current_user.tenant_id,
        audit_id=audit_id,
        title=finding_in.title,
        description=finding_in.description,
        finding_type=finding_in.finding_type,
        severity=finding_in.severity,
        clause_reference=finding_in.clause_reference,
        status="open",
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


@router.get(
    "/audits/{audit_id}/findings",
    response_model=FindingListResponse,
)
def list_audit_findings(
    audit_id: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FindingListResponse:
    """List findings recorded on one audit of the caller's tenant."""
    _get_tenant_audit(db, audit_id, current_user.tenant_id)
    query = db.query(Finding).filter(
        Finding.tenant_id == current_user.tenant_id,
        Finding.audit_id == audit_id,
    )
    return _page_findings(query, skip, limit)


@router.get("/findings", response_model=FindingListResponse)
def list_findings(
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    finding_type: Annotated[FindingType | None, Query()] = None,
    audit_id: Annotated[str | None, Query(max_length=36)] = None,
    finding_status: Annotated[str | None, Query(alias="status", max_length=50)] = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FindingListResponse:
    """List findings for the tenant claim ``custom:tenant_id``.

    ``skip`` and ``limit`` page the result. ``finding_type``, ``audit_id``,
    and ``status`` are optional read filters. ``status`` does not change
    the stored value.
    """
    query = db.query(Finding).filter(Finding.tenant_id == current_user.tenant_id)
    if finding_type:
        query = query.filter(Finding.finding_type == finding_type)
    if audit_id:
        query = query.filter(Finding.audit_id == audit_id)
    if finding_status:
        query = query.filter(Finding.status == finding_status)
    return _page_findings(query, skip, limit)


@router.patch("/findings/{finding_id}", response_model=FindingResponse)
def update_finding(
    finding_id: str,
    finding_in: FindingUpdate,
    current_user: CurrentUser = Depends(require_role(FINDING_EDITOR_ROLES)),
    db: Session = Depends(get_db),
) -> Finding:
    """Update descriptive fields of a finding in the caller's tenant.

    Status, the assignee, and the parent audit are left unchanged.
    """
    finding = _get_tenant_finding(db, finding_id, current_user.tenant_id)
    update_data = finding_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(finding, field, value)
    db.commit()
    db.refresh(finding)
    return finding
