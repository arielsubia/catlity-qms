from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class CorrectiveAction(Base, TimestampMixin):
    """Corrective or preventive action for a finding."""

    __tablename__ = "corrective_actions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="corrective"
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    responsible_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effectiveness: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    finding: Mapped["Finding"] = relationship(back_populates="corrective_actions")  # noqa: F821
    responsible: Mapped["User | None"] = relationship(foreign_keys=[responsible_id])  # noqa: F821

    def __repr__(self) -> str:
        return f"<CorrectiveAction(id={self.id}, status={self.status})>"
