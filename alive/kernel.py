import asyncio
import contextlib
import hashlib
from datetime import UTC
from pathlib import Path

from sqlalchemy import select, text, update

from alive.models import (
    AgentRun,
    BrowserSession,
    Event,
    Goal,
    Instance,
    Memory,
    RuntimeState,
    now,
    record,
    uid,
)
from alive.schemas import EventEnvelope


def public_payload(event_type, payload):
    """What the generic feed (REST, WebSocket, live publish) may carry.

    Run history keeps each stage's output in the database: dependencies, hashing and replay need it.
    The feed carries only the stage's identity, so approved source content that a capability
    returned (for example repository files) is not broadcast to every authenticated reader.
    """
    if event_type == "workflow.stage.result" and isinstance(payload, dict):
        return {k: payload[k] for k in ("run_id", "stage_id") if k in payload} | {
            "output_withheld": True
        }
    return payload


def envelope(row):
    return EventEnvelope(
        event_id=row.id,
        instance_id=row.instance_id,
        event_type=row.event_type,
        source=row.source,
        correlation_id=row.correlation_id,
        causation_id=row.causation_id,
        timestamp=(
            row.occurred_at.replace(tzinfo=UTC)
            if row.occurred_at.tzinfo is None
            else row.occurred_at
        ),
        payload=public_payload(row.event_type, row.payload),
    ).model_dump(mode="json") | {"sequence_number": row.sequence_number}


