# ruff: noqa: F811
"""Offline scripted integration: context delivery and boundaries, not model-quality evidence."""

import json

import httpx
import pytest
from sqlalchemy import select

from alive.admission import live
from alive.continuity import service as continuity
from alive.models import Event, uid
from tests.test_intent_interpretation import interpretation, respond_with
from tests.test_live_admission import call, trust
from tests.test_owner_admission import accepted_goal
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
        [
            "intent.interpret",
            "repository.inspect",
            "repository.analyze",
            "context.reason",
            "context.validate",
        ],
    )
    body = {
        "goal_ref": accepted_goal(client),
        "approval_ref": approval["id"],
        "paths": ["README.md", "calc.py"],
        "max_calls": 20,
        "max_tokens": 200000,
        "contextual": True,
    }
    response = client.post(BASE + "/setup", json=body)
    assert response.status_code == 200, response.text
    setup = response.json()
    result = (client, upstream, setup, body, approval, settings)
    trust(result)
    client.post(
        "/api/v1/cognition/control", json={"command": "enable_model", "provider": "meta"}
    ).raise_for_status()

    def respond(body):
        data = json.loads(body["messages"][1]["content"])
        if "conversation" in data:
            items = data["conversation"]["items"]
            recalled = [i["id"] for i in items if i["source_type"] == "model_finding"][:1]
            revised = "zero" in data["user_goal"].lower()
            value = {
                "answer": "Zero sums can be correct; the divisor is still wrong."
                if revised
                else "The earlier divisor finding concerns calc.py; divide by len(values).",
                "recalled_item_ids": recalled,
                "citations": [
                    {
                        "file": "calc.py",
                        "line_start": 6,
                        "line_end": 6,
                        "quote": "return total / (len(values) + 1)",
                    }
                ],
                "revision": {
                    "supersedes": recalled,
                    "changed": "Not always incorrect",
                    "rationale": "Zero sums yield zero",
                    "still_supported": ["Wrong divisor"],
                    "withdrawn_or_qualified": ["Never correct"],
                }
                if revised
                else None,
                "uncertainty": [],
                "needs_clarification": False,
            }
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps(value)}, "finish_reason": "stop"}
                    ],
                    "usage": USAGE,
                },
            )
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
    return result


def conversation(ready, title="Arithmetic review"):
    client, _, setup, *_ = ready
    response = client.post(
        BASE + "/conversations", json={"consent_ref": setup["id"], "title": title}
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def ask(ready, ref, goal, key=None):
    client, _, setup, *_ = ready
    return client.post(
        BASE + "/ask",
        json={
            "consent_ref": setup["id"],
            "conversation_ref": ref,
            "goal": goal,
            "idempotency_key": key or uid(),
        },
    )


def initial(ready, ref):
    response = ask(ready, ref, "Review the most significant correctness problem")
    assert response.status_code == 200, response.text
    assert response.json()["report"], response.json()
    return response.json()


def test_context_is_frozen_delivered_revised_and_replayed(ready):
    client, upstream, *_ = ready
    ref = conversation(ready)
    original = initial(ready, ref)
    key = uid()
    response = ask(ready, ref, "Why does that problem occur?", key)
    assert response.status_code == 200, response.text
    followup = response.json()
    assert followup["answer"] and followup["model_calls"] == 1
    assert any(i["source_type"] == "model_finding" for i in followup["context"]["items"])
    assert "calc.py" in followup["answer"]["answer"]
    sent = upstream.calls[-1]["body"]["messages"][1]["content"]
    assert "Wrong count" in sent or "wrong count" in sent
    assert followup["answer"]["context_sha256"] == live.digest(followup["context"])
    assert ask(ready, ref, "Why does that problem occur?", key).json() == followup
    revision = ask(ready, ref, "Your claim is too broad for zero values").json()
    assert revision["answer"]["revision"]["supersedes"]
    later = ask(ready, ref, "Summarize what we now know").json()
    assert any(
        i["source_type"] == "model_answer" and i["content"]["revision"]
        for i in later["context"]["items"]
    )
    assert client.get(BASE + "/" + original["id"]).json()["report"] == original["report"]
    assert len(upstream.calls) == 5
    assert client.get(BASE + "/" + later["id"]).json() == later
    assert len(upstream.calls) == 5


def test_new_conversation_has_no_inherited_context_even_with_same_request_key(ready):
    _, upstream, *_ = ready
    first, second = conversation(ready), conversation(ready, "Independent work")
    initial(ready, first)
    response = ask(ready, second, "Why does that problem occur?")
    assert response.status_code == 200, response.text
    assert response.json()["context"] is None  # first turn uses interpretation, never other history
    assert all(
        "conversation" not in json.loads(c["body"]["messages"][1]["content"])
        for c in upstream.calls
    )


@pytest.mark.parametrize("change", ["owner", "source", "instance", "hash"])
def test_context_cannot_cross_or_tamper_with_scope(ready, change):
    client, upstream, *_ = ready
    ref = conversation(ready)
    initial(ready, ref)
    response = ask(ready, ref, "Explain that finding").json()
    count = len(upstream.calls)

    async def tamper(kernel):
        async with kernel.db.sessions.begin() as session:
            if change == "hash":
                row = await session.scalar(
                    select(Event).where(Event.id == response["answer"]["context_ref"])
                )
                row.payload = row.payload | {"sha256": "0" * 64}
            else:
                row = await session.scalar(select(Event).where(Event.id == ref))
                payload = json.loads(json.dumps(row.payload))
                if change == "owner":
                    payload["principal"] = "owner-cli:someone-else"
                elif change == "source":
                    payload["resources"]["content_sha256"] = "0" * 64
                else:
                    from alive.models import Instance

                    other = Instance(id=uid(), name="other")
                    session.add(other)
                    await session.flush()
                    row.instance_id = other.id
                row.payload = payload

    call(client, tamper)
    result = (
        client.get(BASE + "/" + response["id"])
        if change == "hash"
        else ask(ready, ref, "Explain again")
    )
    assert result.status_code == 409, result.text
    assert len(upstream.calls) == count


def test_explicit_older_findings_and_context_dependence(ready):
    _, upstream, *_ = ready
    base = upstream.respond

    def respond(body):
        data = json.loads(body["messages"][1]["content"])
        if "conversation" in data:
            selected = next(i for i in data["conversation"]["items"] if i["id"].endswith(":F23"))
            value = json.loads(base(body).json()["choices"][0]["message"]["content"])
            value["answer"] = selected["content"]["model_assessment"]["title"]
            value["recalled_item_ids"] = [selected["id"]]
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps(value)}, "finish_reason": "stop"}
                    ],
                    "usage": USAGE,
                },
            )
        if "user_goal" in data:
            return base(body)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                analysis(
                                    finding(finding_id="F17", title="Rounding error"),
                                    finding(finding_id="F23", title="Missing authorization check"),
                                )
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": USAGE,
            },
        )

    upstream.respond = respond
    ref = conversation(ready)
    initial(ready, ref)
    result = ask(ready, ref, "Which is the F23 problem rather than F17?").json()
    assert result["answer"]["answer"] == "Missing authorization check"
    assert result["answer"]["recalled_item_ids"][0].endswith(":F23")
    assert {i["id"].split(":")[-1] for i in result["context"]["items"]} >= {"F17", "F23"}


