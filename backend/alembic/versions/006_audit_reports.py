"""add audit report drafts

Revision ID: 006
Revises: 005
Create Date: 2026-11-13

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "audit_id",
            sa.String(36),
            sa.ForeignKey("audits.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("resumen", sa.Text(), nullable=False),
        sa.Column("hallazgos", sa.Text(), nullable=False),
        sa.Column("conclusiones", sa.Text(), nullable=False),
        sa.Column("recomendaciones", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_reports")
