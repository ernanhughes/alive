"""Workflow tables (ALIVE-PI-02A, migration 0008): definitions, runs, stage runs.

The three entities are the minimum correct schema. Existing records are REFERENCED, not duplicated:
events stay in `events`, model calls in `model_invocations`, inquiries in `goals`/`investigations`.
A run keeps a snapshot of the definition identity it ran, so no later change can repoint history.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.workflows import states


def in_list(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ImmutableRecord(RuntimeError):
    """A column that is part of a historical identity was about to change."""


class WorkflowDefinition(Base):
    __tablename__ = "workflow_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    definition_json: Mapped[dict] = mapped_column(J)
    definition_sha256: Mapped[str] = mapped_column(String(64))
    # The only mutable column: lifecycle metadata, deliberately outside the hashed content.
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source: Mapped[str] = mapped_column(String(16), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_workflow_definition_version"),
        CheckConstraint("version >= 1", name="ck_workflow_definition_version"),
        CheckConstraint(
            in_list("status", states.DEFINITION_STATUSES), name="ck_workflow_definition_status"
        ),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="RESTRICT"), index=True
    )
    # Snapshot of the exact definition that ran. Never rewritten.
    workflow_name: Mapped[str] = mapped_column(String(64))
    workflow_version: Mapped[int] = mapped_column(Integer)
    definition_sha256: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer)
    # Existing ALIVE identifiers for the inquiry this run belongs to (both optional).
    goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"), index=True)
    investigation_id: Mapped[str | None] = mapped_column(ForeignKey("investigations.id"))
    trigger: Mapped[str] = mapped_column(String(24), default="manual")
    input_ref: Mapped[str | None] = mapped_column(String(200))  # an opaque reference, never content
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    authorization_ref: Mapped[str | None] = mapped_column(String(200))
    budget_json: Mapped[dict] = mapped_column(J, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=states.PENDING)
    terminal_reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(in_list("status", states.RUN_STATES), name="ck_workflow_run_status"),
        Index("ix_workflow_runs_name_created", "workflow_name", "created_at"),
        Index("ix_workflow_runs_status", "status"),
    )


class WorkflowStageRun(Base):
    __tablename__ = "workflow_stage_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), index=True
    )
    stage_id: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    stage_type: Mapped[str] = mapped_column(String(20))
    operation: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20), default=states.PENDING)
    input_ref: Mapped[str | None] = mapped_column(String(200))
    input_sha256: Mapped[str | None] = mapped_column(String(64))
    output_ref: Mapped[str | None] = mapped_column(String(200))
    output_sha256: Mapped[str | None] = mapped_column(String(64))
    # A Pi stage links to the PI-01B receipt, which stays authoritative for provider dispatch.
    # A plain id, not a foreign key: `pi_runs` ships with PI-01B and PI-02B adds the constraint.
    pi_run_id: Mapped[str | None] = mapped_column(String(36), index=True)
    model_invocation_id: Mapped[str | None] = mapped_column(ForeignKey("model_invocations.id"))
    evidence_refs: Mapped[list] = mapped_column(J, default=list)
    validation_status: Mapped[str] = mapped_column(String(10), default="not_run")
    error_category: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(String(300))
    uncertainty: Mapped[str] = mapped_column(String(24), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("run_id", "stage_id", "attempt", name="uq_workflow_stage_attempt"),
        CheckConstraint(in_list("state", states.STAGE_STATES), name="ck_workflow_stage_state"),
        CheckConstraint(
            in_list("validation_status", states.VALIDATION_STATUSES),
            name="ck_workflow_stage_validation",
        ),
        CheckConstraint(
            in_list("uncertainty", states.UNCERTAINTY), name="ck_workflow_stage_uncertainty"
        ),
        CheckConstraint("attempt >= 1", name="ck_workflow_stage_attempt"),
    )


# --- historical identity cannot change --------------------------------------------------------

_DEFINITION_FROZEN = ("name", "version", "schema_version", "definition_json", "definition_sha256")
_RUN_FROZEN = (
    "definition_id",
    "workflow_name",
    "workflow_version",
    "definition_sha256",
    "schema_version",
    "instance_id",
)
_STAGE_FROZEN = ("run_id", "stage_id", "attempt", "stage_type", "operation")


def _guard(columns):
    def check(_mapper, _connection, target):
        from sqlalchemy import inspect

        state = inspect(target)
        for column in columns:
            if state.attrs[column].history.has_changes():
                raise ImmutableRecord(
                    f"{type(target).__name__}.{column} is part of a historical identity"
                )

    return check


for model, frozen in (
    (WorkflowDefinition, _DEFINITION_FROZEN),
    (WorkflowRun, _RUN_FROZEN),
    (WorkflowStageRun, _STAGE_FROZEN),
):
    event.listen(model, "before_update", _guard(frozen))


@event.listens_for(WorkflowDefinition, "before_delete")
def _no_delete(_mapper, _connection, target):
    raise ImmutableRecord("workflow definitions are retired by status, never deleted")
