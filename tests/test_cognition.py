import time

import pytest
from pydantic import ValidationError

from alive.attention import attention, rank
from alive.cognitive_schema import RoleOutput
from alive.society import evaluate, mock_role, validate_references


def wait_for(client, path, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = client.get("/api/v1" + path).json()
        if predicate(value):
            return value
        time.sleep(0.05)
    raise AssertionError(f"Timed out waiting for {path}: {value}")


def observe(client, scenario="relevant", seed=13):
    lab = client.post("/api/v1/lab", json={"scenario": scenario, "seed": seed}).json()
    view = client.post(f"/api/v1/lab/{lab['id']}/inject", json={}).json()
    event = {
        "event_type": "browser.dom_changed",
        "payload": {"url": f"http://127.0.0.1:8000/world/{lab['id']}", "text": view["text"]},
    }
    assert client.post("/api/v1/events", json=event).status_code == 200
    return lab, event


def start(client, **config):
    if config:
        assert client.post("/api/v1/cognition/configuration", json=config).status_code == 200
    assert (
        client.post(
            "/api/v1/cognition/control", json={"command": "start", "provider": "mock"}
        ).status_code
        == 200
    )


def completed(client):
    values = wait_for(
        client,
        "/cognition/investigations",
        lambda rows: rows and rows[0]["state"] in {"COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"},
    )
    return client.get("/api/v1/cognition/investigations/" + values[0]["id"]).json()


@pytest.mark.parametrize(
    "scenario,verdict", [("relevant", "SUPPORTED"), ("contradiction", "CONTRADICTED")]
)
def test_autonomous_evidence_loop(client, scenario, verdict):
    start(client)
    lab, event = observe(client, scenario)
    result = completed(client)
    assert result["state"] == "COMPLETED", result
    assert result["evaluation"]["status"] == verdict
    assert result["evaluation"]["conclusion_status"] == "VERIFIED"
    assert [m["sender"] for m in result["messages"]] == [
        "governor",
        "observer",
        "proposer",
        "critic",
        "investigator",
        "evaluator",
    ]
    assert result["usage"]["calls"] == 3
    assert all(
        c["provider"] == "mock" and c["status"] == "validated" for c in result["invocations"]
    )
    assert result["actions"][0]["status"] == "executed"
    experience = result["experiences"][0]["data"]
    assert experience["reward_components"]["correctness"] == 1
    assert experience["terminated"] is False and experience["truncated"] is False
    assert experience["state_snapshot"]["environment_id"] == lab["id"]
    assert event["payload"]["text"] in experience["state_snapshot"]["observation"]
    assert client.get("/api/v1/cognition").json()["control"]["reserved"]["tokens"] == 0
    replay = client.post(
        "/api/v1/experiences/" + result["experiences"][0]["id"] + "/replay", json={}
    ).json()
    assert replay["model_reexecuted"] is False
    assert replay["observation_evaluation"]["status"] == verdict
    export = client.get("/api/v1/experiences/export")
    assert export.status_code == 200 and "application/x-ndjson" in export.headers["content-type"]


def test_no_action_noise_duplicates_and_concurrent_arrival(client):
    from concurrent.futures import ThreadPoolExecutor

    start(client)
    lab, event = observe(client, "noise")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: client.post("/api/v1/events", json=event), range(10)))
    assert all(r.status_code == 200 for r in results)
    bids = wait_for(client, "/cognition/observations", lambda rows: rows)
    assert len(bids) == 1 and bids[0]["status"] == "IGNORED"
    assert client.get("/api/v1/cognition/investigations").json() == []
    assert client.get("/api/v1/cognition").json()["control"]["spent"] == {}
    assert not any(g["origin"] == "cognitive_society" for g in client.get("/api/v1/goals").json())


def test_budget_exhaustion_and_no_credential_leak(client):
    start(client, session_calls=0)
    observe(client)
    bids = wait_for(
        client,
        "/cognition/observations",
        lambda rows: rows and rows[0]["status"] == "BUDGET_REJECTED",
    )
    assert bids[0]["status"] == "BUDGET_REJECTED"
    assert client.get("/api/v1/cognition/investigations").json() == []
    assert "api_key" not in client.get("/api/v1/cognition").text.lower()
    assert (
        client.post("/api/v1/cognition/configuration", json={"session_calls": 2000}).status_code
        == 422
    )
    assert client.post("/api/v1/cognition/configuration", json={}).status_code == 409


