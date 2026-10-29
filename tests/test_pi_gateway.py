"""ALIVE-PI-01B: PiGateway end to end: admission, settlement, recovery, cancellation, receipts."""

import asyncio
import contextlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.config import Settings
from alive.model_gateway import DirectMetaGateway, StructuredRequest, gateway_for
from alive.models import uid
from alive.pi import gateway as gateway_module
from alive.pi import states
from alive.pi.gateway import PiGateway
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runner import PiInstall, PiRunner
from alive.pi.runtime import PiRuntime, set_runtime
from alive.providers import MetaProvider, ProviderError
from alive.society import mock_role, role_prompt
from tests.conftest import TOKEN
from tests.test_cognition import completed, observe
from tests.test_recovery_budgets import seed_run

FAKE = str(Path(__file__).resolve().parent / "fixtures" / "fake_pi.py")
REAL_KEY = "sk-real-meta-credential-that-pi-must-never-see"
ROLES = ("observer", "proposer", "critic", "evaluator")
ROLES = ("observer", "proposer", "critic", "evaluator")
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.fixture
def settings(settings):
    settings.alive_meta_api_key = REAL_KEY
    settings.alive_model_transport = "pi"
    settings.alive_pi_run_deadline = 20
    return settings


@pytest.fixture(autouse=True)
def quick_settle(monkeypatch):
    monkeypatch.setattr(gateway_module, "SETTLE_WAIT_SECONDS", 0.5)


class Upstream:
    """A scripted provider: valid cognition role outputs by default, or whatever a test installs."""

    def __init__(self):
        self.calls = []
        self.respond = self.role_output
        self.block = None

    async def handle(self, request):
        body = json.loads(request.content)
        self.calls.append({"headers": dict(request.headers), "body": body})
        if self.block is not None:
            await self.block.wait()
        return self.respond(body)

    @staticmethod
    def role_output(body):
        instructions = body["messages"][0]["content"]
        role = next((r for r in ROLES if role_prompt(r) == instructions), None)
        if role is None:  # a plain request that is not a cognition role
            content = '{"answer":"ok"}'
        else:
            content = mock_role(role, json.loads(body["messages"][1]["content"])).model_dump_json()
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": USAGE,
            },
        )


def use_pi(client, settings, upstream, *, install=None):
    runtime = PiRuntime(
        client.app.state.kernel,
        settings,
        runner=PiRunner(
            settings, install=install or PiInstall(sys.executable, FAKE, "1.4.0", "f" * 64)
        ),
        upstream_transport=httpx.MockTransport(upstream.handle),
    )
    client.app.state.pi = runtime
    set_runtime(runtime)
    return runtime


@pytest.fixture
def upstream():
    return Upstream()


@pytest.fixture
def pi(client, settings, upstream):
    runtime = use_pi(client, settings, upstream)
    yield runtime
    if client.portal is not None:  # a restart test already closed the app (and so this runtime)
        client.portal.call(runtime.close)


def reservation(client):
    """An existing Governor reservation (a `reserved` ModelInvocation) to run under."""
    run_id = seed_run(client, status="reserved")
    return client.get("/api/v1/cognition/investigations/" + run_id).json()["invocations"][0]["id"]


def request(correlation, instructions="Answer briefly.", **over):
    base = dict(
        operation="cognition.role",
        instructions=instructions,
        data={"question": "what changed?"},
        schema={"type": "object"},
        model="muse-approved",
        max_output=256,
        correlation=correlation,
    )
    return StructuredRequest(**(base | over))


def run_gateway(client, settings, req):
    return client.portal.call(lambda: PiGateway(settings, "cognition.role").structured(req))


def db(client, fn):
    async def read():
        async with client.app.state.kernel.db.sessions() as session:
            return await fn(session)

    return client.portal.call(read)


def runs(client):
    async def fn(session):
        out = []
        for run in (await session.scalars(select(PiRun).order_by(PiRun.created_at))).all():
            rows = (
                await session.scalars(
                    select(PiProviderRequest)
                    .where(PiProviderRequest.run_id == run.id)
                    .order_by(PiProviderRequest.seq)
                )
            ).all()
            out.append((run, rows))
        return out

    return db(client, fn)


