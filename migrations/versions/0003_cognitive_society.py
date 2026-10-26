"""Persistent cognition, scoped actions, model accounting and versioned experience."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"


def upgrade():
    j = sa.JSON().with_variant(JSONB(), "postgresql")

    def c(name, kind=sa.String(), **kw):
        return sa.Column(name, kind, **kw)

    def pk():
        return c("id", sa.String(36), primary_key=True)

    def fk(name, target, **kw):
        return sa.Column(name, sa.String(36), sa.ForeignKey(target), **kw)

    def dt(name):
        return c(name, sa.DateTime(timezone=True), nullable=False)

    op.create_table(
        "cognitive_control",
        fk("instance_id", "alive_instances.id", primary_key=True),
        c("mode", nullable=False),
        c("provider", nullable=False),
        c("session_id", nullable=False),
        c("cursor", sa.Integer(), nullable=False),
        c("configuration", j, nullable=False),
        c("spent", j, nullable=False),
        c("reserved", j, nullable=False),
        dt("updated_at"),
    )
    op.create_table(
        "cognitive_observations",
        pk(),
        fk("instance_id", "alive_instances.id", nullable=False),
        fk("source_event_id", "events.id", unique=True, nullable=False),
        c("fingerprint", unique=True, nullable=False),
        c("content", sa.Text(), nullable=False),
        c("provenance", j, nullable=False),
        c("attention", j, nullable=False),
        c("status", nullable=False),
        dt("created_at"),
    )
    op.create_table(
        "investigations",
        pk(),
        fk("instance_id", "alive_instances.id", nullable=False),
        fk("observation_id", "cognitive_observations.id", unique=True, nullable=False),
        fk("goal_id", "goals.id", nullable=False),
        c("state", nullable=False),
        c("snapshot", j, nullable=False),
        c("history", j, nullable=False),
        c("budget", j, nullable=False),
        c("usage", j, nullable=False),
        c("evaluation", j, nullable=False),
        c("error"),
        dt("created_at"),
        dt("updated_at"),
    )
    op.create_table(
        "model_invocations",
        pk(),
        fk("investigation_id", "investigations.id", nullable=False),
        c("role", nullable=False),
        c("provider", nullable=False),
        c("model", nullable=False),
        c("status", nullable=False),
        c("input_json", j, nullable=False),
        c("output_json", j, nullable=False),
        c("usage", j, nullable=False),
        c("latency_ms", sa.Float(), nullable=False),
        c("reserved_tokens", sa.Integer(), nullable=False),
        c("error"),
        dt("created_at"),
    )
    op.create_index(
        "ix_model_invocations_investigation_id", "model_invocations", ["investigation_id"]
    )
    op.create_table(
        "cognitive_messages",
        pk(),
        fk("investigation_id", "investigations.id", nullable=False),
        fk("invocation_id", "model_invocations.id"),
        c("sender", nullable=False),
        c("recipient", nullable=False),
        c("message_type", nullable=False),
        c("content", j, nullable=False),
        c("schema_version", sa.Integer(), nullable=False),
        dt("created_at"),
    )
    op.create_index(
        "ix_cognitive_messages_investigation_id", "cognitive_messages", ["investigation_id"]
    )
    op.create_table(
        "action_proposals",
        pk(),
        fk("investigation_id", "investigations.id", unique=True, nullable=False),
        c("kind", nullable=False),
        c("risk_class", nullable=False),
        c("status", nullable=False),
        c("proposal", j, nullable=False),
        c("outcome", j, nullable=False),
        dt("created_at"),
    )
    op.create_table(
        "experiences",
        pk(),
        fk("investigation_id", "investigations.id", unique=True, nullable=False),
        fk("instance_id", "alive_instances.id", nullable=False),
        c("schema_version", sa.Integer(), nullable=False),
        c("data", j, nullable=False),
        dt("created_at"),
    )
    op.create_table(
        "memory_vectors",
        fk("memory_id", "memories.id", primary_key=True),
        c("model", primary_key=True),
        c("revision", primary_key=True),
        c("dimension", sa.Integer(), nullable=False),
        c("values_json", j, nullable=False),
        dt("created_at"),
    )
    op.create_table(
        "history_imports",
        pk(),
        fk("instance_id", "alive_instances.id", nullable=False),
        c("status", nullable=False),
        c("entries", j, nullable=False),
        c("memory_ids", j, nullable=False),
        dt("created_at"),
    )
    op.create_table(
        "laboratory_environments",
        pk(),
        fk("instance_id", "alive_instances.id", nullable=False),
        c("scenario", nullable=False),
        c("state", j, nullable=False),
        c("sources", j, nullable=False),
        c("version", sa.Integer(), nullable=False),
        c("draft", sa.Text(), nullable=False),
        dt("created_at"),
    )
    # Original vector(384) remains compatible. A versioned sidecar separates model spaces.
    if op.get_bind().dialect.name == "postgresql":
        if op.get_bind().scalar(
            sa.text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
        ):
            op.execute("ALTER TABLE memory_vectors ADD COLUMN embedding vector(384)")
            op.execute(
                "CREATE INDEX ix_memory_vectors_cosine ON memory_vectors "
                "USING hnsw (embedding vector_cosine_ops)"
            )
    op.create_index(
        "ix_cognitive_observations_queue", "cognitive_observations", ["status", "created_at"]
    )
    op.create_index("ix_investigations_state", "investigations", ["state"])


def downgrade():
    for name in [
        "laboratory_environments",
        "history_imports",
        "memory_vectors",
        "experiences",
        "action_proposals",
        "cognitive_messages",
        "model_invocations",
        "investigations",
        "cognitive_observations",
        "cognitive_control",
    ]:
        op.drop_table(name)
