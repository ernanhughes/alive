"""Independent R1 adversarial probes for PI-02B @ b2d06ca. Scratch only; never part of the PR.

Each probe writes its observations to the evidence folder so the review report can cite them.
"""

import asyncio
import contextlib
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alive.app import create_app
from alive.cognitive_models import CognitiveControl, CognitiveMessage, ModelInvocation
from alive.models import Event
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import context as ctx
from alive.workflows import store
from alive.workflows.context import digest
from alive.workflows.examples import fixture_authorization
from alive.workflows.models import WorkflowExecution
from tests.conftest import TOKEN
from tests.test_pi_gateway import REAL_KEY, Upstream
from tests.workflow_execution_helpers import call, observation, prepare

EVIDENCE = Path("C:/Projects/alive-pi02b-r1-evidence")


def record(name, **data):
    EVIDENCE.mkdir(exist_ok=True)
    (EVIDENCE / f"probe-{name}.json").write_text(json.dumps(data, indent=2, default=str))
    print("\nPROBE", name, json.dumps(data, default=str))


@pytest.fixture
def pi_env(client, settings, monkeypatch):
    settings.alive_model_transport = "pi"
    settings.alive_meta_api_key = REAL_KEY

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
    upstream = Upstream()
    client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
    prepare(client, "meta")
    observation(client)
    return upstream


async def states_of(k, run_id):
    run = await store.get_run(k, run_id)
    stages = await store.get_stage_runs(k, run_id)
    async with k.db.sessions() as session:
        invocations = (await session.scalars(select(ModelInvocation))).all()
        pi = (await session.scalars(select(PiRun))).all()
        requests = (await session.scalars(select(PiProviderRequest))).all()
        messages = await session.scalar(select(func.count()).select_from(CognitiveMessage))
        control = await session.get(CognitiveControl, k.instance_id)
    return {
        "run": run["status"],
        "reason": run["terminal_reason"],
        "stages": {s["stage_id"]: (s["state"], s["error_category"]) for s in stages},
        "invocations": [i.status for i in invocations],
        "pi_runs": [p.state for p in pi],
        "pi_requests": [r.state for r in requests],
        "messages": messages,
        "reserved": dict(control.reserved),
    }


# --- A: authority --------------------------------------------------------------------------------


def test_a1_public_ingest_cannot_mint_or_impersonate_owner_events(client):
    for event_type, source in (
        ("workflow.execution.authorized", "workflow-owner"),
        ("workflow.execution.authorized", "user"),
        ("browser.dom_changed", "workflow-owner"),
    ):
        response = client.post(
            "/api/v1/events",
            json={"event_type": event_type, "source": source, "payload": {"x": 1}},
        )
        assert response.status_code == 422, (event_type, source, response.text)
    # A forged grant filed as an allowed public event is not an owner authorization.
    prepare(client)
    observation(client)
    forged = "11111111-1111-4111-8111-111111111111"
    assert (
        client.post(
            "/api/v1/events",
            json={
                "event_id": forged,
                "event_type": "browser.dom_changed",
                "payload": {"text": "g"},
            },
        ).status_code
        == 200
    )

    async def probe(k):
        try:
            await client.app.state.workflows.start(forged)
        except ctx.Refused as error:
            return str(error)

    refusal = call(client, probe)
    assert refusal == "owner_authorization_required"
    record("a1_forged_authorization", refusal=refusal)


def test_a2_context_event_source_is_not_authenticated(client):
    """The grant's context event may be ANY same-instance event whose payload hashes right."""
    from alive.cognitive_models import Investigation
    from alive.schemas import Observation

    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            async with k.db.sessions() as session:
                goal_id = (await session.get(Investigation, inquiry)).goal_id
            public_id = "22222222-2222-4222-8222-222222222222"
            payload = {
                "goal_id": goal_id,
                "context": {
                    "observation": "text posted through the PUBLIC ingest route",
                    "claims": [],
                    "sources": [],
                    "memories": [],
                    "source_event_ids": [public_id],
                    "requested_action_kind": "record_analysis",
                },
                "text": "x",
            }
            # Exactly what POST /api/v1/events does (kernel.ingest), with its allowed source/type.
            await k.ingest(
                Observation(event_id=public_id, event_type="browser.dom_changed", payload=payload)
            )
            async with k.db.sessions() as session:
                stored = await session.scalar(select(Event).where(Event.id == public_id))
                source, kind, stored_payload = stored.source, stored.event_type, stored.payload
            authorization = await fixture_authorization(
                k, inquiry, model=False,
                changes={"context_event_id": public_id, "context_sha256": digest(stored_payload)},
            )  # fmt: skip
            try:
                run = await client.app.state.workflows.start(authorization)
            except ctx.Refused as error:
                return {"source": source, "type": kind, "start": "refused:" + str(error)}
            final = await client.app.state.workflows.execute(run["id"])
            return {"source": source, "type": kind, "start": "admitted", "final": final["status"]}

    record("a2_context_source", **call(client, probe))


