"""ALIVE-02 records extend the original identity, event, goal and memory stores."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid


class CognitiveControl(Base):
    __tablename__ = "cognitive_control"
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(default="stopped")
    provider: Mapped[str] = mapped_column(default="mock")
    session_id: Mapped[str] = mapped_column(default=uid)
    cursor: Mapped[int] = mapped_column(default=0)
    configuration: Mapped[dict] = mapped_column(J, default=dict)
    spent: Mapped[dict] = mapped_column(J, default=dict)
    reserved: Mapped[dict] = mapped_column(J, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CognitiveObservation(Base):
    __tablename__ = "cognitive_observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    source_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), unique=True)
    fingerprint: Mapped[str] = mapped_column(unique=True)
    content: Mapped[str] = mapped_column(Text)
    provenance: Mapped[dict] = mapped_column(J)
    attention: Mapped[dict] = mapped_column(J)
    status: Mapped[str] = mapped_column(default="OBSERVED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Investigation(Base):
    __tablename__ = "investigations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("cognitive_observations.id"), unique=True
    )
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"))
    state: Mapped[str] = mapped_column(default="SCHEDULED")
    snapshot: Mapped[dict] = mapped_column(J)
    history: Mapped[list] = mapped_column(J, default=list)
    budget: Mapped[dict] = mapped_column(J)
    usage: Mapped[dict] = mapped_column(J, default=dict)
    evaluation: Mapped[dict] = mapped_column(J, default=dict)
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ModelInvocation(Base):
    __tablename__ = "model_invocations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    role: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str]
    status: Mapped[str] = mapped_column(default="reserved")
    input_json: Mapped[dict] = mapped_column(J)
    output_json: Mapped[dict] = mapped_column(J, default=dict)
    usage: Mapped[dict] = mapped_column(J, default=dict)
    latency_ms: Mapped[float] = mapped_column(default=0)
    reserved_tokens: Mapped[int]
    error: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class CognitiveMessage(Base):
    __tablename__ = "cognitive_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    invocation_id: Mapped[str | None] = mapped_column(ForeignKey("model_invocations.id"))
    sender: Mapped[str]
    recipient: Mapped[str]
    message_type: Mapped[str]
    content: Mapped[dict] = mapped_column(J)
    schema_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ActionProposal(Base):
    __tablename__ = "action_proposals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True)
    kind: Mapped[str]
    risk_class: Mapped[str]
    status: Mapped[str] = mapped_column(default="proposed")
    proposal: Mapped[dict] = mapped_column(J)
    outcome: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Experience(Base):
    __tablename__ = "experiences"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    schema_version: Mapped[int] = mapped_column(default=1)
    data: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class MemoryVector(Base):
    __tablename__ = "memory_vectors"
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(primary_key=True)
    revision: Mapped[str] = mapped_column(primary_key=True)
    dimension: Mapped[int]
    values_json: Mapped[list] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HistoryImport(Base):
    __tablename__ = "history_imports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    status: Mapped[str] = mapped_column(default="preview")
    entries: Mapped[list] = mapped_column(J)
    memory_ids: Mapped[list] = mapped_column(J, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Laboratory(Base):
    __tablename__ = "laboratory_environments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    scenario: Mapped[str]
    state: Mapped[dict] = mapped_column(J)
    sources: Mapped[list] = mapped_column(J)
    version: Mapped[int] = mapped_column(default=1)
    draft: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
