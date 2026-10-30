"""ALIVE-PI-01B remediation: lifecycle ownership, dispatch fence, recovery, the 1-request cap.

These reproduce, as regressions, the orderings found by the independent review of b2208a8
(PIB-02..PIB-05). Each one used to leave a live run, dispatch after cancellation, mislabel an
ambiguous outcome, or allow a second provider request under one reservation.
"""

import asyncio
import contextlib

import httpx
import pytest
from sqlalchemy import select

from alive.config import Settings
from alive.models import uid
from alive.pi import states
from alive.pi.gateway import PiGateway
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runtime import recover
from alive.providers import ProviderError
from tests.test_pi_gateway import pi as pi  # noqa: F401  (re-exported fixtures)
from tests.test_pi_gateway import request, reservation, run_gateway
from tests.test_pi_gateway import settings as settings  # noqa: F401
from tests.test_pi_gateway import upstream as upstream  # noqa: F401


def snapshot(client):
    async def read():
        async with client.app.state.kernel.db.sessions() as session:
            out = []
            for run in (await session.scalars(select(PiRun))).all():
                rows = (
                    await session.scalars(
                        select(PiProviderRequest)
                        .where(PiProviderRequest.run_id == run.id)
                        .order_by(PiProviderRequest.seq)
                    )
                ).all()
                out.append(
                    (run.state, run.terminal_reason, [(r.state, r.error_category) for r in rows])
                )
            return out

    return client.portal.call(read)


def raises_cancelled(client, settings, req):
    """Run the gateway on the app's loop and require that it ends by re-raising the cancellation."""

    async def go():
        with pytest.raises(asyncio.CancelledError):
            await PiGateway(settings, "cognition.role").structured(req)

    client.portal.call(go)


def cancel_at(client, settings, req, ready):
    """Start the gateway, cancel it once `ready` is set, and wait for it to finish."""

    async def go():
        worker = asyncio.create_task(PiGateway(settings, "cognition.role").structured(req))
        await asyncio.wait_for(ready.wait(), 10)
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        return worker.cancelled()

    return client.portal.call(go)


# --- PIB-02: cancellation after ANY durable transition leaves a t ---


@pytest.mark.parametrize("after", [states.PREPARED, states.ADMITTED, states.STARTING])
def test_cancel_after_every_durable_transition_ends_terminal(
    client, settings, upstream, pi, monkeypatch, after
):
    req = request(reservation(client))
    reached = asyncio.Event()
    if after == states.PREPARED:
        original_prepare = PiGateway._prepare

        async def gated_prepare(self, *args):
            await original_prepare(self, *args)  # the PREPARED row is committed ...
            reached.set()
            await asyncio.Event().wait()  # ... and the cancel lands before anything else runs

        monkeypatch.setattr(PiGateway, "_prepare", gated_prepare)
    else:
        original_update = PiGateway._update

        async def gated_update(self, *args, **kwargs):
            await original_update(self, *args, **kwargs)
            if kwargs["state"] == after:
                reached.set()
                await asyncio.Event().wait()

        monkeypatch.setattr(PiGateway, "_update", gated_update)
    assert cancel_at(client, settings, req, reached) is True
    ((state, reason, rows),) = snapshot(client)
    assert state == states.CANCELLED and reason == "cancelled_before_dispatch"
    assert rows == [] and upstream.calls == []
    assert pi.egress.contexts == {}  # and the run token is gone


def test_a_cancel_that_lands_as_the_first_commit_returns_still_reconciles(
    client, settings, upstream, pi, monkeypatch
):
    """Cancellation delivered the instant PREPARED is durable (nothing awaited in between)."""
    original = PiGateway._prepare

    async def prepare_then_cancel(self, *args):
        await original(self, *args)
        raise asyncio.CancelledError()

    monkeypatch.setattr(PiGateway, "_prepare", prepare_then_cancel)
    raises_cancelled(client, settings, request(reservation(client)))
    ((state, reason, _),) = snapshot(client)
    assert state == states.CANCELLED and reason == "cancelled_before_dispatch"


