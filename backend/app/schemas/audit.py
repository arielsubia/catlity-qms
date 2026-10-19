from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AuditStatus = Literal["planned", "in_progress", "completed", "closed"]


class AuditCreate(BaseModel):
    """Fields the client may set when opening an audit.

    Status is not accepted here. The API always stores ``planned``.
    Auditor assignment belongs to a later story.
    """

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    audit_type: str = Field(default="internal", min_length=1, max_length=50)
    planned_date: date | None = None


class AuditUpdate(BaseModel):
    """Partial update. Status and auditor assignment stay out of this payload."""

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    audit_type: str | None = Field(None, min_length=1, max_length=50)
    planned_date: date | None = None


class AuditStatusUpdate(BaseModel):
    """Target status for one forward transition."""

    status: AuditStatus


class AuditResponse(BaseModel):
    """Audit returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    title: str
    description: str | None
    audit_type: str
    status: str
    status_changed_at: datetime | None
    planned_date: date | None
    completion_date: date | None
    auditor_id: str | None
    created_at: datetime
    updated_at: datetime


class AuditListResponse(BaseModel):
    """One page of audits for the caller's tenant."""

    items: list[AuditResponse]
    total: int
    skip: int
    limit: int
