"""Permissioned documentation snapshots, notes, goals and explicit feedback."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"


def upgrade():
    op.create_table(
        "web_experiences",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), sa.ForeignKey("web_experiences.id")),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("data", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_web_experiences_instance_id", "web_experiences", ["instance_id"])
    op.create_index("ix_web_experiences_kind", "web_experiences", ["kind"])


def downgrade():
    op.drop_table("web_experiences")
