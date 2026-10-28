from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import CurrentUser, get_current_user
from app.schemas.evidence import EvidenceMetadata, UploadUrlRequest, UploadUrlResponse
from app.services.evidence import (
    EvidenceNotFound,
    EvidenceNotUploaded,
    EvidenceObjectMismatch,
    InvalidEvidenceFile,
    confirm_upload,
    create_upload_url,
    get_store,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.post(
    "/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_upload_url(
    body: UploadUrlRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> UploadUrlResponse:
    """Sign a 15-minute PUT for one file of the caller's tenant."""
    try:
        ticket = create_upload_url(
            get_store(),
            tenant_id=current_user.tenant_id,
            uploaded_by=current_user.sub,
            file_name=body.file_name,
            content_type=body.content_type,
            file_size=body.file_size,
        )
    except InvalidEvidenceFile as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return UploadUrlResponse(
        evidence_id=ticket.evidence_id,
        upload_url=ticket.upload_url,
        expires_in=ticket.expires_in,
        headers=ticket.headers,
        s3_key=ticket.s3_key,
    )


@router.post("/{evidence_id}/confirm", response_model=EvidenceMetadata)
def confirm_evidence_upload(
    evidence_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> EvidenceMetadata:
    """Record DynamoDB metadata after the client finishes the PUT."""
    try:
        item = confirm_upload(
            get_store(),
            tenant_id=current_user.tenant_id,
            evidence_id=evidence_id,
        )
    except EvidenceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except EvidenceNotUploaded as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except EvidenceObjectMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return EvidenceMetadata.model_validate(item)
