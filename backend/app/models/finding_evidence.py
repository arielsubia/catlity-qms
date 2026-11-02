from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, generate_uuid


class FindingEvidence(Base):
    """Link between a finding and one DynamoDB evidence item.

    File name, type, size, and the S3 key stay in DynamoDB. ``evidence_id``
    is that table's sort key. The same id can appear on several findings.
    """

    __tablename__ = "finding_evidences"
    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "evidence_id",
            name="uq_finding_evidences_finding_evidence",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    linked_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    finding: Mapped["Finding"] = relationship(back_populates="finding_evidences")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<FindingEvidence(id={self.id}, finding_id={self.finding_id}, "
            f"evidence_id={self.evidence_id})>"
        )