def test_stop_cancels_pending_work(client, monkeypatch):
    import asyncio

    from alive.cognition import Cognition

    async def slow(*args):
        await asyncio.sleep(30)

    monkeypatch.setattr(Cognition, "call_role", slow)
    start(client)
    observe(client)
    wait_for(
        client,
        "/cognition/investigations",
        lambda rows: rows and rows[0]["state"] == "INVESTIGATING",
    )
    assert client.post("/api/v1/cognition/control", json={"command": "stop"}).status_code == 200
    row = completed(client)
    assert row["state"] == "CANCELLED"
    assert row["experiences"][0]["data"]["truncated"] is True
    assert row["actions"] == []


@pytest.mark.parametrize(
    "decision,expected", [("approve", "executed"), ("reject", "rejected"), ("cancel", "cancelled")]
)
def test_human_action_authority_and_idempotency(client, monkeypatch, decision, expected):
    import alive.cognition as cognition

    original = cognition.mock_role

    def draft(role, context):
        output = original(role, context)
        if role == "proposer":
            output.actions[0].kind = "lab_draft"
        return output

    monkeypatch.setattr(cognition, "mock_role", draft)
    start(client)
    lab, _ = observe(client)
    values = wait_for(
        client,
        "/cognition/investigations",
        lambda rows: rows and rows[0]["state"] == "AWAITING_APPROVAL",
    )
    detail = client.get("/api/v1/cognition/investigations/" + values[0]["id"]).json()
    action = detail["actions"][0]
    assert client.get("/api/v1/lab/world/" + lab["id"]).json()["draft"] == ""
    result = client.post(
        "/api/v1/cognition/actions/" + action["id"] + "/decision", json={"decision": decision}
    )
    assert result.status_code == 200, result.text
    assert result.json()["status"] == expected
    after = client.get("/api/v1/lab/world/" + lab["id"]).json()
    assert bool(after["draft"]) == (decision == "approve")
    if decision == "approve":
        again = client.post(
            "/api/v1/cognition/actions/" + action["id"] + "/decision", json={"decision": "approve"}
        )
        assert again.json()["status"] == "executed"
        assert client.get("/api/v1/lab/world/" + lab["id"]).json()["version"] == after["version"]


def test_consequential_action_cannot_be_approved(client, monkeypatch):
    import alive.cognition as cognition

    original = cognition.mock_role

    def external(role, context):
        output = original(role, context)
        if role == "proposer":
            output.actions[0].kind = "external_message"
        return output

    monkeypatch.setattr(cognition, "mock_role", external)
    start(client)
    observe(client)
    actions = wait_for(
        client, "/cognition/actions", lambda rows: rows and rows[0]["status"] == "awaiting_approval"
    )
    response = client.post(
        "/api/v1/cognition/actions/" + actions[0]["id"] + "/decision", json={"decision": "approve"}
    )
    assert response.status_code == 403
    assert client.get("/api/v1/cognition/actions").json()[0]["status"] == "awaiting_approval"


def test_attention_protocol_and_evidence_integrity():
    good = attention("Claim: Helios battery | endurance_hours | 17;", ["battery endurance"])
    noise = attention("Decorative clock pulse 17", ["battery endurance"])
    assert good["score"] > noise["score"] and noise["relevance"] == 0
    bids = [
        {"id": "b", "created_at": 1, "attention": good},
        {"id": "a", "created_at": 1, "attention": good},
    ]
    assert [b["id"] for b in rank(bids)] == ["a", "b"]
    with pytest.raises(ValidationError):
        RoleOutput.model_validate({"summary": "malformed"})
    output = mock_role("proposer", {"claims": [], "sources": []})
    raw = output.model_dump()
    raw["claims"] = [
        {"subject": "A", "predicate": "B", "value": "C", "evidence_refs": ["invented"]}
    ]
    # Validate schema before validating references, as the runtime does.
    output = RoleOutput.model_validate(raw)
    with pytest.raises(ValueError, match="unknown"):
        validate_references(output, {})
    result = evaluate(
        [{"subject": "A", "predicate": "B", "value": "C", "evidence_refs": []}], [], []
    )
    assert result["status"] == "INCONCLUSIVE"


def test_accepted_commitment_cannot_be_starved_by_fresh_high_bids():
    from datetime import timedelta

    from alive.models import now

    timestamp = now()
    candidates = [
        {
            "id": "commitment",
            "created_at": timestamp - timedelta(seconds=61),
            "provenance": {"source_type": "commitment"},
            "attention": {"score": 0.5},
        },
        {
            "id": "fresh",
            "created_at": timestamp,
            "provenance": {"source_type": "managed_browser"},
            "attention": {"score": 0.95},
        },
    ]
    assert rank(candidates, timestamp)[0]["id"] == "commitment"
