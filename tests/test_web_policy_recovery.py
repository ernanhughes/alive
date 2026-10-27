"""Regression cases found in the independent ALIVE-10 review."""

import copy

import pytest
from sqlalchemy import select

from alive.web_models import WebExperience
from tests.test_web_experience import (
    ROOT,
    TEXT,
    analyse,
    consent,
    fake_model,
    post,
    setup,
    snapshot,
    wait,
)


def negative_history(client):
    _, grant = setup(client)
    for index in range(3):
        shot = snapshot(client, grant, TEXT + f" Independent observation {index}.")
        note = wait(client, analyse(client, shot)["id"])
        post(client, "/feedback", {"note_id": note["id"], "useful": False})
    return grant


def test_probe_due_cannot_authorise_old_paused_snapshots(client, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    paused = [snapshot(client, grant, TEXT + f" Paused observation {i}.") for i in range(3)]
    assert all(shot["decision"]["action"] == "no_action" for shot in paused)
    before = client.get(ROOT).json()["policy"]["data"]
    for shot in paused:
        analyse(client, shot, expected=409)
    assert len(calls) == 3
    assert client.get(ROOT).json()["policy"]["data"] == before

    probe = snapshot(client, grant, TEXT + " The explicitly eligible probe.")
    assert probe["snapshot"]["data"]["probe_authorized"] is True
    note = wait(client, analyse(client, probe)["id"])
    assert note["data"]["probe_authorized"] is True
    assert len(calls) == 4
    analyse(client, probe, expected=409)
    for shot in paused:
        analyse(client, shot, expected=409)
    assert len(calls) == 4


def test_rejected_probe_keeps_eligibility_without_provider_dispatch(client, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    for index in range(3):
        snapshot(client, grant, TEXT + f" Paused {index}.")
    probe = snapshot(client, grant, TEXT + " Probe with a temporary budget failure.")
    assert client.post("/api/v1/cognition/configuration", json={"session_calls": 0}).is_success
    before = client.get(ROOT).json()["policy"]["data"]
    analyse(client, probe, expected=409)
    assert len(calls) == 3
    assert client.get(ROOT).json()["policy"]["data"] == before
    assert client.get(ROOT).json()["corrections"] == []
    assert client.post("/api/v1/cognition/configuration", json={"session_calls": 30}).is_success
    note = wait(client, analyse(client, probe)["id"])
    assert note["status"] == "validated"
    assert len(calls) == 4


@pytest.mark.parametrize("keep_history", [False, True])
def test_v1_migration_preserves_latest_revision_not_latest_created_row(
    client, monkeypatch, keep_history
):
    fake_model(monkeypatch)
    _, grant = setup(client)
    first = wait(client, analyse(client, snapshot(client, grant))["id"])
    first_rating = post(client, "/feedback", {"note_id": first["id"], "useful": True})
    second = wait(client, analyse(client, snapshot(client, grant))["id"])
    second_rating = post(client, "/feedback", {"note_id": second["id"], "useful": True})
    post(client, "/feedback", {"note_id": first["id"], "useful": False})

    async def migrate():
        web = client.app.state.web
        async with web.k.lock, web.k.db.sessions.begin() as session:
            policy = await web.policy_row(session)
            # ALIVE-09 updated feedback in place and stored its effective policy version.
            legacy = {
                "policy_id": "companion-feedback-usefulness-v1",
                "version": 3,
                "contexts": {},
                "history": [],
            }
            a = await session.get(WebExperience, first_rating["id"])
            b = await session.get(WebExperience, second_rating["id"])
            assert a.created_at < b.created_at
            effective_at = a.data["updated_at"]
            if keep_history:
                legacy["history"] = [{"feedback_id": a.id, "at": effective_at}]
            policy.data = copy.deepcopy(legacy)
            # v1 did not store updated_at on its in-place revisions.
            a.data = {k: v for k, v in a.data.items() if k != "updated_at"} | {
                "policy_version_after": 3
            }
            b.data = {k: v for k, v in b.data.items() if k != "updated_at"} | {
                "policy_version_after": 2
            }
            await session.flush()
            migrated = await web.policy_row(session)
            assert migrated.id != policy.id
            assert policy.data == legacy
            assert migrated.data["migrated_from"]["row_id"] == policy.id
            unit = next(iter(next(iter(migrated.data["contexts"].values()))["evidence"].values()))
            assert unit["useful"] is False
            assert unit["feedback_id"] == a.id
            assert unit["note_id"] == first["id"]
            assert unit["updated_at"] == (effective_at if keep_history else None)
            assert (await web.policy_row(session)).id == migrated.id
        async with web.k.db.sessions() as session:
            policies = (
                await session.scalars(select(WebExperience).where(WebExperience.kind == "policy"))
            ).all()
            assert len(policies) == 2

    client.portal.call(migrate)
    assert snapshot(client, grant)["decision"]["action"] == "analyse"


def test_repeated_paused_excerpt_does_not_advance_probe(client, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    text = TEXT + " Repeated paused excerpt."
    first = snapshot(client, grant, text)["decision"]
    assert first["action"] == "no_action"
    assert first["adaptive_policy"]["suppressions"] == 1
    version = first["policy_version"]
    for _ in range(3):
        repeated = snapshot(client, grant, text)["decision"]
        assert repeated["action"] == "no_action"
        assert repeated["repeated_suppression"] is True
        assert repeated["adaptive_policy"]["repeated_suppression"] is True
        assert repeated["adaptive_policy"]["suppressions"] == 1
        assert repeated["policy_version"] == version
        assert repeated["adaptive_policy"]["probe_due"] is False
    policy = client.get(ROOT).json()["policy"]["data"]
    context = next(iter(policy["contexts"].values()))
    assert len(context["suppressed_excerpts"]) == 1
    assert context["probes"] == 0
    for index in range(2):
        snapshot(client, grant, TEXT + f" New paused excerpt {index}.")
    probe = snapshot(client, grant, TEXT + " Fresh probe excerpt.")["decision"]
    assert probe["action"] == "analyse"
    assert probe["probe"] is True
    assert len(calls) == 3


def test_repeated_rated_excerpt_does_not_advance_suppression(client, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    rated_text = TEXT + " Independent observation 0."
    before = client.get(ROOT).json()["policy"]["data"]
    for _ in range(3):
        decision = snapshot(client, grant, rated_text)["decision"]
        assert decision["action"] == "no_action"
        assert decision["repeated_suppression"] is True
        assert decision["adaptive_policy"]["suppressions"] == 0
    assert client.get(ROOT).json()["policy"]["data"] == before
    for index in range(3):
        snapshot(client, grant, TEXT + f" Fresh paused after rated {index}.")
    probe = snapshot(client, grant, TEXT + " Probe after repeated rated.")["decision"]
    assert probe["action"] == "analyse"
    assert probe["probe"] is True
    assert len(calls) == 3


def test_negative_exact_excerpt_cannot_become_probe(client, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    for index in range(3):
        snapshot(client, grant, TEXT + f" Paused before stale exact {index}.")
    before = client.get(ROOT).json()["policy"]["data"]
    stale = snapshot(client, grant, TEXT + " Independent observation 0.")["decision"]
    assert stale["action"] == "no_action"
    assert stale["probe_blocked"] == "excerpt_not_fresh"
    assert stale["adaptive_policy"]["probe_due"] is True
    assert stale["adaptive_policy"]["probe"] is False
    assert client.get(ROOT).json()["policy"]["data"] == before
    probe = snapshot(client, grant, TEXT + " Fresh probe after stale.")["decision"]
    assert probe["action"] == "analyse"
    assert probe["probe"] is True
    assert len(calls) == 3


def test_repeated_paused_excerpt_after_restart_does_not_advance(client, settings, monkeypatch):
    calls = fake_model(monkeypatch)
    grant = negative_history(client)
    text = TEXT + " Restart repeated paused excerpt."
    first = snapshot(client, grant, text)["decision"]
    assert first["action"] == "no_action"
    assert first["adaptive_policy"]["suppressions"] == 1
    version = first["policy_version"]

    client.__exit__(None, None, None)
    from fastapi.testclient import TestClient

    from alive.app import create_app
    from tests.conftest import TOKEN

    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as reopened:
        fresh = consent(reopened, grant["parent_id"])
        repeated = snapshot(reopened, fresh, text)["decision"]
        assert repeated["action"] == "no_action"
        assert repeated["repeated_suppression"] is True
        assert repeated["adaptive_policy"]["suppressions"] == 1
        assert repeated["policy_version"] == version
        assert len(calls) == 3