# --- B/C: dispatch fence, faults ----------------------------------------------------------------------


async def gated_pi_run(client, k, before, *, model=True):
    egress = client.app.state.pi.egress
    original = egress._dispatch
    reached, release = asyncio.Event(), asyncio.Event()

    async def gated(request_id):
        reached.set()
        await release.wait()
        return await original(request_id)

    egress._dispatch = gated
    async with client.app.state.cognition.workflow_inquiry() as inquiry:
        authorization = await fixture_authorization(k, inquiry, model=model)
        runner = client.app.state.workflows
        run = await runner.start(authorization)
        task = asyncio.create_task(runner.execute(run["id"]))
        await asyncio.wait_for(reached.wait(), 90)
        await before(authorization, inquiry, k)
        release.set()
        await asyncio.wait_for(task, 90)
        return run["id"], authorization


@pytest.mark.parametrize("change", ["revoke", "withdraw", "configuration", "expire_deadline"])
def test_b_authority_changes_between_reservation_and_dispatch_stop_the_provider(
    client, pi_env, change
):
    async def before(authorization, inquiry, k):
        async with k.db.sessions() as session:
            payload = (await session.scalar(select(Event).where(Event.id == authorization))).payload
        if change == "revoke":
            await ctx.revoke(k, authorization)
        elif change == "withdraw":
            await ctx.withdraw(k, payload["context_event_id"])
        elif change == "configuration":
            async with k.lock, k.db.sessions.begin() as session:
                control = await session.get(CognitiveControl, k.instance_id)
                control.configuration = {**control.configuration, "topics": ["changed"]}
        else:
            async with k.lock, k.db.sessions.begin() as session:
                from datetime import timedelta

                from alive.models import now

                execution = (await session.scalars(select(WorkflowExecution))).one()
                execution.deadline = now() - timedelta(seconds=1)

    async def probe(k):
        run_id, _ = await gated_pi_run(client, k, before)
        return await states_of(k, run_id)

    observed = call(client, probe)
    record(f"b_{change}", upstream_calls=len(pi_env.calls), **observed)
    assert len(pi_env.calls) == 0, observed


def test_b_provider_failures_after_the_dispatch_marker(client, pi_env):
    results = {}
    for name, respond in (
        ("http_500", lambda body: httpx.Response(500, json={})),
        ("timeout", lambda body: (_ for _ in ()).throw(httpx.ReadTimeout("slow"))),
        ("malformed", lambda body: httpx.Response(200, json={"choices": []})),
    ):
        pi_env.respond = respond
        pi_env.calls.clear()

        async def probe(k):
            async with client.app.state.cognition.workflow_inquiry() as inquiry:
                authorization = await fixture_authorization(k, inquiry, model=True)
                runner = client.app.state.workflows
                run = await runner.start(authorization)
                await runner.execute(run["id"])
                return await states_of(k, run["id"])

        results[name] = call(client, probe) | {"upstream_calls": len(pi_env.calls)}
        # a fresh inquiry is needed for the next attempt
        prepare_again = client.post("/api/v1/cognition/control", json={"command": "stop"})
        assert prepare_again.status_code == 200
        break  # one failure mode per database; the others run in their own tests below
    record("b_provider_failure_first", **results)


