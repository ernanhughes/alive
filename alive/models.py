import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


J = JSON().with_variant(JSONB(), "postgresql")


class Instance(Base):
    __tablename__ = "alive_instances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(default="ALIVE-01")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    lifecycle_state: Mapped[str] = mapped_column(default="suspended")
    configuration: Mapped[dict] = mapped_column(J, default=dict)
    version: Mapped[int] = mapped_column(default=1)


class Event(Base):
    __tablename__ = "events"
    sequence_number: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    event_type: Mapped[str] = mapped_column(index=True)
    source: Mapped[str]
    correlation_id: Mapped[str] = mapped_column(index=True)
    causation_id: Mapped[str | None]
    schema_version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(J)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_events_instance_sequence", "instance_id", "sequence_number"),)


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    memory_type: Mapped[str] = mapped_column(default="experience")
    source_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"), unique=True)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    metadata_json: Mapped[dict] = mapped_column("metadata", J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Goal(Base):
    __tablename__ = "goals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    title: Mapped[str]
    description: Mapped[str] = mapped_column(Text, default="")
    origin: Mapped[str] = mapped_column(default="user")
    priority: Mapped[int] = mapped_column(default=50)
    status: Mapped[str] = mapped_column(default="proposed")
    parent_goal_id: Mapped[str | None] = mapped_column(ForeignKey("goals.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    runner: Mapped[str]
    model_provider: Mapped[str]
    model_id: Mapped[str]
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[dict] = mapped_column(J, default=dict)


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    session_type: Mapped[str] = mapped_column(default="managed")
    status: Mapped[str] = mapped_column(default="open")
    current_url: Mapped[str] = mapped_column(default="about:blank")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RuntimeState(Base):
    __tablename__ = "runtime_state"
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), primary_key=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_goals: Mapped[list] = mapped_column(J, default=list)
    resource_budget: Mapped[dict] = mapped_column(J, default=lambda: {"agent_concurrency": 1})
    state_version: Mapped[int] = mapped_column(default=1)
    observation_hashes: Mapped[list] = mapped_column(J, default=list)


def record(obj):
    return {
        c.key: getattr(obj, c.key if c.key != "metadata" else "metadata_json")
        for c in obj.__table__.columns
    }
