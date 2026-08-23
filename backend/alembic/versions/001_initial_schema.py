"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-12-20

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tenants
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
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

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("cognito_sub", sa.String(255), unique=True, nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="auditee"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
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

    # Audits
    op.create_table(
        "audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("audit_type", sa.String(50), nullable=False, server_default="internal"),
        sa.Column("status", sa.String(50), nullable=False, server_default="planned"),
        sa.Column("planned_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column(
            "auditor_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
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

    # Checklists
    op.create_table(
        "checklists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("standard_reference", sa.String(100), nullable=True),
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

    # Checklist Items
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "checklist_id",
            sa.String(36),
            sa.ForeignKey("checklists.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clause_reference", sa.String(100), nullable=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="true"),
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

    # Findings
    op.create_table(
        "findings",
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
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("finding_type", sa.String(50), nullable=False, server_default="minor_nc"),
        sa.Column("severity", sa.String(50), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(50), nullable=False, server_default="open"),
        sa.Column("clause_reference", sa.String(100), nullable=True),
        sa.Column(
            "assignee_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
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

    # Corrective Actions
    op.create_table(
        "corrective_actions",
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
        sa.Column("description", sa.Text, nullable=False),
        sa.Column(
            "action_type", sa.String(50), nullable=False, server_default="corrective"
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column(
            "responsible_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
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

    # Evidences
    op.create_table(
        "evidences",
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
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "uploaded_by_id",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
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
    op.drop_table("evidences")
    op.drop_table("corrective_actions")
    op.drop_table("findings")
    op.drop_table("checklist_items")
    op.drop_table("checklists")
    op.drop_table("audits")
    op.drop_table("users")
    op.drop_table("tenants")
