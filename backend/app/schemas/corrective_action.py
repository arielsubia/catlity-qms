from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CorrectiveActionCreate(BaseModel):
    """Fields the client may set when recording a corrective action.

    Status, action type, and the responsible user are not accepted here.
    The API stores ``pending``, ``corrective``, and an empty responsible.
    """

    description: str = Field(..., min_length=1)
    due_date: date | None = None
    completion_date: date | None = None
    effectiveness: str | None = Field(None, max_length=255)


class CorrectiveActionUpdate(BaseModel):
    """Partial update of the descriptive corrective-action fields.

    The parent finding, status, action type, and responsible stay out of
    this payload.
    """

    description: str | None = Field(None, min_length=1)
    due_date: date | None = None
    completion_date: date | None = None
    effectiveness: str | None = Field(None, max_length=255)

    @field_validator("description")
    @classmethod
    def reject_explicit_null(cls, value: str | None) -> str | None:
        """Keep the required description from being cleared with JSON null."""
        if value is None:
            raise ValueError("cannot be null")
        return value


class CorrectiveActionResponse(BaseModel):
    """Corrective action returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    finding_id: str
    description: str
    action_type: str
    status: str
    responsible_id: str | None
    due_date: date | None
    completion_date: date | None
    effectiveness: str | None
    created_at: datetime
    updated_at: datetime


class CorrectiveActionListResponse(BaseModel):
    """One page of corrective actions for a finding in the caller's tenant."""

    items: list[CorrectiveActionResponse]
    total: int
    skip: int
    limit: int
