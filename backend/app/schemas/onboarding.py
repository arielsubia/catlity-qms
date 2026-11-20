from pydantic import BaseModel, Field, field_validator


class OnboardingMessageRequest(BaseModel):
    """One user reply in an onboarding session."""

    session_id: str = Field(..., min_length=1)
    message: str

    @field_validator("session_id", "message")
    @classmethod
    def text_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped


class OnboardingResponse(BaseModel):
    """The session, the next prompt, and the four onboarding flags."""

    session_id: str
    reply: str
    industry_selected: bool
    kb_assigned: bool
    checklists_created: bool
    admin_created: bool
    knowledge_base_ids: dict[str, str] | None = None
    tenant_id: str | None = None
