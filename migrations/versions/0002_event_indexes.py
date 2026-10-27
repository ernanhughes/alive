"""Time and bounded outbox indexes."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_index("ix_events_occurred_at", "events", ["occurred_at"])
    op.create_index(
        "ix_events_outbox",
        "events",
        ["sequence_number"],
        postgresql_where=sa.text("published_at IS NULL"),
        sqlite_where=sa.text("published_at IS NULL"),
    )


def downgrade():
    op.drop_index("ix_events_outbox", table_name="events")
    op.drop_index("ix_events_occurred_at", table_name="events")
