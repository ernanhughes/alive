"""Source custody: immutable captures and separately recorded owner approvals."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = depends_on = None


def upgrade():
    data = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "source_captures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("locator", sa.String(256), nullable=False, server_default=""),
        sa.Column("classification", sa.String(24), nullable=False),
        sa.Column("capture_method", sa.String(48), nullable=False),
        sa.Column("content", data, nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("byte_count", sa.Integer, nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capture_event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('repository','document','browser','collection')",
            name="ck_source_capture_type",
        ),
        sa.CheckConstraint(
            "classification IN ('owner_internal','untrusted_browser')",
            name="ck_source_capture_classification",
        ),
        sa.CheckConstraint("byte_count >= 0 AND item_count >= 0", name="ck_source_capture_counts"),
    )
    op.create_index("ix_source_captures_instance_id", "source_captures", ["instance_id"])
    op.create_table(
        "source_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("capture_id", sa.String(36), sa.ForeignKey("source_captures.id"), nullable=False),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("operations", data, nullable=False),
        sa.Column("scope", data, nullable=False),
        sa.Column("scope_sha256", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.String(100), nullable=False),
        sa.Column("approval_event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_by", sa.String(100), nullable=True),
        sa.Column("withdrawn_reason", sa.String(200), nullable=True),
        sa.Column("withdrawal_event_id", sa.String(36), sa.ForeignKey("events.id"), nullable=True),
        sa.UniqueConstraint(
            "instance_id", "idempotency_key", name="uq_source_approval_idempotency"
        ),
    )
    op.create_index("ix_source_approvals_capture_id", "source_approvals", ["capture_id"])
    op.create_index("ix_source_approvals_instance_id", "source_approvals", ["instance_id"])


def downgrade():
    op.drop_index("ix_source_approvals_instance_id", table_name="source_approvals")
    op.drop_index("ix_source_approvals_capture_id", table_name="source_approvals")
    op.drop_table("source_approvals")
    op.drop_index("ix_source_captures_instance_id", table_name="source_captures")
    op.drop_table("source_captures")
