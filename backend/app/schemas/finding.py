from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

FindingType = Literal[
    "major_nc",
    "minor_nc",
    "observation",
    "improvement_opportunity",
]
FindingStatus = Literal[
    "open",
    "in_progress",
    "resolved",
    "verified",
    "closed",
]


class FindingCreate(BaseModel):
    """Fields the client may set when recording a finding.

    Status is not accepted here. The API always stores ``open``.
    The assignee is left empty; lifecycle and corrective actions use
    other routes.
    """

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    finding_type: FindingType = "minor_nc"
    severity: str = Field(default="medium", min_length=1, max_length=50)
    clause_reference: str | None = Field(None, max_length=100)


class FindingUpdate(BaseModel):
    """Partial update of descriptive fields.

    Status, assignee, and the parent audit stay out of this payload.
    """

    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    finding_type: FindingType | None = None
    severity: str | None = Field(None, min_length=1, max_length=50)
    clause_reference: str | None = Field(None, max_length=100)

    @field_validator("title", "finding_type", "severity")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str | None:
        """Keep non-nullable columns from being cleared with JSON null."""
        if value is None:
            raise ValueError("cannot be null")
        return value


class FindingStatusUpdate(BaseModel):
    """Target status for one allowed finding transition."""

    status: FindingStatus


class FindingResponse(BaseModel):
    """Finding returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    audit_id: str
    title: str
    description: str | None
    finding_type: str
    severity: str
    status: str
    status_changed_at: datetime | None
    clause_reference: str | None
    assignee_id: str | None
    created_at: datetime
    updated_at: datetime


class FindingListResponse(BaseModel):
    """One page of findings for the caller's tenant."""

    items: list[FindingResponse]
    total: int
    skip: int
    limit: int
