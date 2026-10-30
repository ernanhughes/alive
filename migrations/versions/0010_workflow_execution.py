"""Explicit workflow execution ownership after durable Intelligence 0009."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"


def upgrade():
    dangling = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM workflow_stage_runs s LEFT JOIN pi_runs p ON s.pi_run_id = p.id "
            "WHERE s.pi_run_id IS NOT NULL AND p.id IS NULL"
        )
    )
    if dangling:
        raise RuntimeError("Reconcile historical dangling workflow Pi references before migration")
    op.create_table(
        "workflow_executions",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("workflow_runs.id"), primary_key=True),
        sa.Column(
            "authorization_id",
            sa.String(36),
            sa.ForeignKey("events.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("authorization_sha256", sa.String(64), nullable=False),
        sa.Column(
            "investigation_id",
            sa.String(36),
            sa.ForeignKey("investigations.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        ),
        sa.Column("slot", sa.String(36), unique=True),
        sa.Column("owner", sa.String(36)),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("workflow_stage_runs") as batch:
        batch.create_foreign_key("fk_workflow_stage_pi_run", "pi_runs", ["pi_run_id"], ["id"])


def downgrade():
    with op.batch_alter_table("workflow_stage_runs") as batch:
        batch.drop_constraint("fk_workflow_stage_pi_run", type_="foreignkey")
    op.drop_table("workflow_executions")
