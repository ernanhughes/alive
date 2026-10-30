"""Workflow definitions, runs and stage runs (ALIVE-PI-02A).

Follows 0007 (pi_runs, PI-01B).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"

J = sa.JSON().with_variant(JSONB(), "postgresql")


def values(column, items):
    return f"{column} IN ({', '.join(repr(v) for v in items)})"


RUN_STATES = (
    "PENDING", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "CANCELLED", "UNKNOWN",
)  # fmt: skip
STAGE_STATES = (
    "PENDING", "RUNNING", "WAITING_APPROVAL", "COMPLETED", "FAILED", "SKIPPED", "CANCELLED",
    "UNKNOWN",
)  # fmt: skip


def upgrade():
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("definition_json", J, nullable=False),
        sa.Column("definition_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_workflow_definition_version"),
        sa.CheckConstraint("version >= 1", name="ck_workflow_definition_version"),
        sa.CheckConstraint(
            values("status", ("draft", "active", "superseded", "archived")),
            name="ck_workflow_definition_status",
        ),
    )
    op.create_index("ix_workflow_definitions_name", "workflow_definitions", ["name"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("workflow_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("workflow_name", sa.String(64), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("definition_sha256", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("goals.id")),
        sa.Column("investigation_id", sa.String(36), sa.ForeignKey("investigations.id")),
        sa.Column("trigger", sa.String(24), nullable=False),
        sa.Column("input_ref", sa.String(200)),
        sa.Column("input_sha256", sa.String(64)),
        sa.Column("authorization_ref", sa.String(200)),
        sa.Column("budget_json", J, nullable=False),
        sa.Column("idempotency_key", sa.String(120), unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("terminal_reason", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(values("status", RUN_STATES), name="ck_workflow_run_status"),
    )
    op.create_index("ix_workflow_runs_instance_id", "workflow_runs", ["instance_id"])
    op.create_index("ix_workflow_runs_definition_id", "workflow_runs", ["definition_id"])
    op.create_index("ix_workflow_runs_goal_id", "workflow_runs", ["goal_id"])
    op.create_index(
        "ix_workflow_runs_name_created", "workflow_runs", ["workflow_name", "created_at"]
    )
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "workflow_stage_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(36),
            sa.ForeignKey("workflow_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("stage_id", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("stage_type", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("input_ref", sa.String(200)),
        sa.Column("input_sha256", sa.String(64)),
        sa.Column("output_ref", sa.String(200)),
        sa.Column("output_sha256", sa.String(64)),
        sa.Column("pi_run_id", sa.String(36)),
        sa.Column("model_invocation_id", sa.String(36), sa.ForeignKey("model_invocations.id")),
        sa.Column("evidence_refs", J, nullable=False),
        sa.Column("validation_status", sa.String(10), nullable=False),
        sa.Column("error_category", sa.String(64)),
        sa.Column("error_detail", sa.String(300)),
        sa.Column("uncertainty", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "stage_id", "attempt", name="uq_workflow_stage_attempt"),
        sa.CheckConstraint(values("state", STAGE_STATES), name="ck_workflow_stage_state"),
        sa.CheckConstraint(
            values("validation_status", ("not_run", "passed", "failed")),
            name="ck_workflow_stage_validation",
        ),
        sa.CheckConstraint(
            values("uncertainty", ("none", "ambiguous_dispatch", "unknown_outcome")),
            name="ck_workflow_stage_uncertainty",
        ),
        sa.CheckConstraint("attempt >= 1", name="ck_workflow_stage_attempt"),
    )
    op.create_index("ix_workflow_stage_runs_run_id", "workflow_stage_runs", ["run_id"])
    op.create_index("ix_workflow_stage_runs_pi_run_id", "workflow_stage_runs", ["pi_run_id"])


def downgrade():
    op.drop_table("workflow_stage_runs")
    op.drop_table("workflow_runs")
    op.drop_table("workflow_definitions")