@pytest.mark.parametrize("mode", ["http_500", "timeout", "malformed"])
def test_b_each_provider_failure_mode(client, pi_env, mode):
    pi_env.respond = {
        "http_500": lambda body: httpx.Response(500, json={}),
        "timeout": lambda body: (_ for _ in ()).throw(httpx.ReadTimeout("slow")),
        "malformed": lambda body: httpx.Response(200, json={"choices": []}),
    }[mode]

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            await runner.execute(run["id"])
            second = await runner.execute(run["id"])  # a retry attempt
            return await states_of(k, run["id"]) | {"retry_status": second["status"]}

    observed = call(client, probe)
    record(f"b_failure_{mode}", upstream_calls=len(pi_env.calls), **observed)
    assert len(pi_env.calls) <= 1
    assert all(v == 0 for v in observed["reserved"].values())


def test_b_duplicate_starts_and_executes_dispatch_once(client, pi_env):
    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            starts = await asyncio.gather(
                runner.start(authorization), runner.start(authorization), return_exceptions=True
            )
            ids = {s["id"] for s in starts if isinstance(s, dict)}
            second = await fixture_authorization(k, inquiry, model=True)
            try:
                other = await runner.start(second)
            except ctx.Refused as error:
                other = "refused:" + str(error)
            run_id = next(iter(ids))
            finals = await asyncio.gather(
                runner.execute(run_id), runner.execute(run_id), return_exceptions=True
            )
            return {
                "starts": [type(s).__name__ for s in starts],
                "distinct_runs": len(ids),
                "second_grant": other if isinstance(other, str) else "admitted",
                "finals": [f["status"] if isinstance(f, dict) else repr(f) for f in finals],
                "state": await states_of(k, run_id),
            }

    observed = call(client, probe)
    record("b_duplicates", upstream_calls=len(pi_env.calls), **observed)
    assert len(pi_env.calls) == 1 and observed["distinct_runs"] == 1


# --- C: transactions and honesty of the artifact -----------------------------------------------------


def test_c_failure_while_settling_the_inquiry_after_all_stages_completed(client):
    prepare(client)
    observation(client)
    cognition = client.app.state.cognition
    original = cognition.finish_in_session

    async def failing(session, run_id, target, *args, **kwargs):
        if target == "COMPLETED":
            raise RuntimeError("injected during cognition settlement")
        return await original(session, run_id, target, *args, **kwargs)

    cognition.finish_in_session = failing

    async def probe(k):
        async with cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            final = await runner.execute(run["id"])
            return run["id"], final, await states_of(k, run["id"])

    run_id, final, observed = call(client, probe)
    stages = observed["stages"]
    record_stage = next(s for s in stages if s.startswith("record") or s == "record")
    artifact = client.get(f"/api/v1/workflow-runs/{run_id}/artifacts/{record_stage}")
    record(
        "c_finish_fault",
        returned_status=final["status"],
        returned_reason=final["terminal_reason"],
        artifact_http=artifact.status_code,
        artifact_has_run_status="status"
        in (artifact.json() if artifact.status_code == 200 else {}),
        artifact_keys=sorted(artifact.json()) if artifact.status_code == 200 else None,
        **observed,
    )


def test_c_cancel_requested_just_before_terminal_settlement(client):
    prepare(client)
    observation(client)
    runner = client.app.state.workflows
    original = runner._finish

    async def cancel_then_finish(run_id, owner):
        k = client.app.state.kernel
        async with k.lock, k.db.sessions.begin() as session:
            (await session.get(WorkflowExecution, run_id)).cancel_requested = True
        return await original(run_id, owner)

    runner._finish = cancel_then_finish

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            run = await runner.start(authorization)
            final = await runner.execute(run["id"])
            return run["id"], final, await states_of(k, run["id"])

    run_id, final, observed = call(client, probe)
    artifact = client.get(f"/api/v1/workflow-runs/{run_id}/artifacts/record")
    record(
        "c_cancel_before_finish",
        returned_status=final["status"],
        artifact_http=artifact.status_code,
        **observed,
    )


def test_c_revocation_after_provider_success_before_stage_commit(client, pi_env):
    runner = client.app.state.workflows
    original = runner._stage

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            run = await runner.start(authorization)
            real_dispatch = client.app.state.pi.egress._dispatch

            async def revoke_after_response(request_id):
                return await real_dispatch(request_id)

            task = asyncio.create_task(runner.execute(run["id"]))
            # revoke as soon as the provider has answered
            for _ in range(600):
                await asyncio.sleep(0.1)
                if pi_env.calls:
                    await asyncio.sleep(0.05)
                    with contextlib.suppress(ctx.Refused):
                        await ctx.revoke(k, authorization)
                    break
            await asyncio.wait_for(task, 90)
            return await states_of(k, run["id"])

    _ = original
    observed = call(client, probe)
    record("c_revoke_after_response", upstream_calls=len(pi_env.calls), **observed)
    assert len(pi_env.calls) == 1


