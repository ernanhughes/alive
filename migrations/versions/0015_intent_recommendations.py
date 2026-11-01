"""Immutable intent-interpretation recommendations (L2-01)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "intent_recommendations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column(
            "admission_id",
            sa.String(36),
            sa.ForeignKey("owner_admissions.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("record_sha256", sa.String(64), nullable=False),
        sa.Column(
            "record", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_intent_recommendations_instance_id", "intent_recommendations", ["instance_id"]
    )


def downgrade():
    op.drop_table("intent_recommendations")
