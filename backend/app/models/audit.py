from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Audit(Base, TimestampMixin):
    """Audit session planned and executed within a tenant."""

    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="internal"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="planned"
    )
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auditor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="audits")  # noqa: F821
    auditor: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="assigned_audits", foreign_keys=[auditor_id]
    )
    findings: Mapped[list["Finding"]] = relationship(back_populates="audit")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Audit(id={self.id}, title={self.title}, status={self.status})>"
