"""Durable advisory Intelligence lifecycle (INT-02), after workflow foundation 0008."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009"
down_revision = "0008"
J = sa.JSON().with_variant(JSONB(), "postgresql")


def fk(name, table, *, unique=False, nullable=False, length=36):
    return sa.Column(
        name, sa.String(length), sa.ForeignKey(table), unique=unique, nullable=nullable
    )


def stamp():
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade():
    op.create_table(
        "intelligence_states",
        sa.Column("id", sa.String(36), primary_key=True),
        fk("instance_id", "alive_instances.id"),
        fk("goal_id", "goals.id"),
        sa.Column("active_json", J, nullable=False),
        sa.Column("active_hash", sa.String(64), nullable=False),
        sa.Column("candidate_json", J, nullable=False),
        sa.Column("candidate_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("quarantined", sa.Boolean(), nullable=False),
        stamp(),
        sa.CheckConstraint("revision >= 0", name="ck_intelligence_revision"),
    )
    op.create_table(
        "intelligence_episodes",
        sa.Column("id", sa.String(100), primary_key=True),
        fk("instance_id", "alive_instances.id"),
        fk("state_id", "intelligence_states.id"),
        fk("workflow_stage_id", "workflow_stage_runs.id"),
        fk("source_event_id", "events.id", unique=True),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("snapshot_json", J, nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("proposal_id", sa.String(100), unique=True, nullable=False),
        *[
            sa.Column(n, sa.String(20))
            for n in (
                "proposed_action",
                "active_choice",
                "shadow_action",
                "authorized_action",
                "executed_action",
            )
        ],
        fk("model_invocation_id", "model_invocations.id", nullable=True),
        fk("pi_run_id", "pi_runs.id", nullable=True),
        fk("previous_id", "intelligence_episodes.id", nullable=True, length=100),
        stamp(),
        sa.CheckConstraint(
            "authorized_action IS NULL AND executed_action IS NULL",
            name="ck_intelligence_advisory_only",
        ),
    )
    op.create_table(
        "intelligence_feedback",
        sa.Column("id", sa.String(100), primary_key=True),
        fk("instance_id", "alive_instances.id"),
        fk("episode_id", "intelligence_episodes.id", unique=True, length=100),
        fk("source_event_id", "events.id", unique=True),
        sa.Column("outcome_hash", sa.String(64), nullable=False),
        sa.Column("payload_json", J, nullable=False),
        sa.Column("authority_class", sa.String(32), nullable=False),
        stamp(),
    )
    op.create_table(
        "intelligence_measurement_uses",
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), primary_key=True
        ),
        sa.Column("evidence_id", sa.String(100), primary_key=True),
        sa.Column("observation_hash", sa.String(64), nullable=False),
        fk("feedback_id", "intelligence_feedback.id", length=100),
        sa.UniqueConstraint(
            "instance_id", "observation_hash", name="uq_intelligence_measurement_use"
        ),
    )
    op.create_table(
        "intelligence_learning_updates",
        sa.Column("id", sa.String(36), primary_key=True),
        fk("state_id", "intelligence_states.id"),
        fk("feedback_id", "intelligence_feedback.id", unique=True, length=100),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column("before_json", J, nullable=False),
        sa.Column("before_hash", sa.String(64), nullable=False),
        sa.Column("after_json", J, nullable=False),
        sa.Column("after_hash", sa.String(64), nullable=False),
        stamp(),
    )
    for table, columns in {
        "intelligence_states": ("instance_id",),
        "intelligence_episodes": ("instance_id", "state_id"),
        "intelligence_feedback": ("instance_id",),
        "intelligence_learning_updates": ("state_id",),
    }.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in (
        "intelligence_learning_updates",
        "intelligence_measurement_uses",
        "intelligence_feedback",
        "intelligence_episodes",
        "intelligence_states",
    ):
        op.drop_table(table)
