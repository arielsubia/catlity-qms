from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantBase(BaseModel):
    """Shared properties for tenant."""

    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class TenantCreate(TenantBase):
    """Properties required to create a tenant."""

    pass


class TenantUpdate(BaseModel):
    """Properties that can be updated on a tenant."""

    name: str | None = Field(None, min_length=1, max_length=255)
    industry: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    is_active: bool | None = None


class TenantResponse(TenantBase):
    """Properties returned to the client."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