@pytest.mark.parametrize("change", ["consent", "source"])
def test_revoked_context_scope_never_dispatches(ready, change):
    from alive.sources import custody
    from alive.sources.cli import principal

    _, upstream, setup, _, approval, _ = ready
    ref = conversation(ready)
    initial(ready, ref)
    if change == "consent":
        call(ready[0], live.revoke, setup["id"], principal=principal())
    else:
        call(ready[0], custody.withdraw, approval["id"], reason="test", principal=principal())
    assert ask(ready, ref, "Explain it").status_code == 409
    assert len(upstream.calls) == 2


def test_unrelated_memory_is_not_disclosed_and_essential_budget_fails_visibly(ready, monkeypatch):
    from alive.models import Memory

    client, upstream, *_ = ready
    ref = conversation(ready)
    first = initial(ready, ref)

    async def unrelated(kernel):
        async with kernel.db.sessions.begin() as session:
            session.add(
                Memory(instance_id=kernel.instance_id, content="UNAUTHORIZED_MEMORY_CANARY")
            )

    call(client, unrelated)
    response = ask(ready, ref, "Why does it happen?").json()
    assert "UNAUTHORIZED_MEMORY_CANARY" not in json.dumps(response["context"])
    assert "UNAUTHORIZED_MEMORY_CANARY" not in json.dumps(upstream.calls)
    monkeypatch.setattr(continuity, "MAX_BYTES", 50)
    refused = ask(ready, ref, "Explain it again")
    assert refused.status_code == 409 and "essential_context_does_not_fit" in refused.text
    assert len(upstream.calls) == 3
    assert client.get(BASE + "/" + first["id"]).json()["report"] == first["report"]


def test_pi_dispatch_binds_all_recalled_and_source_bytes(ready):
    client, upstream, *_ = ready
    ref = conversation(ready)
    initial(ready, ref)
    guard = client.app.state.pi.egress.workflow_guard

    async def tamper(session, call):
        stored = json.loads(json.dumps(call.input_json))
        stored["context"]["source"]["files"][0]["numbered_lines"] = "Forged source bytes"
        stored["context_sha256"] = live.digest(stored["context"])
        call.input_json = stored
        return await guard(session, call)

    client.app.state.pi.egress.workflow_guard = tamper
    response = ask(ready, ref, "Explain that finding")
    assert response.status_code == 200, response.text
    assert response.json()["answer"] is None
    assert len(upstream.calls) == 2
