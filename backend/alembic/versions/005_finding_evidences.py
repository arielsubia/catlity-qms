"""add finding evidence links

Revision ID: 005
Revises: 004
Create Date: 2026-11-01

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "finding_evidences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "finding_id",
            sa.String(36),
            sa.ForeignKey("findings.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("linked_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "finding_id",
            "evidence_id",
            name="uq_finding_evidences_finding_evidence",
        ),
    )


def downgrade() -> None:
    op.drop_table("finding_evidences")
