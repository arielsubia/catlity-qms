from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, generate_uuid


class AuditReport(Base, TimestampMixin):
    """Editable draft produced for one completed audit.

    Each generate call inserts a new row. Later edits use these text columns.
    The row lives in the local database.
    """

    __tablename__ = "audit_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    audit_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("audits.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft"
    )
    resumen: Mapped[str] = mapped_column(Text, nullable=False)
    hallazgos: Mapped[str] = mapped_column(Text, nullable=False)
    conclusiones: Mapped[str] = mapped_column(Text, nullable=False)
    recomendaciones: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AuditReport(id={self.id}, audit_id={self.audit_id}, "
            f"status={self.status})>"
        )
