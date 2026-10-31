"""Immutable Bespoke recommendation history; grants and runs remain existing records."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "bespoke_recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("principal", sa.String(100), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("goals.id"), nullable=False),
        sa.Column(
            "investigation_id", sa.String(36), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column("source_ref", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("selection_sha256", sa.String(64), nullable=False),
        sa.Column(
            "selection", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instance_id", "principal", "idempotency_key", name="uq_bespoke_retry"),
    )
    op.create_index(
        "ix_bespoke_recommendations_instance_id", "bespoke_recommendations", ["instance_id"]
    )


def downgrade():
    op.drop_table("bespoke_recommendations")
