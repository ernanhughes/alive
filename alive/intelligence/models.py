"""INT-02 durable records. Import explicitly at application setup, never package import."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.workflows.models import ImmutableRecord


class IntelligenceState(Base):
    __tablename__ = "intelligence_states"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"))
    active_json: Mapped[dict] = mapped_column(J)
    active_hash: Mapped[str] = mapped_column(String(64))
    candidate_json: Mapped[dict] = mapped_column(J)
    candidate_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    quarantined: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("revision >= 0", name="ck_intelligence_revision"),)


class IntelligenceEpisode(Base):
    """One immutable proposal/decision snapshot, optionally linked to an earlier assessment."""

    __tablename__ = "intelligence_episodes"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    state_id: Mapped[str] = mapped_column(ForeignKey("intelligence_states.id"), index=True)
    workflow_stage_id: Mapped[str] = mapped_column(ForeignKey("workflow_stage_runs.id"))
    source_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), unique=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    context_hash: Mapped[str] = mapped_column(String(64))
    snapshot_json: Mapped[dict] = mapped_column(J)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    proposal_id: Mapped[str] = mapped_column(String(100), unique=True)
    proposed_action: Mapped[str | None] = mapped_column(String(20))
    active_choice: Mapped[str | None] = mapped_column(String(20))
    shadow_action: Mapped[str | None] = mapped_column(String(20))
    authorized_action: Mapped[str | None] = mapped_column(String(20))
    executed_action: Mapped[str | None] = mapped_column(String(20))
    model_invocation_id: Mapped[str | None] = mapped_column(ForeignKey("model_invocations.id"))
    pi_run_id: Mapped[str | None] = mapped_column(ForeignKey("pi_runs.id"))
    previous_id: Mapped[str | None] = mapped_column(ForeignKey("intelligence_episodes.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint(
            "authorized_action IS NULL AND executed_action IS NULL",
            name="ck_intelligence_advisory_only",
        ),
    )


class IntelligenceFeedback(Base):
    __tablename__ = "intelligence_feedback"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("intelligence_episodes.id"), unique=True)
    source_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), unique=True)
    outcome_hash: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(J)
    authority_class: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IntelligenceLearningUpdate(Base):
    __tablename__ = "intelligence_learning_updates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    state_id: Mapped[str] = mapped_column(ForeignKey("intelligence_states.id"), index=True)
    feedback_id: Mapped[str] = mapped_column(ForeignKey("intelligence_feedback.id"), unique=True)
    algorithm: Mapped[str] = mapped_column(String(64))
    before_json: Mapped[dict] = mapped_column(J)
    before_hash: Mapped[str] = mapped_column(String(64))
    after_json: Mapped[dict] = mapped_column(J)
    after_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class IntelligenceMeasurementUse(Base):
    """Identity-only consumption ledger, not another evidence content store."""

    __tablename__ = "intelligence_measurement_uses"
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    observation_hash: Mapped[str] = mapped_column(String(64))
    feedback_id: Mapped[str] = mapped_column(ForeignKey("intelligence_feedback.id"))
    __table_args__ = (
        UniqueConstraint("instance_id", "observation_hash", name="uq_intelligence_measurement_use"),
    )


def immutable(_mapper, _connection, _target):
    raise ImmutableRecord("Intelligence history is append-only")


for model in (
    IntelligenceEpisode,
    IntelligenceFeedback,
    IntelligenceLearningUpdate,
    IntelligenceMeasurementUse,
):
    event.listen(model, "before_update", immutable)
    event.listen(model, "before_delete", immutable)


@event.listens_for(IntelligenceState, "before_update")
def frozen_active(_mapper, _connection, target):
    from sqlalchemy import inspect

    state = inspect(target)
    for column in ("id", "instance_id", "goal_id", "active_json", "active_hash", "created_at"):
        if state.attrs[column].history.has_changes():
            raise ImmutableRecord("Active policy and learning identity are frozen")