def only_run(client):
    ((run, requests),) = runs(client)
    return run, requests


def meta_available(monkeypatch):
    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    monkeypatch.setattr(MetaProvider, "discover", discover)


# --- the headline: an existing cognition operation runs through Pi ----


def test_a_cognition_role_runs_through_pi_end_to_end(client, settings, upstream, pi, monkeypatch):
    meta_available(monkeypatch)
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert run["state"] in {"COMPLETED", "ABSTAINED"}, run["error"]
    assert run["invocations"] and all(c["status"] == "validated" for c in run["invocations"])
    pi_runs = runs(client)
    assert len(pi_runs) == len(run["invocations"]) == len(upstream.calls)  # one Pi run per call
    for (pi_run, requests), call in zip(pi_runs, run["invocations"], strict=True):
        assert pi_run.state == states.SETTLED and pi_run.reservation_ref == call["id"]
        assert [r.state for r in requests] == [states.R_SETTLED]
    # The cognition contract is unchanged: the invocation id is still the upstream correlation.
    assert [c["headers"]["x-request-id"] for c in upstream.calls] == [
        c["id"] for c in run["invocations"]
    ]
    assert all(c["headers"]["authorization"] == f"Bearer {REAL_KEY}" for c in upstream.calls)


def test_the_default_transport_is_direct_and_loads_no_pi_code(settings):
    assert Settings(_env_file=None).alive_model_transport == "direct"
    direct = Settings(_env_file=None, alive_model_transport="direct")
    assert isinstance(gateway_for(direct, "cognition.role"), DirectMetaGateway)
    assert isinstance(gateway_for(settings, "cognition.role"), PiGateway)
    with pytest.raises(ValueError):
        Settings(_env_file=None, alive_model_transport="pie")  # a typo cannot select the wrong path
    code = (
        "import sys; from alive.config import Settings;"
        "from alive.model_gateway import gateway_for;"
        "gateway_for(Settings(_env_file=None), 'cognition.role');"
        "print('alive.pi.gateway' in sys.modules)"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


# --- admission and idempotency ----------------------------------------


def test_no_reservation_means_no_run_and_no_dispatch(client, settings, upstream, pi):
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(uid()))  # a reservation that does not exist
    assert error.value.category == "pi_no_reservation"
    assert runs(client) == [] and upstream.calls == []
    with pytest.raises(ProviderError) as missing:
        run_gateway(client, settings, request(None))
    assert missing.value.category == "pi_no_reservation"


def test_a_reservation_is_never_dispatched_twice(client, settings, upstream, pi):
    reservation_id = reservation(client)
    first = run_gateway(client, settings, request(reservation_id))
    assert first.text == '{"answer":"ok"}' and first.usage == USAGE  # settled once
    with pytest.raises(ProviderError) as again:
        run_gateway(client, settings, request(reservation_id))
    assert again.value.category == "ambiguous_settlement"
    assert len(upstream.calls) == 1  # the second attempt never reached Pi or upstream


def test_idempotency_survives_an_app_restart(client, settings, upstream, pi):
    reservation_id = reservation(client)
    run_gateway(client, settings, request(reservation_id))
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        runtime = use_pi(reopened, settings, upstream)
        with pytest.raises(ProviderError) as again:
            reopened.portal.call(
                lambda: PiGateway(settings, "cognition.role").structured(request(reservation_id))
            )
        reopened.portal.call(runtime.close)
    # Restart reconciled the reservation (reserved -> interrupted), so the gateway fails closed.
    assert again.value.category == "pi_no_reservation" and len(upstream.calls) == 1


# --- typed failures ----------------------------------------


@pytest.mark.parametrize(
    "instructions,category,state",
    [
        ("GATEWAY:crash x", "pi_process_exited", states.FAILED),
        ("GATEWAY:handled x", "pi_prompt_handled", states.FAILED),
        ("GATEWAY:reject x", "pi_prompt_rejected", states.FAILED),
        ("GATEWAY:flood x", "pi_protocol_error", states.FAILED),
        ("GATEWAY:mismatch-prompt x", "pi_unexpected_requests", states.FAILED),
    ],
)
def test_pi_failures_are_typed_recorded_and_never_dispatch_upstream(
    client, settings, upstream, pi, instructions, category, state
):
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), instructions))
    assert error.value.category == category
    run, requests = only_run(client)
    assert run.state == state and run.terminal_reason == category
    assert upstream.calls == []
    assert run.result_json["cleanup_confirmed"] is True