def test_an_unexpected_error_after_admission_also_ends_terminal(
    client, settings, upstream, pi, monkeypatch
):
    async def explode(*args, **kwargs):
        raise RuntimeError("egress would not start")

    monkeypatch.setattr(type(pi), "ensure_egress", explode)
    with pytest.raises(RuntimeError):
        run_gateway(client, settings, request(reservation(client)))
    ((state, reason, rows),) = snapshot(client)
    assert (state, reason, rows) == (states.FAILED, "pi_internal_error", [])


# --- PIB-03: no request is left admitted, and none can dispatch a ---


def stub_runner(pi, monkeypatch, body):
    async def runner(**kwargs):
        await kwargs["on_running"]()
        ctx = pi.egress.context_for("Bearer " + kwargs["token"])
        await body(kwargs, ctx)

    monkeypatch.setattr(pi.runner, "run", runner)


def chat_body(ctx):
    return {"stream": True, "messages": [{"role": "user", "content": ctx.prompt_text}]}


def test_an_admitted_slot_that_never_dispatched_is_rejected_when_the_run_ends(
    client, settings, upstream, pi, monkeypatch
):
    async def body(kwargs, ctx):
        outcome, _ = await pi.egress._admit(ctx, "a" * 64, chat_body(ctx), None)
        assert outcome == "admitted"
        raise asyncio.CancelledError()

    stub_runner(pi, monkeypatch, body)
    raises_cancelled(client, settings, request(reservation(client)))
    ((state, reason, rows),) = snapshot(client)
    assert state == states.CANCELLED and reason == "cancelled_before_dispatch"
    assert rows == [(states.R_REJECTED, "cancelled_before_dispatch")]
    client.portal.call(lambda: recover(client.app.state.kernel))
    assert snapshot(client) == [(state, reason, rows)]  # nothing left for recovery to repair
    assert upstream.calls == []


def test_a_handler_that_was_admitted_cannot_dispatch_after_the_run_is_cancelled(
    client, settings, upstream, pi, monkeypatch
):
    reached, release = asyncio.Event(), asyncio.Event()
    original = pi.egress._dispatch

    async def gated_dispatch(request_id):
        reached.set()
        await release.wait()  # admitted, paused exactly at the dispatch boundary
        return await original(request_id)

    monkeypatch.setattr(pi.egress, "_dispatch", gated_dispatch)
    calls = []

    async def body(kwargs, ctx):
        async def http():
            async with httpx.AsyncClient(timeout=10) as http_client:
                return await http_client.post(
                    pi.egress.base_url + "/chat/completions",
                    headers={"Authorization": "Bearer " + kwargs["token"]},
                    json=chat_body(ctx),
                )

        calls.append(asyncio.create_task(http()))
        await asyncio.wait_for(reached.wait(), 10)
        raise asyncio.CancelledError()

    stub_runner(pi, monkeypatch, body)
    reservation_id = reservation(client)

    async def go():
        try:
            with pytest.raises(asyncio.CancelledError):
                await PiGateway(settings, "cognition.role").structured(request(reservation_id))
        finally:
            release.set()
        return await asyncio.wait_for(calls[0], 10)

    response = client.portal.call(go)
    assert response.status_code == 409  # refused: the run no longer holds authority
    assert upstream.calls == []  # and the provider was never called
    ((state, reason, rows),) = snapshot(client)
    assert state == states.CANCELLED and reason == "cancelled_before_dispatch"
    assert rows == [(states.R_REJECTED, "cancelled_before_dispatch")]


def test_a_dispatch_that_won_the_race_is_ambiguous_and_the_run_unknown(
    client, settings, upstream, pi, monkeypatch
):
    upstream.block = asyncio.Event()  # the provider call is in flight and never returns
    ready = asyncio.Event()
    original = pi.egress._dispatch

    async def noting(request_id):
        outcome = await original(request_id)
        ready.set()
        return outcome

    monkeypatch.setattr(pi.egress, "_dispatch", noting)
    monkeypatch.setattr("alive.pi.gateway.SETTLE_WAIT_SECONDS", 0.2)
    assert cancel_at(client, settings, request(reservation(client)), ready) is True
    ((state, reason, rows),) = snapshot(client)
    assert (state, reason) == (states.UNKNOWN, "cancelled_after_possible_dispatch")
    assert [r[0] for r in rows] == [states.R_AMBIGUOUS]


