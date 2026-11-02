from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.findings import _get_tenant_finding
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.finding_evidence import FindingEvidence
from app.schemas.finding_evidence import (
    FindingEvidenceCreate,
    FindingEvidenceListResponse,
    FindingEvidenceResponse,
)
from app.services.evidence import get_store

router = APIRouter(tags=["finding-evidence"])


def _uploaded_item(tenant_id: str, evidence_id: str) -> dict[str, Any]:
    """Return DynamoDB metadata when this tenant has an uploaded object."""
    item = get_store().get(tenant_id, evidence_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evidence not found",
        )
    if item["status"] != "uploaded":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evidence is not uploaded yet",
        )
    return item


def _to_response(link: FindingEvidence, item: dict[str, Any]) -> FindingEvidenceResponse:
    """Combine the PostgreSQL link with the file metadata from DynamoDB."""
    return FindingEvidenceResponse(
        id=link.id,
        tenant_id=link.tenant_id,
        finding_id=link.finding_id,
        evidence_id=link.evidence_id,
        file_name=item["file_name"],
        content_type=item["content_type"],
        file_size=item["file_size"],
        s3_key=item["s3_key"],
        status=item["status"],
        uploaded_by=item["uploaded_by"],
        uploaded_at=item.get("uploaded_at"),
        linked_by=link.linked_by,
        created_at=link.created_at,
    )


@router.post(
    "/findings/{finding_id}/evidence",
    response_model=FindingEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def link_finding_evidence(
    finding_id: str,
    body: FindingEvidenceCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FindingEvidenceResponse:
    """Link an uploaded evidence item to a finding of the caller's tenant.

    Any authenticated role of the tenant may link. The file metadata stays
    in DynamoDB. A second link of the same pair returns 409.
    """
    _get_tenant_finding(db, finding_id, current_user.tenant_id)
    item = _uploaded_item(current_user.tenant_id, body.evidence_id)
    link = FindingEvidence(
        tenant_id=current_user.tenant_id,
        finding_id=finding_id,
        evidence_id=body.evidence_id,
        linked_by=current_user.sub,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evidence is already linked to this finding",
        ) from None
    db.refresh(link)
    return _to_response(link, item)


@router.get(
    "/findings/{finding_id}/evidence",
    response_model=FindingEvidenceListResponse,
)
def list_finding_evidence(
    finding_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FindingEvidenceListResponse:
    """List evidence linked to one finding, with metadata read from DynamoDB."""
    _get_tenant_finding(db, finding_id, current_user.tenant_id)
    links = (
        db.query(FindingEvidence)
        .filter(
            FindingEvidence.tenant_id == current_user.tenant_id,
            FindingEvidence.finding_id == finding_id,
        )
        .order_by(FindingEvidence.created_at.asc(), FindingEvidence.id.asc())
        .all()
    )
    items: list[FindingEvidenceResponse] = []
    for link in links:
        metadata = get_store().get(current_user.tenant_id, link.evidence_id)
        if metadata is None:
            continue
        items.append(_to_response(link, metadata))
    return FindingEvidenceListResponse(items=items)
