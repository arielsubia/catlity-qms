from pydantic import BaseModel, ConfigDict, EmailStr, Field

ALLOWED_ROLES = ("admin", "qa_manager", "lead_auditor", "auditor", "auditee")
DEFAULT_ROLE = "auditee"


class RegisterRequest(BaseModel):
    """Payload to register a new user within a tenant."""

    email: EmailStr
    password: str = Field(..., min_length=12, max_length=256)
    full_name: str = Field(..., min_length=1, max_length=255)
    tenant_id: str = Field(..., min_length=1, max_length=36)
    role: str = Field(default="auditee")

    @property
    def normalized_role(self) -> str:
        return self.role.strip().lower()


class RegisterResponse(BaseModel):
    """Result of a successful registration."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    tenant_id: str
    role: str
    cognito_sub: str | None = None


class CurrentUserResponse(BaseModel):
    """Authenticated principal returned by the /auth/me endpoint."""

    sub: str
    email: str | None
    tenant_id: str
    role: str
    groups: list[str]
