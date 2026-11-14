from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReportGenerateRequest(BaseModel):
    """Audit whose completed findings become a draft report."""

    audit_id: str = Field(..., min_length=1, max_length=36)

    @field_validator("audit_id")
    @classmethod
    def audit_id_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("audit_id is required")
        return stripped


class ReportReferenceResponse(BaseModel):
    """File name of a study note retrieved for the draft.

    The notes are plain text, so the file name is both the document and the
    section. The name is stored as it appears in the note.
    """

    document: str
    section: str


class ReportGenerateResponse(BaseModel):
    """Draft stored for a completed audit, split into the four sections."""

    id: str
    audit_id: str
    status: Literal["draft"]
    resumen: str
    hallazgos: str
    conclusiones: str
    recomendaciones: str
    references: list[ReportReferenceResponse]