# --- restart from a crash image ---------------------------------------------------------------------------


def test_e_crash_image_mid_provider_call_recovers_unknown_without_redispatch(
    client, settings, pi_env, tmp_path
):
    pi_env.block = asyncio.Event()
    source = Path(settings.database_url.split("///", 1)[1])
    image = tmp_path / "crash.db"

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            task = asyncio.create_task(runner.execute(run["id"]))
            for _ in range(900):
                await asyncio.sleep(0.1)
                if pi_env.calls:
                    break
            assert pi_env.calls, "provider never reached"
            # A consistent image of the database while the provider call is in flight = a crash.
            with sqlite3.connect(source) as src, sqlite3.connect(image) as dst:
                src.backup(dst)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            pi_env.block.set()
            return run["id"]

    run_id = call(client, probe)
    copy = settings.model_copy(update={"database_url": f"sqlite+aiosqlite:///{image}"})
    with TestClient(create_app(copy), headers={"Authorization": f"Bearer {TOKEN}"}) as restarted:
        restarted.app.state.pi.upstream_transport = httpx.MockTransport(Upstream().handle)
        observed = call(restarted, lambda k: states_of(k, run_id))
        again = call(restarted, lambda k: restarted.app.state.workflows.execute(run_id))
        after = call(restarted, lambda k: states_of(k, run_id))
    record("e_crash_image", before=observed, replay=again["status"], after=after)
    assert observed["run"] in {"UNKNOWN", "CANCELLED", "FAILED"}
    assert observed == after


# --- more fault points and the cancel race -------------------------------------------------------------


def test_c_fault_inside_the_reservation_transaction_leaves_no_invocation(client, pi_env, monkeypatch):
    original = client.app.state.kernel.add_event

    def fail(session, kind, payload=None, **kwargs):
        if kind == "cognition.model_reserved":
            raise RuntimeError("injected before reservation commit")
        return original(session, kind, payload, **kwargs)

    monkeypatch.setattr(client.app.state.kernel, "add_event", fail)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            await runner.execute(run["id"])
            return await states_of(k, run["id"])

    observed = call(client, probe)
    record("c_fault_before_reservation_commit", upstream_calls=len(pi_env.calls), **observed)
    assert observed["invocations"] == [] and len(pi_env.calls) == 0


def test_c_cancel_immediately_after_reservation_commit(client, pi_env, monkeypatch):
    from alive.pi.gateway import PiGateway

    async def cancelled(self, req):
        raise asyncio.CancelledError()

    monkeypatch.setattr(PiGateway, "structured", cancelled)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            final = await runner.execute(run["id"])
            return await states_of(k, run["id"]) | {"returned": final["status"]}

    observed = call(client, probe)
    record("c_cancel_after_reservation_commit", upstream_calls=len(pi_env.calls), **observed)
    assert len(pi_env.calls) == 0 and all(v == 0 for v in observed["reserved"].values())


def run_seeded_observation(client, seed):
    from tests.test_cognition import observe

    observe(client, seed=seed)

    async def perceive(_):
        await client.app.state.cognition.perceive()

    call(client, perceive)


