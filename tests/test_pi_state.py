"""ALIVE-PI-01B: the Pi run and provider-request state machines and their durable records."""

import asyncio

import pytest
from sqlalchemy.exc import IntegrityError

from alive.db import Database
from alive.models import Base, Instance, uid
from alive.pi import states
from alive.pi.models import PiProviderRequest, PiRun


@pytest.mark.parametrize(
    "current,new",
    [
        (states.PREPARED, states.ADMITTED),
        (states.ADMITTED, states.STARTING),
        (states.STARTING, states.RUNNING),
        (states.RUNNING, states.SETTLED),
        (states.RUNNING, states.UNKNOWN),
        (states.PREPARED, states.CANCELLED),
        (states.ADMITTED, states.CANCELLED),
    ],
)
def test_legal_run_transitions(current, new):
    assert states.advance(current, new, states.RUN_TRANSITIONS) == new


@pytest.mark.parametrize(
    "current,new",
    [
        (states.PREPARED, states.RUNNING),  # nothing starts without admission
        (states.PREPARED, states.SETTLED),
        (states.ADMITTED, states.SETTLED),
        (states.STARTING, states.UNKNOWN),  # UNKNOWN only after Pi was actually running
        (states.SETTLED, states.FAILED),  # terminal states are final
        (states.FAILED, states.SETTLED),
        (states.CANCELLED, states.RUNNING),
        (states.UNKNOWN, states.SETTLED),
    ],
)
def test_illegal_run_transitions_are_refused(current, new):
    with pytest.raises(states.IllegalTransition):
        states.advance(current, new, states.RUN_TRANSITIONS)


def test_terminal_states_have_no_exits():
    for terminal in states.RUN_TERMINAL:
        assert terminal not in states.RUN_TRANSITIONS
    for terminal in states.REQUEST_TERMINAL:
        assert terminal not in states.REQUEST_TRANSITIONS


def test_a_request_must_be_dispatched_before_it_can_be_settled():
    # `dispatched` is the durable marker written before the upstream call. Skipping it would make
    # a crash between the call and its settlement indistinguishable from "never sent".
    with pytest.raises(states.IllegalTransition):
        states.advance(states.R_ADMITTED, states.R_SETTLED, states.REQUEST_TRANSITIONS)
    with pytest.raises(states.IllegalTransition):
        states.advance(states.R_ADMITTED, states.R_AMBIGUOUS, states.REQUEST_TRANSITIONS)
    assert (
        states.advance(states.R_ADMITTED, states.R_DISPATCHED, states.REQUEST_TRANSITIONS)
        == states.R_DISPATCHED
    )
    assert (
        states.advance(states.R_DISPATCHED, states.R_AMBIGUOUS, states.REQUEST_TRANSITIONS)
        == states.R_AMBIGUOUS
    )


def _db(tmp_path):
    return Database(f"sqlite+aiosqlite:///{tmp_path}/pi.db")


async def _prepare(db):
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    instance_id = uid()
    async with db.sessions.begin() as session:
        session.add(Instance(id=instance_id))
    return instance_id


def _run(instance_id, key="cognition.role:abc"):
    return PiRun(
        id=uid(),
        instance_id=instance_id,
        operation="cognition.role",
        idempotency_key=key,
        approved_request_json={"operation": "cognition.role"},
        approved_request_sha256="a" * 64,
        requested_json={"model": "m"},
        token_sha256="b" * 64,
    )


def test_unknown_usage_is_stored_as_null_never_zero(tmp_path):
    async def scenario():
        db = _db(tmp_path)
        instance_id = await _prepare(db)
        async with db.sessions.begin() as session:
            run = _run(instance_id)
            session.add(run)
            await session.flush()
            session.add(PiProviderRequest(run_id=run.id, seq=1))
            run_id = run.id
        async with db.sessions() as session:
            request = await session.scalar(
                __import__("sqlalchemy")
                .select(PiProviderRequest)
                .where(PiProviderRequest.run_id == run_id)
            )
            assert request.usage_json is None  # unknown, not {} and not zero
            assert request.latency_ms is None and request.http_status is None
            assert request.state == states.R_ADMITTED
        await db.engine.dispose()

    asyncio.run(scenario())


def test_one_run_per_idempotency_key(tmp_path):
    async def scenario():
        db = _db(tmp_path)
        instance_id = await _prepare(db)
        async with db.sessions.begin() as session:
            session.add(_run(instance_id))
        with pytest.raises(IntegrityError):
            async with db.sessions.begin() as session:
                session.add(_run(instance_id))  # same operation + reservation: never twice
        await db.engine.dispose()

    asyncio.run(scenario())


def test_request_sequence_numbers_are_unique_within_a_run(tmp_path):
    async def scenario():
        db = _db(tmp_path)
        instance_id = await _prepare(db)
        async with db.sessions.begin() as session:
            run = _run(instance_id)
            session.add(run)
            await session.flush()
            session.add(PiProviderRequest(run_id=run.id, seq=1))
            run_id = run.id
        with pytest.raises(IntegrityError):
            async with db.sessions.begin() as session:
                session.add(PiProviderRequest(run_id=run_id, seq=1))
        await db.engine.dispose()

    asyncio.run(scenario())


def test_the_run_token_is_stored_only_as_a_hash(tmp_path):
    assert "token" not in {c.name for c in PiRun.__table__.columns if c.name != "token_sha256"}
