from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Tenant(Base, TimestampMixin):
    """Organization/company that uses the platform."""

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="tenant")  # noqa: F821
    audits: Mapped[list["Audit"]] = relationship(back_populates="tenant")  # noqa: F821
    checklists: Mapped[list["Checklist"]] = relationship(back_populates="tenant")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name}, industry={self.industry})>"
