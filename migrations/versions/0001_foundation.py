"""Initial ALIVE schema with PostgreSQL search and optional vector storage."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None


def upgrade():
    bind = op.get_bind()
    j = sa.JSON().with_variant(JSONB(), "postgresql")

    def col(name, kind=sa.String(), **kwargs):
        return sa.Column(name, kind, **kwargs)

    def pk():
        return col("id", sa.String(36), primary_key=True)

    def instance():
        return sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), nullable=False
        )

    def date(name):
        return col(name, sa.DateTime(timezone=True), nullable=False)

    op.create_table(
        "alive_instances",
        pk(),
        col("name", nullable=False),
        date("created_at"),
        date("last_active_at"),
        col("lifecycle_state", nullable=False),
        col("configuration", j, nullable=False),
        col("version", sa.Integer(), nullable=False),
    )
    op.create_table(
        "events",
        col("sequence_number", sa.Integer(), primary_key=True, autoincrement=True),
        col("id", sa.String(36), nullable=False, unique=True),
        instance(),
        col("event_type", nullable=False),
        col("source", nullable=False),
        col("correlation_id", nullable=False),
        col("causation_id"),
        col("schema_version", sa.Integer(), nullable=False),
        col("payload", j, nullable=False),
        date("occurred_at"),
        date("recorded_at"),
        col("published_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "memories",
        pk(),
        instance(),
        col("content", sa.Text(), nullable=False),
        col("memory_type", nullable=False),
        sa.Column("source_event_id", sa.String(36), sa.ForeignKey("events.id"), unique=True),
        col("importance", sa.Float(), nullable=False),
        col("confidence", sa.Float(), nullable=False),
        col("metadata", j, nullable=False),
        date("created_at"),
        date("updated_at"),
    )
    op.create_table(
        "goals",
        pk(),
        instance(),
        col("title", nullable=False),
        col("description", sa.Text(), nullable=False),
        col("origin", nullable=False),
        col("priority", sa.Integer(), nullable=False),
        col("status", nullable=False),
        sa.Column("parent_goal_id", sa.String(36), sa.ForeignKey("goals.id")),
        date("created_at"),
        date("updated_at"),
        col("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "agent_runs",
        pk(),
        instance(),
        col("runner", nullable=False),
        col("model_provider", nullable=False),
        col("model_id", nullable=False),
        col("objective", sa.Text(), nullable=False),
        col("status", nullable=False),
        date("started_at"),
        col("completed_at", sa.DateTime(timezone=True)),
        col("result", sa.Text()),
        col("error", sa.Text()),
        col("usage", j, nullable=False),
    )
    op.create_table(
        "browser_sessions",
        pk(),
        instance(),
        col("session_type", nullable=False),
        col("status", nullable=False),
        col("current_url", nullable=False),
        date("created_at"),
        date("updated_at"),
    )
    op.create_table(
        "runtime_state",
        sa.Column(
            "instance_id", sa.String(36), sa.ForeignKey("alive_instances.id"), primary_key=True
        ),
        col("heartbeat_at", sa.DateTime(timezone=True)),
        col("active_goals", j, nullable=False),
        col("resource_budget", j, nullable=False),
        col("state_version", sa.Integer(), nullable=False),
        col("observation_hashes", j, nullable=False),
    )
    for table, columns in [
        ("events", ["instance_id"]),
        ("events", ["event_type"]),
        ("events", ["correlation_id"]),
        ("events", ["instance_id", "sequence_number"]),
        ("memories", ["instance_id"]),
        ("goals", ["instance_id"]),
        ("agent_runs", ["instance_id"]),
    ]:
        name = "ix_events_instance_sequence" if len(columns) == 2 else f"ix_{table}_{columns[0]}"
        op.create_index(name, table, columns)
    if bind.dialect.name == "postgresql":
        op.execute("""ALTER TABLE memories ADD COLUMN search_document tsvector
          GENERATED ALWAYS AS (to_tsvector('english', content)) STORED""")
        op.execute("CREATE INDEX ix_memory_fts ON memories USING gin(search_document)")
        # Availability and privilege are independent; a failed CREATE must not abort migration.
        op.execute("""DO $$ BEGIN
          CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN undefined_file OR insufficient_privilege OR feature_not_supported THEN
          RAISE NOTICE 'pgvector unavailable; semantic search disabled';
        END $$""")
        available = bind.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
        )
        if available:
            op.execute("ALTER TABLE memories ADD COLUMN embedding vector(384)")
        else:
            op.execute("ALTER TABLE memories ADD COLUMN embedding JSONB")
        for table, expression, name in [
            (
                "goals",
                "status IN ('proposed','accepted','active','completed','cancelled')",
                "goal_status",
            ),
            (
                "memories",
                "importance BETWEEN 0 AND 1 AND confidence BETWEEN 0 AND 1",
                "memory_scores",
            ),
            ("agent_runs", "status IN ('running','completed','failed','cancelled')", "run_status"),
        ]:
            op.create_check_constraint(name, table, expression)


def downgrade():
    for table in [
        "runtime_state",
        "browser_sessions",
        "agent_runs",
        "goals",
        "memories",
        "events",
        "alive_instances",
    ]:
        op.drop_table(table)
