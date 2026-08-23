from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Checklist(Base, TimestampMixin):
    """Audit checklist template for a tenant."""

    __tablename__ = "checklists"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    standard_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="checklists")  # noqa: F821
    items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="checklist", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Checklist(id={self.id}, name={self.name})>"


class ChecklistItem(Base, TimestampMixin):
    """Individual item within a checklist."""

    __tablename__ = "checklist_items"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    checklist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("checklists.id"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clause_reference: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    is_mandatory: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Relationships
    checklist: Mapped["Checklist"] = relationship(back_populates="items")

    def __repr__(self) -> str:
        return f"<ChecklistItem(id={self.id}, clause={self.clause_reference})>"
