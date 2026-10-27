"""Regression cases found in the independent ALIVE-10 review."""

import copy

import pytest
from sqlalchemy import select

from alive.web_models import WebExperience
from tests.test_web_experience import ROOT, TEXT, analyse, fake_model, post, setup, snapshot, wait


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
