"""ALIVE-DEMO-INTEGRATION-01: the one-click tour, its guards and its failure paths."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.demo_live_01 import DIRECTORY
from tests.conftest import TOKEN
from tests.test_research_memory import ROOT, goal

TOUR = "/api/v1/demo-tour"
KEYS = [
    "observe_original",
    "save_memory",
    "anchor",
    "observe_later",
    "compare_consent",
    "compare",
    "abstention_consent",
    "abstention",
    "before_withdrawal",
    "withdraw",
    "after_withdrawal",
    "audit",
]


@pytest.fixture
def settings(settings):
    settings.alive_relationship_allow_test_providers = True
    settings.alive_demo_tour_enabled = True
    return settings


@pytest.fixture(autouse=True)
def no_external_models(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The demonstration must never reach an external provider")

    monkeypatch.setattr("alive.providers.MetaProvider.structured", forbidden)
    monkeypatch.setattr("alive.providers.MetaProvider._request", forbidden)
    monkeypatch.setattr("alive.providers.MetaProvider.discover", forbidden)


def start(client, **body):
    response = client.post(TOUR + "/runs", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def step(run, key):
    return next(item for item in run["steps"] if item["key"] == key)


def owner_goals(client):
    return client.get(ROOT).json()["goals"]


def relationships(client, goal_id):
    return client.get(ROOT + "/research/relationships", params={"goal_id": goal_id}).json()


def test_info_names_the_fixture_provider_and_pinned_sources(client):
    info = client.get(TOUR).json()
    assert info["enabled"] is True
    assert info["label"] == "DETERMINISTIC LOCAL FIXTURE — NOT LIVE META"
    assert info["provider"] == {"id": "local_fixture_claim", "external": False}
    assert [s["id"] for s in info["sources"]] == [
        "python-3.11",
        "python-3.12",
        "synthetic-no-change",
    ]
    assert all(len(s["mirror_html_sha256"]) == 64 for s in info["sources"])
    assert "no model is called" in info["consent_text"]


def test_one_click_run_completes_with_real_rows_and_bound_pairs(client):
    run = start(client)
    assert run["status"] == "completed", run["error"]
    assert [s["key"] for s in run["steps"]] == KEYS
    assert all(s["status"] == "ok" for s in run["steps"])
    assert run["provider"] == "local_fixture_claim"
    assert run["label"].startswith("DETERMINISTIC LOCAL FIXTURE")

    memory_id = step(run, "save_memory")["evidence"]["memory_id"]
    assert step(run, "save_memory")["evidence"]["source_identity"]["id"] == "python-3.11"
    assert step(run, "save_memory")["evidence"]["model_note_created"] is False
    later = step(run, "observe_later")["evidence"]
    compare = step(run, "compare")["evidence"]
    assert compare["bound_pair"] == {
        "goal_id": run["goal_id"],
        "current_url": later["url"],
        "current_sha256": later["text_sha256"],
        "historical_memory_id": memory_id,
    }
    assert compare["relation_type"] == "explicit_supersession"
    assert compare["historical_quote_retained_in_current"] is True
    assert compare["is_candidate_not_truth"] is True
    assert "Deprecated since version 3.12" in compare["supersession_basis_quote"]

    abstention = step(run, "abstention")["evidence"]
    assert abstention["abstained"] is True and abstention["connection"] is None
    assert abstention["relationship"] == "insufficient_evidence"
    assert abstention["bound_pair"]["current_sha256"] == abstention["text_sha256"]
    assert abstention["bound_pair"]["current_sha256"] != later["text_sha256"]
    assert abstention["bound_pair"]["historical_memory_id"] == memory_id

    for key in ("compare_consent", "abstention_consent"):
        evidence = step(run, key)["evidence"]
        assert evidence["provider"]["id"] == "local_fixture_claim"
        assert evidence["external"] is False


def test_pause_then_withdraw_uses_the_real_endpoints(client):
    run = start(client, pause_before_withdrawal=True)
    assert run["status"] == "paused"
    assert [s["key"] for s in run["steps"]] == KEYS[:9]
    goal_id = run["goal_id"]
    memory_id = step(run, "save_memory")["evidence"]["memory_id"]
    connection_id = step(run, "compare")["evidence"]["connection_id"]

    # Before: ordinary public reads, not the tour's own bookkeeping, show the rows.
    memories = client.get(ROOT + "/research/memories", params={"goal_id": goal_id}).json()
    assert [m["id"] for m in memories["memories"]] == [memory_id]
    before = relationships(client, goal_id)
    assert [c["id"] for c in before["connections"]] == [connection_id]
    assert len(before["analyses"]) == 2

    finished = client.post(f"{TOUR}/runs/{run['run_id']}/withdraw", json={})
    assert finished.status_code == 200, finished.text
    done = finished.json()
    assert done["status"] == "completed"
    assert [s["key"] for s in done["steps"]] == KEYS

    # After: the same ordinary reads no longer return the source or anything built on it.
    assert (
        client.get(ROOT + "/research/memories", params={"goal_id": goal_id}).json()["memories"]
        == []
    )
    after = relationships(client, goal_id)
    assert after["connections"] == [] and after["analyses"] == []
    snapshot_id = step(run, "observe_later")["evidence"]["snapshot_id"]
    retrieved = client.post(
        ROOT + "/research/retrieve", json={"snapshot_id": snapshot_id, "top_k": 3}
    ).json()
    assert retrieved["results"] == [] and retrieved["abstained"] is True


def test_withdrawal_is_audited_not_erased(client):
    run = start(client)
    audit = step(run, "audit")["evidence"]
    status = {row["label"]: row["status"] for row in audit["rows"]}
    assert status["memory"] == "withdrawn"
    assert status["connection"] == "invalidated" and status["analysis"] == "invalidated"
    assert audit["physically_deleted"] is False
    assert len(audit["withdrawal_events"]) == 1
    assert "excerpt" not in json.dumps(audit) and "tzinfo" not in json.dumps(audit)


def test_persisted_state_is_identical_after_an_app_restart(client, settings):
    run = start(client)
    run_id, goal_id = run["run_id"], run["goal_id"]
    boot_before = client.get(TOUR).json()["boot"]["id"]
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as reopened:
        info = reopened.get(TOUR).json()
        assert info["boot"]["id"] != boot_before  # genuinely a new process
        assert [r["run_id"] for r in info["runs"]] == [run_id]
        again = reopened.get(f"{TOUR}/runs/{run_id}").json()
        assert [s["key"] for s in again["steps"]] == KEYS
        assert again["live"]["memory_active"] is False
        assert again["live"]["connection_ids"] == [] and again["live"]["analysis_ids"] == []
        assert {r["status"] for r in again["audit"]["rows"]} == {"withdrawn", "invalidated"}
        listed = reopened.get(ROOT + "/research/relationships", params={"goal_id": goal_id}).json()
        assert listed["connections"] == [] and listed["analyses"] == []


def test_a_second_run_is_separate_and_never_touches_owner_data(client):
    owner = goal(client, "My own research goal")
    first = start(client, pause_before_withdrawal=True)
    second = start(client)
    assert first["goal_id"] not in (second["goal_id"], owner["id"])
    assert second["status"] == "completed"
    # The paused first run is untouched by the second run's withdrawal.
    live = client.get(f"{TOUR}/runs/{first['run_id']}").json()["live"]
    assert live["memory_active"] is True and len(live["connection_ids"]) == 1
    assert {g["id"] for g in owner_goals(client)} == {
        owner["id"],
        first["goal_id"],
        second["goal_id"],
    }
    assert (
        client.get(ROOT + "/research/memories", params={"goal_id": owner["id"]}).json()["memories"]
        == []
    )
    assert [r["number"] for r in client.get(TOUR).json()["runs"]] == [2, 1]


def test_analyses_never_cross_between_goals(client):
    first = start(client, pause_before_withdrawal=True)
    second = start(client, pause_before_withdrawal=True)
    ids = {}
    for name, run in (("first", first), ("second", second)):
        listed = relationships(client, run["goal_id"])
        ids[name] = {a["id"] for a in listed["analyses"]}
        assert len(ids[name]) == 2
        for analysis in listed["analyses"]:
            assert analysis["data"]["goal_id"] == run["goal_id"]
            assert (
                analysis["data"]["historical_memory_id"]
                == step(run, "save_memory")["evidence"]["memory_id"]
            )
    assert ids["first"].isdisjoint(ids["second"])


def test_dismissing_the_candidate_does_not_alter_the_abstention_binding(client):
    run = start(client, pause_before_withdrawal=True)
    connection_id = step(run, "compare")["evidence"]["connection_id"]
    before = {a["id"]: a["data"] for a in relationships(client, run["goal_id"])["analyses"]}
    response = client.post(
        ROOT + f"/research/connections/{connection_id}/feedback", json={"useful": False}
    )
    assert response.status_code == 200, response.text
    after = {a["id"]: a["data"] for a in relationships(client, run["goal_id"])["analyses"]}
    abstention = step(run, "abstention")["evidence"]
    assert after[abstention["analysis_id"]]["current_sha256"] == abstention["text_sha256"]
    assert (
        after[abstention["analysis_id"]]["historical_memory_id"]
        == before[abstention["analysis_id"]]["historical_memory_id"]
    )


@pytest.mark.parametrize(
    "tour,fixture",
    [(False, True), (True, False), (False, False)],
)
def test_disabled_runtime_refuses_and_writes_nothing(client, tour, fixture):
    settings = client.app.state.kernel.settings
    settings.alive_demo_tour_enabled, settings.alive_relationship_allow_test_providers = (
        tour,
        fixture,
    )
    info = client.get(TOUR).json()
    assert info["enabled"] is False and info["reason"]
    response = client.post(TOUR + "/runs", json={})
    assert response.status_code == 403
    assert owner_goals(client) == []
    assert client.get(TOUR).json()["runs"] == []


def test_authentication_is_required(client):
    anonymous = TestClient(client.app)
    assert anonymous.get(TOUR).status_code == 401
    assert anonymous.post(TOUR + "/runs", json={}).status_code == 401
    wrong = {"Authorization": "Bearer wrong-token-wrong-token-wrong-0000"}
    assert anonymous.post(TOUR + "/runs", json={}, headers=wrong).status_code == 401
    assert owner_goals(client) == []


def test_unavailable_pinned_source_fails_closed_before_any_row(client, monkeypatch):
    monkeypatch.setattr("alive.demo_tour.DIRECTORY", Path("does-not-exist"))
    response = client.post(TOUR + "/runs", json={})
    assert response.status_code == 409
    assert "unavailable" in response.json()["error"]["message"]
    assert owner_goals(client) == [] and client.get(TOUR).json()["runs"] == []


def test_changed_pinned_source_fails_closed_before_any_row(client, monkeypatch, tmp_path):
    shutil.copytree(DIRECTORY, tmp_path / "fixtures")
    capture = tmp_path / "fixtures" / "python-3.12.capture.json"
    data = json.loads(capture.read_text(encoding="utf-8"))
    data["text"] = data["text"].replace("Deprecated", "Not deprecated")
    capture.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("alive.demo_tour.DIRECTORY", tmp_path / "fixtures")
    response = client.post(TOUR + "/runs", json={})
    assert response.status_code == 409
    assert "recorded hash" in response.json()["error"]["message"]
    assert owner_goals(client) == []


def test_a_source_that_is_not_the_pinned_bytes_stops_the_run(client, monkeypatch):
    from alive import demo_tour

    real = demo_tour.load_captures()
    forged = {name: dict(data) for name, data in real.items()}
    forged["python-3.11"]["text"] = forged["python-3.11"]["text"] + " Extra, unpinned sentence."
    monkeypatch.setattr("alive.demo_tour.load_captures", lambda: forged)
    run = start(client)
    assert run["status"] == "failed"
    assert "source identity was not verified" in run["error"]
    last = run["steps"][-1]
    assert last["status"] == "failed" and last["key"] == "save_memory"
    assert not any(s["key"] in ("compare", "abstention", "withdraw") for s in run["steps"])
    assert relationships(client, run["goal_id"])["connections"] == []


def test_the_provider_cannot_be_anything_but_the_local_fixture(client, monkeypatch):
    source = (
        Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("alive/demo_tour.py")
        .read_text(encoding="utf-8")
    )
    assert '"meta"' not in source and "MetaProvider" not in source
    monkeypatch.setattr("alive.demo_tour.PROVIDER", "meta")
    run = start(client)  # the runtime refuses Meta; the sentinel proves nothing was dispatched
    assert run["status"] == "failed"
    assert "refused (403)" in run["error"] and "disabled" in run["error"]
    assert not any(s["key"] in ("compare", "withdraw") for s in run["steps"] if s["status"] == "ok")


def test_a_failed_run_never_displays_a_finding_and_cannot_be_withdrawn(client, monkeypatch):
    monkeypatch.setattr("alive.demo_tour.PROVIDER", "meta")
    run = start(client)
    assert run["status"] == "failed"
    assert relationships(client, run["goal_id"]) == {
        "analyses": [],
        "connections": [],
        "current_analyses": [],
        "paired_analyses": [],
    }
    response = client.post(f"{TOUR}/runs/{run['run_id']}/withdraw", json={})
    assert response.status_code == 409


def test_unknown_run_is_404_and_completed_withdraw_is_idempotent(client):
    assert client.get(TOUR + "/runs/does-not-exist").status_code == 404
    assert client.post(TOUR + "/runs/does-not-exist/withdraw", json={}).status_code == 404
    run = start(client)
    again = client.post(f"{TOUR}/runs/{run['run_id']}/withdraw", json={})
    assert again.status_code == 200 and again.json()["status"] == "completed"
    assert [s["key"] for s in again.json()["steps"]] == KEYS


def test_the_run_requests_no_extra_fields(client):
    assert client.post(TOUR + "/runs", json={"provider": "meta"}).status_code == 422
    assert owner_goals(client) == []


def forge_preview(client, monkeypatch, change):
    """Make the public preview endpoint misbehave, to prove the tour's own guards fire."""
    real = client.app.state.relationships.preview

    async def forged(*args, **kwargs):
        consent = await real(*args, **kwargs)
        return change(consent)

    async def never(*args, **kwargs):
        raise AssertionError("authorize must not be reached after a refused preview")

    monkeypatch.setattr(client.app.state.relationships, "preview", forged)
    monkeypatch.setattr(client.app.state.relationships, "authorize", never)


