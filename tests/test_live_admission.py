# ruff: noqa: F811
"""Offline regression only: scripted upstream through the existing Pi admission path."""

import asyncio
import json
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from alive.admission import live, service
from alive.admission.contracts import LiveGoal
from alive.models import Event, now, uid
from alive.sources import custody
from alive.sources.cli import principal
from tests.test_intent_interpretation import interpretation, respond_with
from tests.test_owner_admission import accepted_goal, call
from tests.test_pi_gateway import USAGE
from tests.test_repository_analysis import (  # noqa: F401
    analysis,
    approve_source,
    case,
    finding,
    quick_settle,
    settings,
)

BASE = "/api/v1/admissions/live"


@pytest.fixture
def ready(case):
    client, upstream, root, settings = case
    _, approval = call(
        client,
        approve_source,
        root,
        ["README.md", "calc.py"],
        ["intent.interpret", "repository.inspect", "repository.analyze"],
    )
    body = {
        "goal_ref": accepted_goal(client),
        "approval_ref": approval["id"],
        "paths": ["README.md", "calc.py"],
        "max_calls": 6,
        "max_tokens": 200000,
    }
    response = client.post(BASE + "/setup", json=body)
    assert response.status_code == 200, response.text
    setup = response.json()
    # Enable explicit inference while autonomy is paused, as the real dashboard does.
    enabled = client.post(
        "/api/v1/cognition/control", json={"command": "enable_model", "provider": "meta"}
    )
    assert enabled.status_code == 200, enabled.text

    def respond(body):
        data = json.loads(body["messages"][1]["content"])
        if "user_goal" in data:
            return respond_with(interpretation)(body)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": json.dumps(analysis(finding()))},
                        "finish_reason": "stop",
                    }
                ],
                "usage": USAGE,
            },
        )

    upstream.respond = respond
    return client, upstream, setup, body, approval, settings


def trust(ready):
    client, _, setup, *_ = ready
    return call(
        client, live.approve, setup["id"], confirm_sha256=setup["sha256"], principal=principal()
    )


def ask(ready, goal="Review these files for shipping blockers", key=None):
    client, _, setup, *_ = ready
    return client.post(
        BASE + "/ask",
        json={"consent_ref": setup["id"], "goal": goal, "idempotency_key": key or uid()},
    )


def test_three_goals_one_consent_real_dispatch_path_and_retained_results(ready):
    client, upstream, setup, *_ = ready
    assert ask(ready).status_code == 409 and not upstream.calls
    trust(ready)
    responses = []
    for i in range(3):
        goal, key = f"Review the supplied implementation, question {i}", uid()
        response = ask(ready, goal, key)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["status"] == "LIVE MODEL"
        assert value["goal"] == goal
        assert value["model_calls"] == 2
        assert value["report"]["result"]["findings"]
        assert all(
            c["status"] == "validated"
            and c["usage"]["total_tokens"] == USAGE["total_tokens"]
            and c["provider_receipts"][0]["http_status"] == 200
            for c in value["calls"]
        )
        # Retry is retained history, not another inference.
        assert ask(ready, goal, key).json() == value
        responses.append(value)
    assert len(upstream.calls) == 6  # interpreter + selected analysis for each goal
    history = client.get(BASE).json()
    assert {v["id"] for v in history["exchanges"]} == {v["id"] for v in responses}
    for value in responses:
        assert client.get(BASE + "/" + value["id"]).json() == value
    assert len(upstream.calls) == 6
    assert ask(ready, "A fourth goal").status_code == 409
    assert len(upstream.calls) == 6


