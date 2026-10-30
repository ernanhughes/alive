"""Pi runs and the provider requests they make (ALIVE-PI-01B)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"

JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade():
    op.create_table(
        "pi_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False, unique=True),
        sa.Column("reservation_ref", sa.String(36)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("approved_request_json", JSON, nullable=False),
        sa.Column("approved_request_sha256", sa.String(64), nullable=False),
        sa.Column("requested_json", JSON, nullable=False),
        sa.Column("pi_version", sa.String(32)),
        sa.Column("pi_bundle_sha256", sa.String(64)),
        sa.Column("flags_sha256", sa.String(64)),
        sa.Column("token_sha256", sa.String(64), nullable=False),
        sa.Column("max_provider_requests", sa.Integer(), nullable=False),
        sa.Column("inbound_requests", sa.Integer(), nullable=False),
        sa.Column("provider_requests", sa.Integer(), nullable=False),
        sa.Column("terminal_reason", sa.String(120)),
        sa.Column("result_json", JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_pi_runs_instance_id", "pi_runs", ["instance_id"])
    op.create_index("ix_pi_runs_operation", "pi_runs", ["operation"])
    op.create_index("ix_pi_runs_state", "pi_runs", ["state"])
    op.create_table(
        "pi_provider_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("pi_runs.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("body_sha256_in", sa.String(64)),
        sa.Column("approved_request_sha256", sa.String(64)),
        sa.Column("model_requested", sa.String(120)),
        sa.Column("model_observed", sa.String(160)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("usage_json", JSON, nullable=True),
        sa.Column("latency_ms", sa.Float()),
        sa.Column("upstream_ref", sa.String(80)),
        sa.Column("error_category", sa.String(64)),
        sa.Column("response_sha256", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_pi_provider_requests_run_seq"),
    )
    op.create_index("ix_pi_provider_requests_run_id", "pi_provider_requests", ["run_id"])
    op.create_index(
        "ix_pi_provider_requests_run_state", "pi_provider_requests", ["run_id", "state"]
    )


def downgrade():
    op.drop_table("pi_provider_requests")
    op.drop_table("pi_runs")
