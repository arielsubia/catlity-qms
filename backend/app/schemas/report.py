from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.report_html import report_plain_text, sanitize_report_html

MAX_SECTION_LENGTH = 20_000


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


class ReportDraftResponse(BaseModel):
    """One stored draft. References are not columns on the row."""

    id: str
    audit_id: str
    status: str
    resumen: str
    hallazgos: str
    conclusiones: str
    recomendaciones: str


class ReportUpdateRequest(BaseModel):
    """The four sections an editor can replace on an existing draft."""

    resumen: str = Field(..., min_length=1, max_length=MAX_SECTION_LENGTH)
    hallazgos: str = Field(..., min_length=1, max_length=MAX_SECTION_LENGTH)
    conclusiones: str = Field(..., min_length=1, max_length=MAX_SECTION_LENGTH)
    recomendaciones: str = Field(..., min_length=1, max_length=MAX_SECTION_LENGTH)

    @field_validator("resumen", "hallazgos", "conclusiones", "recomendaciones")
    @classmethod
    def section_has_visible_text(cls, value: str) -> str:
        cleaned = sanitize_report_html(value)
        if not report_plain_text(cleaned):
            raise ValueError("section text is required")
        if len(cleaned) > MAX_SECTION_LENGTH:
            raise ValueError("section text is too long")
        return cleaned