# --- PIB-04: recovery ---

RUN_STATES = [
    states.PREPARED,
    states.ADMITTED,
    states.STARTING,
    states.RUNNING,
    states.SETTLED,
    states.FAILED,
    states.CANCELLED,
    states.UNKNOWN,
]
REQUEST_STATES = [
    None,
    states.R_ADMITTED,
    states.R_DISPATCHED,
    states.R_SETTLED,
    states.R_FAILED,
    states.R_AMBIGUOUS,
    states.R_REJECTED,
]


def test_recovery_leaves_nothing_pending_and_never_downgrades_a_possible_dispatch(client):
    async def scenario():
        k = client.app.state.kernel
        seeded = []
        async with k.lock, k.db.sessions.begin() as session:
            for run_state in RUN_STATES:
                for request_state in REQUEST_STATES:
                    run = PiRun(
                        id=uid(),
                        instance_id=k.instance_id,
                        operation="cognition.role",
                        idempotency_key=uid(),
                        state=run_state,
                        approved_request_json={},
                        approved_request_sha256="a" * 64,
                        requested_json={},
                        token_sha256="b" * 64,
                    )
                    session.add(run)
                    await session.flush()
                    if request_state:
                        session.add(PiProviderRequest(run_id=run.id, seq=1, state=request_state))
                    seeded.append((run.id, run_state, request_state))
        await recover(k)
        await recover(k)  # and it is idempotent
        out = []
        async with k.db.sessions() as session:
            for run_id, run_state, request_state in seeded:
                run = await session.get(PiRun, run_id)
                row = await session.scalar(
                    select(PiProviderRequest).where(PiProviderRequest.run_id == run_id)
                )
                out.append((run_state, request_state, run.state, row.state if row else None))
        return out

    rows = client.portal.call(scenario)
    assert len(rows) == len(RUN_STATES) * len(REQUEST_STATES)
    for run_before, request_before, run_after, request_after in rows:
        label = (run_before, request_before)
        assert run_after in states.RUN_TERMINAL, label  # no live run survives recovery
        assert request_after in (None, *states.REQUEST_TERMINAL), label  # nor a pending request
        if run_before in states.RUN_TERMINAL:
            assert run_after == run_before, label  # a terminal run is never rewritten
        elif request_before in (states.R_DISPATCHED, states.R_AMBIGUOUS):
            assert run_after == states.UNKNOWN, label  # it may have reached the provider
        else:
            assert run_after == states.CANCELLED, label
        if request_before == states.R_DISPATCHED:
            assert request_after == states.R_AMBIGUOUS, label
        if request_before == states.R_ADMITTED:
            assert request_after == states.R_REJECTED, label  # never sent: never ambiguous


# --- PIB-05: one reservation, one provider request, in every acce ---


def test_the_provider_request_ceiling_cannot_be_raised_above_one(client, settings, upstream, pi):
    with pytest.raises(ValueError):
        Settings(_env_file=None, alive_pi_max_provider_requests=2)
    settings.alive_pi_max_provider_requests = 2  # even if a settings object is mutated afterwards
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), "GATEWAY:multi 2 x"))
    assert error.value.category == "pi_config_invalid"
    assert snapshot(client) == [] and upstream.calls == []  # refused before any durable state


def test_dispatch_refuses_an_admitted_slot_whose_run_is_no_longer_running(
    client, settings, upstream, pi, monkeypatch
):
    """The run-state check on its own: no other guard (settlement) has reconciled the slot."""

    async def body(kwargs, ctx):
        outcome, request_id = await pi.egress._admit(ctx, "a" * 64, chat_body(ctx), None)
        assert outcome == "admitted"
        k = client.app.state.kernel
        async with k.lock, k.db.sessions.begin() as session:
            (await session.get(PiRun, ctx.run_id)).state = states.CANCELLED
        assert await pi.egress._dispatch(request_id) is False
        raise asyncio.CancelledError()

    stub_runner(pi, monkeypatch, body)
    raises_cancelled(client, settings, request(reservation(client)))
    ((state, _, rows),) = snapshot(client)
    assert state == states.CANCELLED
    assert rows == [(states.R_REJECTED, "run_not_running")]
    assert upstream.calls == []
