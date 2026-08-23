from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Evidence(Base, TimestampMixin):
    """Document or photo evidence attached to a finding."""

    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id"), nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    # Relationships
    finding: Mapped["Finding"] = relationship(back_populates="evidences")  # noqa: F821
    uploaded_by: Mapped["User | None"] = relationship(foreign_keys=[uploaded_by_id])  # noqa: F821

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, file_name={self.file_name})>"
