from datetime import datetime

from pydantic import BaseModel, Field


class FindingEvidenceCreate(BaseModel):
    """Existing DynamoDB evidence item to attach to a finding."""

    evidence_id: str = Field(..., min_length=1, max_length=36)


class FindingEvidenceResponse(BaseModel):
    """One link plus the file metadata read from DynamoDB."""

    id: str
    tenant_id: str
    finding_id: str
    evidence_id: str
    file_name: str
    content_type: str
    file_size: int
    s3_key: str
    status: str
    uploaded_by: str
    uploaded_at: str | None = None
    linked_by: str
    created_at: datetime


class FindingEvidenceListResponse(BaseModel):
    """Evidence linked to one finding of the caller's tenant."""

    items: list[FindingEvidenceResponse]