@pytest.mark.parametrize(
    "change",
    [
        "revoked",
        "expired",
        "endpoint",
        "scope",
        "budget",
        "model",
        "transport",
        "credential",
        "governor_budget",
    ],
)
def test_standing_terms_fail_closed_without_model_fallback(ready, change):
    client, upstream, setup, body, approval, settings = ready
    trust(ready)
    if change == "revoked":
        call(client, live.revoke, setup["id"], principal=principal())
    elif change == "endpoint":
        settings.alive_meta_base_url = "https://wrong.example/v1"
    elif change == "model":
        settings.alive_meta_model = "unapproved-model"
    elif change == "transport":
        settings.alive_model_transport = "direct"
    elif change == "credential":
        settings.alive_meta_api_key = ""
    elif change == "governor_budget":

        async def spend_budget(kernel):
            from alive.cognitive_models import CognitiveControl

            async with kernel.db.sessions.begin() as session:
                control = await session.get(CognitiveControl, kernel.instance_id)
                control.spent = control.spent | {"session_tokens": 200000, "session_calls": 30}

        call(client, spend_budget)
    elif change == "scope":
        call(
            client,
            custody.withdraw,
            approval["id"],
            reason="test withdrawal",
            principal=principal(),
        )
    elif change in ("expired", "budget"):
        # Fault injection into the retained proposal simulates expiry / smaller explicit limit.
        async def change_terms(kernel):
            async with kernel.db.sessions.begin() as session:
                event = await session.scalar(select(Event).where(Event.id == setup["id"]))
                terms = dict(event.payload["terms"])
                if change == "expired":
                    terms["expires_at"] = (now() - timedelta(seconds=1)).isoformat()
                else:
                    terms["max_tokens"] = 1
                event.payload = {"terms": terms, "sha256": live.digest(terms)}
                approvals = (
                    await session.scalars(
                        select(Event).where(
                            Event.correlation_id == setup["id"],
                            Event.event_type == live.APPROVED,
                        )
                    )
                ).all()
                for receipt in approvals:
                    receipt.payload = receipt.payload | {"sha256": event.payload["sha256"]}

        call(client, change_terms)
    response = ask(ready)
    assert response.status_code == 409, response.text
    assert not upstream.calls


def test_model_failure_is_visible_and_never_retried(ready):
    client, upstream, *_ = ready
    trust(ready)
    upstream.respond = lambda _: httpx.Response(503, json={"error": "unavailable"})
    key = uid()
    response = ask(ready, key=key)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["availability"] == "AI unavailable"
    assert value["status"] == "MODEL CALL FAILED" and value["report"] is None
    assert ask(ready, key=key).json() == value
    assert len(upstream.calls) == 1


def test_no_useful_procedure_returns_interpretation_without_extra_call(ready):
    _, upstream, *_ = ready
    trust(ready)
    upstream.respond = respond_with(lambda goal: interpretation(goal, candidates=[]))
    response = ask(ready, "Write a poem")
    assert response.status_code == 200, response.text
    assert response.json()["recommendation"]["record"]["recommendation"] is None
    assert response.json()["model_calls"] == 1 and response.json()["report"] is None
    assert len(upstream.calls) == 1


def test_selected_inspection_returns_captured_evidence_without_another_model_call(ready):
    _, upstream, *_ = ready
    trust(ready)
    upstream.respond = respond_with(
        lambda goal: interpretation(
            goal,
            candidates=[
                {
                    "recipe_id": "approved-repository-inspection",
                    "recipe_version": "1.0.0",
                    "addresses": "fully",
                    "relevance": "Read the captured implementation",
                }
            ],
        )
    )
    response = ask(ready, "Show the implementation")
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["result_admission"]["run"]["status"] == "COMPLETED"
    assert value["inspection"]["files"] and value["report"] is None
    assert value["model_calls"] == 1 and len(upstream.calls) == 1


def test_cancellation_does_not_redispatch(ready):
    client, upstream, setup, *_ = ready
    trust(ready)
    request = LiveGoal(consent_ref=setup["id"], goal="Review these files", idempotency_key=uid())

    async def run(kernel):
        upstream.block = asyncio.Event()
        task = asyncio.create_task(live.ask(client.app, request))
        for _ in range(400):
            if upstream.calls:
                break
            await asyncio.sleep(0.05)
        history = await live.listing(kernel)
        row = history["exchanges"][0]
        await service.cancel(client.app, row["id"])
        upstream.block.set()
        await asyncio.gather(task, return_exceptions=True)
        return await live.exchange(kernel, row["id"])

    value = call(client, run)
    assert value["admission"]["run"]["status"] in ("CANCELLED", "UNKNOWN")
    replay = client.post(BASE + "/ask", json=request.model_dump())
    assert replay.status_code == 200, replay.text
    assert replay.json()["admission"]["run"]["status"] == value["admission"]["run"]["status"]
    assert len(upstream.calls) == 1


def test_revocation_at_pi_dispatch_fence_blocks_outbound_request(ready):
    client, upstream, setup, *_ = ready
    trust(ready)
    egress = client.app.state.pi.egress
    original = egress.workflow_guard

    async def revoked(session, row):
        # Inject a committed owner revocation after reservation, before actual egress.
        client.app.state.kernel.add_event(
            session,
            live.REVOKED,
            {"consent_ref": setup["id"], "principal": principal()},
            source=service.OWNER_SOURCE,
            correlation=setup["id"],
        )
        await session.flush()
        return await original(session, row)

    egress.workflow_guard = revoked
    result = ask(ready)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "NO MODEL CALL"
    assert result.json()["model_calls"] == 0
    assert not upstream.calls