class Kernel:
    def __init__(self, db, transport, settings):
        self.db, self.transport, self.settings = db, transport, settings
        self.lock = asyncio.Lock()
        self.instance_id = None
        self.ready = False
        self.error = None
        self.vector_storage = False
        self.tasks = []
        self.lease = None
        self.lock_file = None

    async def initialize(self):
        try:
            self.vector_storage = await self.db.probe()
            # Own one scheduler per database, including across backend processes.
            if self.db.pg:
                self.lease = await self.db.engine.connect()
                if not await self.lease.scalar(text("SELECT pg_try_advisory_lock(410101)")):
                    raise RuntimeError("Another ALIVE process owns this database")
            else:
                from filelock import FileLock

                path = self.db.engine.url.database
                self.lock_file = FileLock(str(Path(path).with_suffix(".runtime.lock")))
                self.lock_file.acquire(timeout=0)
            async with self.db.sessions.begin() as session:
                instance = await session.scalar(select(Instance))
                if not instance:
                    instance = Instance(id=uid())
                    session.add(instance)
                    await session.flush()
                    session.add(RuntimeState(instance_id=instance.id))
                self.instance_id = instance.id
                self.add_event(session, "alive.started", {"identity": instance.id})
                await session.execute(
                    update(AgentRun)
                    .where(AgentRun.status == "running")
                    .values(
                        status="failed",
                        error="Runtime restarted during execution",
                        completed_at=now(),
                    )
                )
                await session.execute(
                    update(BrowserSession)
                    .where(BrowserSession.status == "open")
                    .values(status="closed", updated_at=now())
                )
            self.ready = True
            self.tasks = [asyncio.create_task(self.heartbeat()), asyncio.create_task(self.outbox())]
            for task in self.tasks:
                task.add_done_callback(self.background_completed)
        except Exception as exc:
            # Do not echo database URLs or driver errors containing credentials.
            self.error = (
                f"{type(exc).__name__}: database, migrations or runtime ownership unavailable"
            )

    def background_completed(self, task):
        if not task.cancelled() and task.exception():
            self.ready = False
            self.error = "Runtime background worker failed; restore infrastructure and restart"

    def add_event(
        self,
        session,
        event_type,
        payload=None,
        source="kernel",
        correlation=None,
        cause=None,
        event_id=None,
    ):
        event = EventEnvelope(
            event_id=event_id or uid(),
            instance_id=self.instance_id,
            event_type=event_type,
            source=source,
            correlation_id=correlation or uid(),
            causation_id=cause,
            payload=payload or {},
        )
        session.add(
            Event(
                id=str(event.event_id),
                instance_id=self.instance_id,
                event_type=event.event_type,
                source=source,
                correlation_id=str(event.correlation_id),
                causation_id=str(event.causation_id) if event.causation_id else None,
                payload=event.payload,
                occurred_at=event.timestamp,
            )
        )
        return event

    async def emit(self, event_type, payload=None, **kwargs):
        async with self.lock, self.db.sessions.begin() as session:
            return self.add_event(session, event_type, payload, **kwargs)

    async def ingest(self, observation):
        async with self.lock, self.db.sessions.begin() as session:
            existing = await session.scalar(
                select(Event).where(Event.id == str(observation.event_id))
            )
            if existing:
                return {"event_id": existing.id, "duplicate": True}
            event = self.add_event(
                session,
                observation.event_type,
                observation.payload,
                source=observation.source,
                event_id=str(observation.event_id),
                correlation=str(observation.correlation_id),
                cause=str(observation.causation_id) if observation.causation_id else None,
            )
            await session.flush()
            content = str(observation.payload.get("text", ""))[:8000]
            fingerprint = hashlib.sha256(content.encode()).hexdigest()
            state = await session.get(RuntimeState, self.instance_id)
            instance = await session.get(Instance, self.instance_id)
            if content and fingerprint not in state.observation_hashes:
                state.observation_hashes = (state.observation_hashes + [fingerprint])[-200:]
                memory = Memory(
                    id=uid(),
                    instance_id=self.instance_id,
                    content=content,
                    source_event_id=str(event.event_id),
                    metadata_json={"url": observation.payload.get("url"), "drive": "curiosity"},
                )
                session.add(memory)
                self.add_event(
                    session,
                    "memory.created",
                    {"memory_id": memory.id},
                    correlation=str(event.correlation_id),
                    cause=str(event.event_id),
                )
                if instance.lifecycle_state == "running" and not getattr(
                    self, "cognition_enabled", False
                ):
                    goal = Goal(
                        id=uid(),
                        instance_id=self.instance_id,
                        title="Investigate novel observation",
                        description=content[:2000],
                        origin="curiosity",
                    )
                    session.add(goal)
                    self.add_event(
                        session,
                        "goal.proposed",
                        {"goal_id": goal.id, "drive": "curiosity"},
                        correlation=str(event.correlation_id),
                        cause=str(event.event_id),
                    )
            elif content:
                self.add_event(
                    session,
                    "alive.observation_repeated",
                    {"drive": "coherence"},
                    correlation=str(event.correlation_id),
                    cause=str(event.event_id),
                )
            expected = observation.payload.get("expected_text")
            if expected is not None and expected != content:
                self.add_event(
                    session,
                    "alive.state_unexpected",
                    {"drive": "coherence"},
                    correlation=str(event.correlation_id),
                    cause=str(event.event_id),
                )
            state.state_version += 1
            return {"event_id": str(event.event_id), "duplicate": False}

    async def set_running(self, running):
        async with self.lock, self.db.sessions.begin() as session:
            instance = await session.get(Instance, self.instance_id)
            target = "running" if running else "suspended"
            if instance.lifecycle_state != target:
                instance.lifecycle_state = target
                self.add_event(session, "alive.resumed" if running else "alive.suspended")
            return record(instance)

    async def heartbeat(self):
        while True:
            await asyncio.sleep(self.settings.alive_heartbeat_seconds)
            if self.db.pg:
                # A lost advisory-lock connection must stop this scheduler.
                await self.lease.execute(text("SELECT 1"))
            async with self.lock, self.db.sessions.begin() as session:
                instance = await session.get(Instance, self.instance_id)
                if instance.lifecycle_state != "running":
                    continue
                state = await session.get(RuntimeState, self.instance_id)
                state.heartbeat_at = instance.last_active_at = now()
                state.state_version += 1
                state.active_goals = list(
                    (
                        await session.scalars(
                            select(Goal.id).where(Goal.status.in_(["accepted", "active"]))
                        )
                    ).all()
                )
                self.add_event(
                    session,
                    "alive.heartbeat",
                    {
                        "state_version": state.state_version,
                        "drive": "commitment",
                        "unfinished_goals": len(state.active_goals),
                    },
                )

    async def outbox(self):
        while True:
            async with self.lock, self.db.sessions.begin() as session:
                rows = (
                    await session.scalars(
                        select(Event)
                        .where(Event.published_at.is_(None))
                        .order_by(Event.sequence_number)
                        .limit(100)
                    )
                ).all()
                for row in rows:
                    await self.transport.publish(envelope(row))
                    # This marks a publication attempt, never subscriber acknowledgement.
                    row.published_at = now()
            await asyncio.sleep(0.1)

    async def state(self):
        async with self.db.sessions() as session:
            instance = await session.get(Instance, self.instance_id)
            state = await session.get(RuntimeState, self.instance_id)
            return {
                "identity": record(instance),
                "runtime": record(state),
                "drives": {
                    "curiosity": "Novel text creates a memory and proposed goal while running",
                    "coherence": "Repeated observations and expectation mismatches are recorded",
                    "commitment": "Heartbeat tracks accepted unfinished goals",
                },
            }

    async def close(self):
        for task in self.tasks:
            task.cancel()
        for task in self.tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self.lease:
            with contextlib.suppress(Exception):
                await self.lease.execute(text("SELECT pg_advisory_unlock(410101)"))
            await self.lease.close()
        if self.lock_file:
            self.lock_file.release()
        await self.db.engine.dispose()
