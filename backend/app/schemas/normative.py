from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_LENGTH = 1000


class NormativeQueryRequest(BaseModel):
    """Question sent to the normative advisor."""

    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)

    @field_validator("question")
    @classmethod
    def question_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question is required")
        return stripped


class NormativeReference(BaseModel):
    """File name of a study note used to answer the question.

    The notes are plain text, so the file name is both the document and the
    section. Retrieve does not return a page number.
    """

    document: str
    section: str


class NormativeQueryResponse(BaseModel):
    """Answer and the study notes that were retrieved for it."""

    answer: str
    references: list[NormativeReference]
