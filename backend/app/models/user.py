from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    """User belonging to a tenant organization."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    cognito_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="auditee")
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="users")  # noqa: F821
    assigned_audits: Mapped[list["Audit"]] = relationship(  # noqa: F821
        back_populates="auditor", foreign_keys="Audit.auditor_id"
    )
    assigned_findings: Mapped[list["Finding"]] = relationship(  # noqa: F821
        back_populates="assignee", foreign_keys="Finding.assignee_id"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
