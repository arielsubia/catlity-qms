from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Finding(Base, TimestampMixin):
    """Non-conformity or observation found during an audit."""

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    audit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audits.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="minor_nc"
    )
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False, default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="open"
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    clause_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    assignee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    audit: Mapped["Audit"] = relationship(back_populates="findings")  # noqa: F821
    assignee: Mapped["User | None"] = relationship(  # noqa: F821
        back_populates="assigned_findings", foreign_keys=[assignee_id]
    )
    corrective_actions: Mapped[list["CorrectiveAction"]] = relationship(  # noqa: F821
        back_populates="finding"
    )
    evidences: Mapped[list["Evidence"]] = relationship(back_populates="finding")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Finding(id={self.id}, type={self.finding_type}, status={self.status})>"
