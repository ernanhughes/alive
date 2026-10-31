"""Retain exact capability contracts without rewriting historical definition hashes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None


def upgrade():
    data = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "workflow_capability_bindings",
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("snapshot", data, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("source_ref", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("workflow_executions") as batch:
        batch.add_column(
            sa.Column("capability_snapshot", data, nullable=False, server_default="{}")
        )
        batch.add_column(sa.Column("capability_snapshot_sha256", sa.String(64), nullable=True))


def downgrade():
    with op.batch_alter_table("workflow_executions") as batch:
        batch.drop_column("capability_snapshot_sha256")
        batch.drop_column("capability_snapshot")
    op.drop_table("workflow_capability_bindings")
