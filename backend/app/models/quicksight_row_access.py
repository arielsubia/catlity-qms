from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class QuickSightRowAccess(Base, TimestampMixin):
    """QuickSight user allowed to see one tenant, or every tenant when tenant_id is null."""

    __tablename__ = "quicksight_row_access"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    user_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<QuickSightRowAccess(user_name={self.user_name}, "
            f"tenant_id={self.tenant_id})>"
        )