def test_tour_refuses_a_consent_naming_a_non_fixture_provider(client, monkeypatch):
    def external(consent):
        return consent | {"provider": {"id": "meta", "model": "m", "external": True}}

    forge_preview(client, monkeypatch, external)
    run = start(client)
    assert run["status"] == "failed"
    assert "not the local fixture provider" in run["error"]
    assert relationships(client, run["goal_id"])["connections"] == []


def test_tour_refuses_a_consent_for_a_different_source_pair(client, monkeypatch):
    def other_source(consent):
        return consent | {"preview": consent["preview"] | {"current_sha256": "0" * 64}}

    forge_preview(client, monkeypatch, other_source)
    run = start(client)
    assert run["status"] == "failed"
    assert "not bound to this exact source pair" in run["error"]
    assert not any(s["key"] == "compare" and s["status"] == "ok" for s in run["steps"])


def test_tour_fails_if_withdrawal_does_not_actually_retire_the_source(client, monkeypatch):
    async def pretend(research_id):
        return {"status": "withdrawn", "idempotent": False}

    monkeypatch.setattr(client.app.state.research, "withdraw", pretend)
    run = start(client)
    assert run["status"] == "failed"
    assert "still returned by an ordinary read" in run["error"]
    assert not any(s["key"] == "after_withdrawal" and s["status"] == "ok" for s in run["steps"])