def test_a_pi_that_never_settles_hits_the_deadline_and_is_cleaned_up(
    client, settings, upstream, pi
):
    settings.alive_pi_run_deadline = 1.5
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), "GATEWAY:no-settle x"))
    assert error.value.category == "pi_deadline"
    run, _ = only_run(client)
    assert run.state == states.FAILED and run.result_json["cleanup_confirmed"] is True


def test_extra_pi_requests_fail_the_run_even_though_one_dispatch_was_paid_for(
    client, settings, upstream, pi
):
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), "GATEWAY:multi 3 x"))
    assert error.value.category == "pi_unexpected_requests"
    assert error.value.usage == USAGE  # the spent usage is carried, not dropped
    run, requests = only_run(client)
    assert len(upstream.calls) == 1 and run.state == states.FAILED
    assert [r.state for r in requests].count(states.R_REJECTED) == 2


class Tweaked(PiRunner):
    """A runner whose result is altered after a real run: the gateway must re-check it."""

    def __init__(self, settings, install, **changes):
        super().__init__(settings, install=install)
        self.changes = changes

    async def run(self, **kw):
        result = await super().run(**kw)
        for name, value in self.changes.items():
            setattr(result, name, value)
        return result


@pytest.mark.parametrize(
    "changes,category",
    [
        ({"cleanup_confirmed": False}, "pi_cleanup_unconfirmed"),
        ({"stop_reason": "length"}, "pi_model_error"),
        ({"settled": False}, "pi_not_settled"),
    ],
)
def test_the_gateway_rechecks_what_the_runner_reports(
    client, settings, upstream, pi, changes, category
):
    pi.runner = Tweaked(settings, PiInstall(sys.executable, FAKE, "1.4.0", "f" * 64), **changes)
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client)))
    assert error.value.category == category
    run, _ = only_run(client)
    assert run.state == states.FAILED and run.terminal_reason == category
    assert error.value.usage == USAGE  # the dispatched call was paid for, whatever Pi reported


def test_tool_activity_fails_the_run(client, settings, upstream, pi):
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), "GATEWAY:tool x"))
    assert error.value.category == "pi_tool_activity"
    assert only_run(client)[0].result_json["tool_events"] == 1


def test_pi_changing_the_text_it_was_given_is_caught_and_the_spend_is_kept(
    client, settings, upstream, pi
):
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client), "GATEWAY:tamper x"))
    assert error.value.category == "invalid_response" and error.value.response_received is True
    assert error.value.usage == USAGE  # the provider call happened and was paid for
    run, _ = only_run(client)
    assert (
        run.terminal_reason == "pi_output_mismatch"
        and run.result_json["matches_egress_record"] is False
    )


@pytest.mark.parametrize(
    "response,category,run_state,request_state",
    [
        (lambda b: httpx.Response(401, json={}), "authentication", states.FAILED, states.R_FAILED),
        (lambda b: httpx.Response(500, json={}), "server_error", states.FAILED, states.R_FAILED),
        (
            lambda b: httpx.Response(200, json={"x": 1}),
            "invalid_response",
            states.FAILED,
            states.R_FAILED,
        ),
    ],
)
def test_upstream_errors_keep_their_existing_provider_categories(
    client, settings, upstream, pi, response, category, run_state, request_state
):
    upstream.respond = response
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client)))
    assert error.value.category == category  # the same typed error the direct path raises
    run, requests = only_run(client)
    assert (run.state, requests[0].state) == (run_state, request_state)
    assert len(upstream.calls) == 1  # and never retried


