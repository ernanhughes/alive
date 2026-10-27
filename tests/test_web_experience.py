import asyncio
import json
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.web_experience import WebCompanion, digest, goal_relevance
from tests.conftest import TOKEN

ROOT = "/api/v1/browser-experience"
URL = "https://docs.python.org/3/tutorial/"
TEXT = "Python is an easy to learn, powerful programming language. This excerpt is incomplete."


def post(client, path, body, expected=200):
    response = client.post(ROOT + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def setup(client):
    goal = post(client, "/goals", {"instruction": "Help me decide where to start learning Python"})
    grant = consent(client, goal["id"])
    return goal, grant


def consent(client, goal_id):
    return post(
        client,
        "/grants",
        {"goal_id": goal_id, "url": URL, "tab_key": "test-session-tab", "approved": True},
    )


def snapshot(client, grant, text=TEXT, expected=200):
    return post(
        client,
        "/snapshots",
        {
            "grant_id": grant["id"],
            "url": URL,
            "title": "Tutorial",
            "text": text,
            "reviewed_sha256": digest(text),
        },
        expected,
    )


def analyse(client, shot, expected=200):
    return post(
        client,
        "/analyse",
        {
            "snapshot_id": shot["snapshot"]["id"],
            "reviewed_sha256": shot["snapshot"]["data"]["sha256"],
            "send_to_meta": True,
        },
        expected,
    )


def wait(client, note_id):
    for _ in range(100):
        row = client.get(ROOT + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def fake_model(monkeypatch, quote="Python is an easy to learn"):
    calls = []

    async def structured(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            text=json.dumps(
                {
                    "summary": "A limited introductory note.",
                    "evidence_quote": quote,
                    "limitations": "Only the selected excerpt was read.",
                }
            ),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", structured)
    return calls


def test_feedback_changes_exact_state_choice_and_survives_restart(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    goal, grant = setup(client)
    first = snapshot(client, grant)
    note = wait(client, analyse(client, first)["id"])
    assert note["status"] == "validated"
    analyse(client, first, expected=409)
    # A memory alone does not change the action.
    before = snapshot(client, grant)
    assert before["decision"]["action"] == "analyse"
    feedback = post(client, "/feedback", {"note_id": note["id"], "useful": True})
    after = snapshot(client, grant)
    assert before["decision"]["same_state_sha256"] == after["decision"]["same_state_sha256"]
    assert after["decision"]["action"] == "recall"
    assert after["decision"]["without_feedback_action"] == "analyse"
    assert after["decision"]["feedback_id"] == feedback["id"]
    assert after["decision"]["note"]["id"] == note["id"]
    assert after["snapshot"]["data"]["verified_fact"] is False
    assert len(calls) == 1
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        snapshot(reopened, grant, expected=403)
        fresh_grant = consent(reopened, goal["id"])
        recalled = snapshot(reopened, fresh_grant)
        assert recalled["decision"]["note"]["id"] == note["id"]
        assert len(calls) == 1


def test_changed_excerpt_and_negative_feedback_prevent_reuse(client, monkeypatch):
    fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)
    note = wait(client, analyse(client, shot)["id"])
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    changed = snapshot(client, grant, TEXT + " New content.")
    assert changed["decision"]["action"] == "analyse"
    assert changed["snapshot"]["data"]["text_status"] == "changed_excerpt"
    post(client, "/feedback", {"note_id": note["id"], "useful": False})
    assert snapshot(client, grant)["decision"]["action"] == "analyse"


def test_goal_relevance_is_deterministic_and_explicit():
    relevant = goal_relevance("Help me decide where to start learning Python", TEXT)
    assert relevant["policy"] == "deterministic-goal-excerpt-overlap-v1"
    assert relevant["relevant"] is True
    assert "python" in relevant["matched_terms"]

    irrelevant = goal_relevance("Check coolant temperature", TEXT)
    assert irrelevant["relevant"] is False
    assert irrelevant["matched_terms"] == []


def test_unrelated_goal_returns_no_action_without_model_call(client, monkeypatch):
    calls = fake_model(monkeypatch)
    goal = post(client, "/goals", {"instruction": "Check coolant temperature"})
    grant = consent(client, goal["id"])
    shot = snapshot(client, grant)

    decision = shot["decision"]
    assert decision["action"] == "no_action"
    assert decision["without_feedback_action"] == "no_action"
    assert decision["goal_relevance"]["relevant"] is False
    assert decision["inference_calls"] == 0
    assert decision["note"] is None and decision["candidate_note"] is None
    assert "does not match" in decision["reason"]
    assert not calls

    # The API must enforce the same gate, not rely on the panel disabling a button.
    analyse(client, shot, expected=409)
    assert not calls


def test_exact_consent_hash_and_owner_goal_isolation(client, monkeypatch):
    fake_model(monkeypatch)
    goal, grant = setup(client)
    for url in [URL + "?secret=x", URL + "index.html", "https://example.com", URL + "../"]:
        post(
            client,
            "/grants",
            {"goal_id": goal["id"], "url": url, "tab_key": "test-session-tab", "approved": True},
            403,
        )
    post(
        client,
        "/snapshots",
        {
            "grant_id": grant["id"],
            "url": URL,
            "title": "Tutorial",
            "text": TEXT,
            "reviewed_sha256": "wrong",
        },
        403,
    )
    shot = snapshot(client, grant)
    note = wait(client, analyse(client, shot)["id"])
    post(client, "/feedback", {"note_id": note["id"], "useful": True})
    _, other = setup(client)
    assert snapshot(client, other)["decision"]["action"] == "analyse"
    post(client, "/grants/" + grant["id"] + "/revoke", {})
    snapshot(client, grant, expected=403)
    analyse(client, shot, expected=403)


def test_zero_governor_budget_blocks_calls(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)
    assert (
        client.post("/api/v1/cognition/configuration", json={"session_calls": 0}).status_code == 200
    )
    analyse(client, shot, expected=409)
    assert not calls


def test_bad_citation_preserves_failure_and_consumes_reservation(client, monkeypatch):
    fake_model(monkeypatch, "invented evidence")
    _, grant = setup(client)
    note = wait(client, analyse(client, snapshot(client, grant))["id"])
    assert note["status"] == "failed"
    assert note["data"]["error"] == "ValueError"
    assert note["data"]["charged_tokens"] == note["data"]["reserved_tokens"]
    post(client, "/feedback", {"note_id": note["id"], "useful": True}, 409)


def test_stop_cancels_paid_worker_and_settles_unknown_usage(client, monkeypatch):
    import asyncio

    async def blocked(*args, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", blocked)
    _, grant = setup(client)
    note_id = analyse(client, snapshot(client, grant))["id"]
    assert client.post("/api/v1/cognition/configuration", json={}).status_code == 409
    assert client.post("/api/v1/alive/stop").status_code == 200
    row = wait(client, note_id)
    assert row["status"] == "failed"
    assert row["data"]["error"] == "CancelledError"
    assert row["data"]["charged_tokens"] == row["data"]["reserved_tokens"]
    snapshot(client, grant, expected=403)


def test_revocation_before_inference_prevents_provider_call(client, monkeypatch):
    calls = fake_model(monkeypatch)
    _, grant = setup(client)
    shot = snapshot(client, grant)

    original_execute = WebCompanion.execute

    async def delayed_execute(self, note_id, context, cfg, reserve):
        await asyncio.sleep(0.5)
        return await original_execute(self, note_id, context, cfg, reserve)

    async def no_cancel(self):
        return None

    monkeypatch.setattr(WebCompanion, "execute", delayed_execute)
    monkeypatch.setattr(WebCompanion, "cancel", no_cancel)

    note_id = analyse(client, shot)["id"]
    post(client, "/grants/" + grant["id"] + "/revoke", {})
    row = wait(client, note_id)

    assert row["status"] == "failed"
    assert row["data"]["error"] == "PermissionError"
    assert row["data"]["charged_tokens"] == row["data"]["reserved_tokens"]
    assert not calls
    assert client.get(ROOT).json()["active"] is False
