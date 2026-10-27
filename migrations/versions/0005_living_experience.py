"""Durable living journeys, completed transitions and empirical policies."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005"
down_revision = "0004"


def upgrade():
    j = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "living_policies",
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), primary_key=True
        ),
        sa.Column("data", j, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "living_journeys",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("data", j, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "living_transitions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("journey_id", sa.String(), sa.ForeignKey("living_journeys.id"), nullable=False),
        sa.Column("episode", sa.Integer(), nullable=False),
        sa.Column("context", sa.String(), nullable=False),
        sa.Column("data", j, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("journey_id", "episode"),
    )


def downgrade():
    for table in ["living_transitions", "living_journeys", "living_policies"]:
        op.drop_table(table)