def test_a_timeout_after_dispatch_makes_the_run_unknown_and_is_never_retried(
    client, settings, upstream, pi
):
    def timeout(body):
        raise httpx.ReadTimeout("slow")

    upstream.respond = timeout
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client)))
    assert error.value.category == "timeout"
    run, requests = only_run(client)
    assert (run.state, requests[0].state) == (states.UNKNOWN, states.R_AMBIGUOUS)
    assert len(upstream.calls) == 1


def test_a_wrong_pi_version_is_refused_before_anything_starts(client, settings, upstream, tmp_path):
    package = tmp_path / "node_modules" / "@earendil-works" / "pi-coding-agent"
    (package / "dist" / "bundle").mkdir(parents=True)
    (package / "package.json").write_text(
        json.dumps({"name": "@earendil-works/pi-coding-agent", "version": "9.9.9"})
    )
    (package / "dist" / "bundle" / "cli.js").write_text("//")
    settings.alive_pi_cli = str(package / "dist" / "bundle" / "cli.js")
    runtime = use_pi(client, settings, upstream)
    runtime.runner = PiRunner(settings)  # the real locate, not a fake install
    with pytest.raises(ProviderError) as error:
        run_gateway(client, settings, request(reservation(client)))
    assert error.value.category == "pi_version_mismatch"
    run, _ = only_run(client)
    assert run.state == states.FAILED and run.pi_bundle_sha256 is None and upstream.calls == []
    client.portal.call(runtime.close)


# --- cancellation ----------------------------------------


def cancel_when(client, settings, req, ready):
    """Run the gateway, cancel it once `ready()` holds, return (outcome, runtime state)."""

    async def go():
        task = asyncio.create_task(PiGateway(settings, "cognition.role").structured(req))
        for _ in range(200):
            await asyncio.sleep(0.05)
            ready_now = ready()
            if inspect.isawaitable(ready_now):
                ready_now = await ready_now
            if ready_now:
                break
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        return task.cancelled()

    return client.portal.call(go)


def test_cancel_before_any_dispatch_is_cancelled_and_leaves_no_process(
    client, settings, upstream, pi
):
    req = request(reservation(client), "GATEWAY:no-settle x")  # Pi runs but never calls out
    assert cancel_when(client, settings, req, lambda: running(client)) is True
    run, requests = only_run(client)
    assert run.state == states.CANCELLED and run.terminal_reason == "cancelled_before_dispatch"
    assert requests == [] and upstream.calls == []
    assert run.result_json["cleanup_confirmed"] is True


async def running(client):
    async with client.app.state.kernel.db.sessions() as session:
        rows = (await session.scalars(select(PiRun))).all()
        return any(r.state == states.RUNNING for r in rows)


def test_cancel_during_the_provider_call_is_unknown_not_cancelled(client, settings, upstream, pi):
    upstream.block = asyncio.Event()  # the provider call never returns
    req = request(reservation(client))
    assert cancel_when(client, settings, req, lambda: bool(upstream.calls)) is True
    run, requests = only_run(client)
    assert (
        run.state == states.UNKNOWN and run.terminal_reason == "cancelled_after_possible_dispatch"
    )
    assert [r.state for r in requests] == [states.R_AMBIGUOUS]  # the outcome is genuinely unknown
    assert len(upstream.calls) == 1
    assert run.result_json["cleanup_confirmed"] is True


# --- crash recovery ----------------------------------------


def test_restart_settles_a_dispatched_request_as_ambiguous_and_never_replays_it(
    client, settings, upstream, pi
):
    reservation_id = reservation(client)

    async def seed():
        k = client.app.state.kernel
        async with k.lock, k.db.sessions.begin() as session:
            run = PiRun(
                id=uid(),
                instance_id=k.instance_id,
                operation="cognition.role",
                idempotency_key=f"cognition.role:{reservation_id}",
                reservation_ref=reservation_id,
                state=states.RUNNING,
                approved_request_json={},
                approved_request_sha256="a" * 64,
                requested_json={},
                token_sha256="b" * 64,
                max_provider_requests=1,
                provider_requests=1,
                inbound_requests=1,
            )
            session.add(run)
            await session.flush()
            session.add(PiProviderRequest(run_id=run.id, seq=1, state=states.R_DISPATCHED))
            return run.id

    run_id = client.portal.call(seed)  # the process "died" with a request in flight
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        runtime = use_pi(reopened, settings, upstream)
        run, requests = only_run(reopened)
        assert run.id == run_id
        assert (run.state, run.terminal_reason) == (
            states.UNKNOWN,
            "restart_after_possible_dispatch",
        )
        assert [(r.state, r.error_category) for r in requests] == [(states.R_AMBIGUOUS, "restart")]
        with pytest.raises(ProviderError) as again:  # the reservation is not dispatched again
            reopened.portal.call(
                lambda: PiGateway(settings, "cognition.role").structured(request(reservation_id))
            )
        reopened.portal.call(runtime.close)
    assert again.value.category == "pi_no_reservation" and upstream.calls == []