@pytest.mark.parametrize("model", [False, True])
def test_g_randomized_cancel_race_keeps_the_invariants(client, settings, monkeypatch, model):
    if model:
        settings.alive_model_transport = "pi"
        settings.alive_meta_api_key = REAL_KEY

        async def catalog(_):
            return {"status": "available", "models": [settings.alive_meta_model]}

        monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
        upstream = Upstream()
        client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
        prepare(client, "meta")
    else:
        upstream = None
        prepare(client)
    trials = []
    delays = [0, 0.01, 0.03, 0.06, 0.1, 0.2, 0.4, 0.8] if model else [0, 0.005, 0.01, 0.02, 0.04, 0.08]
    for seed, delay in enumerate(delays, start=20):
        run_seeded_observation(client, seed)

        async def probe(k, delay=delay):
            async with client.app.state.cognition.workflow_inquiry() as inquiry:
                authorization = await fixture_authorization(k, inquiry, model=model)
                runner = client.app.state.workflows
                run = await runner.start(authorization)
                task = asyncio.create_task(runner.execute(run["id"]))
                await asyncio.sleep(delay)
                await runner.cancel(run["id"])
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(task, 60)
                return run["id"], await states_of(k, run["id"])

        run_id, observed = call(client, probe)
        terminal = {"COMPLETED", "FAILED", "CANCELLED", "UNKNOWN"}
        stage_terminal = {"COMPLETED", "FAILED", "CANCELLED", "UNKNOWN"}
        assert observed["run"] in terminal, observed
        assert all(state in stage_terminal for state, _ in observed["stages"].values()), observed
        assert all(v == 0 for v in observed["reserved"].values()), observed
        assert not [i for i in observed["invocations"] if i == "reserved"], observed
        if observed["run"] == "COMPLETED":
            assert all(state == "COMPLETED" for state, _ in observed["stages"].values())
        if upstream is not None:
            assert len(upstream.calls) <= len(trials) + 1
        trials.append({"delay": delay, **{k: observed[k] for k in ("run", "reason", "invocations", "pi_runs", "pi_requests")}})
    record(f"g_cancel_race_model_{model}", trials=trials, upstream_calls=len(upstream.calls) if upstream else 0)


# --- F: evidence substitution -------------------------------------------------------------------


@pytest.mark.parametrize("tamper", ["event_output", "artifact_content", "artifact_hash_rebuilt", "swap_output_ref"])
def test_f_evidence_substitution_is_detected_on_read(client, tamper):
    from sqlalchemy import update

    from alive.workflows.models import WorkflowStageRun

    prepare(client)
    observation(client)
    cognition = client.app.state.cognition

    async def probe(k):
        async with cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            await runner.execute(run["id"])
            stages = await store.get_stage_runs(k, run["id"])
            rec = next(s for s in stages if s["operation"] == "result.record")
            other = next(s for s in stages if s["operation"] != "result.record" and s["state"] == "COMPLETED")
            async with k.db.sessions.begin() as session:
                row = await session.scalar(
                    select(WorkflowStageRun).where(WorkflowStageRun.id == rec["id"])
                )
                ev = await session.scalar(select(Event).where(Event.id == row.output_ref[6:]))
                art = await session.get(CognitiveMessage, ev.payload["output"]["artifact_id"])
                if tamper == "event_output":
                    ev.payload = {**ev.payload, "output": {**ev.payload["output"], "sha256": "f" * 64}}
                elif tamper == "artifact_content":
                    art.content = {**art.content, "result": {"forged": True}}
                elif tamper == "artifact_hash_rebuilt":
                    content = {**art.content, "result": {"forged": True}}
                    art.content = content
                    out = {**ev.payload["output"], "sha256": digest(content)}
                    ev.payload = {**ev.payload, "output": out}
                elif tamper == "swap_output_ref":
                    orow = await session.scalar(
                        select(WorkflowStageRun).where(WorkflowStageRun.id == other["id"])
                    )
                    row.output_ref = orow.output_ref
            return run["id"], rec["stage_id"]

    run_id, stage_id = call(client, probe)
    response = client.get(f"/api/v1/workflow-runs/{run_id}/artifacts/{stage_id}")
    record(
        f"f_{tamper}",
        http=response.status_code,
        body=response.text[:300],
    )


def test_h_second_run_after_a_completed_run_can_take_the_execution_slot(client):
    prepare(client)
    cognition = client.app.state.cognition

    async def one(k):
        async with cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            final = await runner.execute(run["id"])
            return (final["status"], final["terminal_reason"])

    async def slots(k):
        async with k.db.sessions() as session:
            return (await session.scalars(select(WorkflowExecution.slot))).all()

    outcomes = []
    for _ in range(2):
        observation(client)
        outcomes.append(call(client, one))
    record("h_sequential_runs", outcomes=outcomes, slots_after=call(client, slots))
    assert [o[0] for o in outcomes] == ["COMPLETED", "COMPLETED"]


