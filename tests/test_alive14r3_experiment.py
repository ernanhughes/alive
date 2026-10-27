"""Focused qualification of the frozen ALIVE-14-R3 runner and protocol."""

import json

import pytest

import scripts.alive14r3_experiment as runner


def protocol():
    return json.loads(runner.PROTOCOL.read_text(encoding="utf-8"))


def test_protocol_v3_is_frozen_neutral_and_separated_from_the_answer_key():
    frozen = protocol()
    assert runner.canonical_sha256(runner.PROTOCOL) == runner.EXPECTED_PROTOCOL_SHA256
    assert runner.canonical_sha256(runner.ANSWER_KEY) == runner.EXPECTED_ANSWER_KEY_SHA256
    assert frozen["protocol_version"] == "alive14r3-paired-v3"
    assert frozen["primary_endpoint"]["name"] == "owner_rated_supported_usefulness"
    assert frozen["model_plan"]["calls"] == 18
    assert frozen["model_plan"]["retries"] == 0
    assert frozen["answer_key"]["sealed_until_reveal"] is True
    questions = [task["question"].lower() for task in frozen["tasks"]]
    for question in questions:
        assert "historical" not in question
        assert "previous" not in question
        assert "older" not in question
        assert "prior" not in question
    task_ids = [task["task_id"] for task in frozen["tasks"]]
    assert sorted(frozen["task_order"]) == sorted(task_ids)
    assert frozen["task_order"] != task_ids
    assert "reference_answer" not in json.dumps(frozen)
    answer_key = json.loads(runner.ANSWER_KEY.read_text(encoding="utf-8"))
    assert set(answer_key["tasks"]) == set(task_ids)
    assert all(
        "reference_answer" in answer_key["tasks"][task_id]
        and "prohibited_claims" in answer_key["tasks"][task_id]
        for task_id in task_ids
    )


def test_full_synthetic_run_reaches_every_phase_with_a_null_rating_pattern(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    runner.full_synthetic()
    frozen = protocol()
    directory = runner.run_dir("synthetic", frozen)
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "archived"
    assert state["parity"] == {
        "instructions_equal": True,
        "schema_equal": True,
        "a_has_no_historical_keys": True,
        "b_adds_only_historical_keys": True,
        "answer_key_not_in_requests": True,
    }
    assert state["blind"]["randomized_creation_order"] is True
    assert state["blind"]["assignment_commitment"]
    assert state["grant_reactivations"]["count"] == len(frozen["tasks"])
    results = json.loads((directory / "results.json").read_text(encoding="utf-8"))
    assert results["commitment_verified"] is True
    assert len(results["ratings"]) == 27
    assert all(
        row["data"]["provenance"] == "synthetic_owner_endpoint" and row["data"]["synthetic"] is True
        for row in results["ratings"]
    )
    analysis = json.loads((directory / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["synthetic"] is True
    assert analysis["conditions"]["A"]["n"] == 9
    assert analysis["conditions"]["B"]["n"] == 9
    assert analysis["conditions"]["C"]["n"] == 9
    assert (
        analysis["conditions"]["A"]["supported_useful"]
        == analysis["conditions"]["B"]["supported_useful"]
    )
    assert all(row["difference_b_minus_a"] == 0 for row in analysis["paired"])
    assert "Synthetic ratings are scripted" in analysis["limitations"][0]
    archived = runner.ARCHIVE / state["run_id"]
    assert (archived / "manifest.json").exists()
    assert (archived / "results.json").exists()
    manifest = json.loads((archived / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["synthetic"] is True
    assert manifest["paid_calls"] == 0
    assert "results.json" in manifest["files"]


def test_a_real_run_cannot_execute_without_a_matching_human_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    frozen = protocol()
    runner.prepare("real")
    directory = runner.run_dir("real", frozen)
    with pytest.raises(SystemExit):
        runner.execute("real")
    state = json.loads((directory / "state.json").read_text(encoding="utf-8"))
    approval = {
        "run_id": state["run_id"],
        "protocol_sha256": state["protocol_sha256"],
        "provider": "meta",
        "model": state["model"],
        "task_count": len(state["tasks"]),
        "calls": state["totals"]["calls"],
        "payload_sha256s": {row["task_id"]: row["payload_sha256s"] for row in state["tasks"]},
        "max_input_tokens": state["totals"]["reserved_tokens"],
        "max_output_tokens": 1536,
        "max_usd": 0.45,
        "no_retries": True,
        "human_approval": True,
        "approved_by": "test-owner",
        "approved_at": state["created_at"],
    }
    wrong = json.loads(json.dumps(approval))
    first = state["tasks"][0]["task_id"]
    wrong["payload_sha256s"][first]["A"] = "0" * 64
    path = tmp_path / "wrong-approval.json"
    path.write_text(json.dumps(wrong), encoding="utf-8")
    with pytest.raises(SystemExit):
        runner.approve("real", approval_file=str(path))
    path.write_text(json.dumps(approval), encoding="utf-8")
    approved = runner.approve("real", approval_file=str(path))
    assert approved["phase"] == "approved"
    assert approved["approval"]["human_approval"] is True


def test_phases_do_not_silently_authorise_the_next(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNS", tmp_path / "runs")
    monkeypatch.setattr(runner, "ARCHIVE", tmp_path / "archive")
    runner.prepare("synthetic")
    with pytest.raises(SystemExit):
        runner.reveal("synthetic")
    with pytest.raises(SystemExit):
        runner.archive("synthetic")
    runner.approve("synthetic", synthetic=True)
    with pytest.raises(SystemExit):
        runner.rate("synthetic", synthetic=False)