def test_restart_cancels_a_run_that_never_dispatched(client, settings, upstream, pi):
    async def seed():
        k = client.app.state.kernel
        async with k.lock, k.db.sessions.begin() as session:
            session.add(
                PiRun(
                    id=uid(),
                    instance_id=k.instance_id,
                    operation="cognition.role",
                    idempotency_key="cognition.role:" + uid(),
                    state=states.STARTING,
                    approved_request_json={},
                    approved_request_sha256="a" * 64,
                    requested_json={},
                    token_sha256="b" * 64,
                    max_provider_requests=1,
                )
            )

    client.portal.call(seed)
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        run, _ = only_run(reopened)
        assert (run.state, run.terminal_reason) == (states.CANCELLED, "restart")


# --- receipts ----------------------------------------


def test_the_receipt_and_event_trail_explain_the_run_without_leaking(
    client, settings, upstream, pi
):
    secret = "TOP-SECRET-QUESTION-TEXT"
    reservation_id = reservation(client)
    run_gateway(client, settings, request(reservation_id, data={"question": secret}))
    run, requests = only_run(client)
    receipt = client.get(f"/api/v1/pi/runs/{run.id}").json()
    assert receipt["state"] == states.SETTLED and receipt["terminal"] is True
    assert receipt["identity"]["requested_upstream_model"] == "muse-approved"
    assert receipt["identity"]["pi_observed"] == {
        "provider": "alive-egress",
        "model": "alive-approved",
    }
    assert receipt["identity"]["matches_expected_alias"] is True
    assert receipt["requests"]["counts"]["settled"] == 1 and receipt["requests"]["ceiling"] == 1
    item = receipt["requests"]["items"][0]
    assert item["usage"] == USAGE and item["cost_usd"] is None  # cost is unknown, not zero
    assert receipt["cost"]["usd"] is None
    assert (
        receipt["settlement"]["cleanup_confirmed"] is True
        and receipt["settlement"]["recovered"] is False
    )
    events = client.get(f"/api/v1/pi/runs/{run.id}/events").json()
    types = [e["event_type"] for e in events]
    assert types[0] == "pi.run.prepared" and types[-1] == "pi.run.settled"
    assert [e["sequence_number"] for e in events] == sorted(e["sequence_number"] for e in events)
    blob = json.dumps(receipt) + json.dumps(events)
    assert secret not in blob and REAL_KEY not in blob  # no prompt text, no credential
    listing = client.get("/api/v1/pi/runs").json()
    assert [r["run_id"] for r in listing] == [run.id]


def test_receipts_require_authentication_and_unknown_runs_are_404(client):
    anonymous = TestClient(client.app)
    for path in ("/api/v1/pi/runs", "/api/v1/pi/runs/x", "/api/v1/pi/runs/x/events"):
        assert anonymous.get(path).status_code == 401
    assert client.get("/api/v1/pi/runs/does-not-exist").status_code == 404
    assert client.get("/api/v1/pi/runs/does-not-exist/events").status_code == 404


def test_there_is_no_public_way_to_start_or_cancel_a_pi_run(client):
    for method, path in (("post", "/api/v1/pi/runs"), ("delete", "/api/v1/pi/runs/x")):
        assert getattr(client, method)(path).status_code in (404, 405)


def test_tokens_do_not_outlive_their_run(client, settings, upstream, pi):
    run_gateway(client, settings, request(reservation(client)))
    assert pi.egress.contexts == {}  # the run token was unregistered when the run ended