def test_i_api_disclosure_and_scoping(client, pi_env):
    cognition = client.app.state.cognition

    async def run(k):
        async with cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run_ = await runner.start(authorization)
            final = await runner.execute(run_["id"])
            return run_["id"], final["status"]

    run_id, status = call(client, run)
    stages = client.get(f"/api/v1/workflow-runs/{run_id}/stages").json()
    stage_rows = stages if isinstance(stages, list) else stages.get("stages", stages)
    out = {"status": status}
    rec = next(s for s in stage_rows if s["operation"] == "result.record")
    other = next(s for s in stage_rows if s["operation"] != "result.record")
    art = client.get(f"/api/v1/workflow-runs/{run_id}/artifacts/{rec['stage_id']}")
    out["artifact_http"] = art.status_code
    out["artifact_keys"] = sorted(art.json())
    blob = art.text + client.get(f"/api/v1/workflow-runs/{run_id}").text + json.dumps(stage_rows)
    out["leaks"] = {
        "api_key": REAL_KEY in blob,
        "token": TOKEN in blob,
        "windows_path": "C:\\\\" in blob or "C:/" in blob or "Users" in blob,
        "prompt_marker": "system_prompt" in blob or "messages" in blob,
    }
    out["non_record_stage_artifact"] = client.get(
        f"/api/v1/workflow-runs/{run_id}/artifacts/{other['stage_id']}"
    ).status_code
    out["unknown_run"] = client.get("/api/v1/workflow-runs/nope/artifacts/x").status_code
    out["oversize"] = client.get("/api/v1/workflow-runs/" + "a" * 40 + "/artifacts/x").status_code
    out["no_auth"] = TestClient(client.app).get(
        f"/api/v1/workflow-runs/{run_id}/artifacts/{rec['stage_id']}"
    ).status_code
    out["write_methods"] = [
        client.request(m, f"/api/v1/workflow-runs/{run_id}/artifacts/{rec['stage_id']}").status_code
        for m in ("POST", "PUT", "DELETE", "PATCH")
    ]
    out["stage_row_keys"] = sorted(stage_rows[0])
    out["artifact_body"] = art.json()
    out["model_stage_validation"] = [(s["stage_id"], s["validation_status"], s["state"]) for s in stage_rows]
    record("i_api", **out)


@pytest.mark.parametrize("tamper", ["model", "context", "status", "stage_state", "stage_link"])
def test_j_binding_clauses_stop_a_substituted_reservation(client, pi_env, tamper):
    from sqlalchemy.orm.attributes import flag_modified

    from alive.workflows.models import WorkflowStageRun

    async def before(authorization, inquiry, k):
        async with k.lock, k.db.sessions.begin() as session:
            inv = (await session.scalars(select(ModelInvocation))).one()
            stage = await session.scalar(
                select(WorkflowStageRun).where(WorkflowStageRun.model_invocation_id == inv.id)
            )
            if tamper == "model":
                inv.model = "some-other-model"
            elif tamper == "context":
                inv.input_json = {**inv.input_json, "context": {"substituted": True}}
                flag_modified(inv, "input_json")
            elif tamper == "status":
                inv.status = "validated"
            elif tamper == "stage_state":
                stage.state = "PENDING"
            else:
                stage.model_invocation_id = None

    async def probe(k):
        run_id, _ = await gated_pi_run(client, k, before)
        return await states_of(k, run_id)

    observed = call(client, probe)
    record(f"j_{tamper}", upstream_calls=len(pi_env.calls), **observed)


def test_k_real_pi_completed_then_database_fault_in_stage_commit(client, pi_env):
    runner = client.app.state.workflows
    original = runner.k.add_event
    seen = []

    def faulty(session, event_type, payload=None, *args, **kwargs):
        if event_type == "workflow.stage.result":
            seen.append(1)
        if event_type == "workflow.stage.result" and len(seen) == 2:
            raise RuntimeError("injected database fault while committing the stage result")
        return original(session, event_type, payload, *args, **kwargs)

    runner.k.add_event = faulty

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            run = await runner.start(authorization)
            final = await runner.execute(run["id"])
            replay = await runner.execute(run["id"])
            await runner.recover()
            return run["id"], final["status"], replay["status"], await states_of(k, run["id"])

    run_id, final, replay, observed = call(client, probe)
    runner.k.add_event = original
    record("k_pi_ok_then_db_fault", returned=final, replay=replay, upstream_calls=len(pi_env.calls), **observed)
