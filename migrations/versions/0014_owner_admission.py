"""Exact local owner-admission reviews and one-way receipt links."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "owner_admissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("principal", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("review_sha256", sa.String(64), nullable=False),
        sa.Column(
            "terms", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_ref", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("revocation_ref", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("authorization_ref", sa.String(36), sa.ForeignKey("events.id")),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id")),
        sa.UniqueConstraint(
            "instance_id", "principal", "idempotency_key", name="uq_owner_admission_retry"
        ),
    )
    op.create_index("ix_owner_admissions_instance_id", "owner_admissions", ["instance_id"])


def downgrade():
    op.drop_table("owner_admissions")
