import json
import time

import pytest
from pydantic import ValidationError

from alive.cognitive_schema import RoleOutput
from alive.experiment.corpus import audit, generate
from alive.experiment.metrics import price, wilson
from alive.experiment.policy import AlwaysCritic, NeverCritic, SelectiveCritic, calibrate, features
from alive.experiment.schema import Features
from alive.experiment.scoring import score, solve
from alive.experiment.service import mock_decision


def test_corpus_sizes_ground_truth_and_contamination():
    dev, test = generate("calibration"), generate("evaluation")
    result = audit(dev, test)
    assert result["calibration_tasks"] == 48 and result["evaluation_tasks"] == 120
    assert set(result["evaluation_distribution"].values()) == {30}
    assert set(result["calibration_distribution"].values()) == {12}
    assert (
        result["exact_payload_duplicates"] == 0
        and result["max_cross_split_objective_trigram_jaccard"] < 0.65
    )
    assert [t.model_dump() for t in dev] == [t.model_dump() for t in generate("calibration")]
    with pytest.raises(ValueError, match="Duplicate"):
        audit(dev, dev)
    for task in dev + test:
        assert not {
            "id",
            "category",
            "expected",
            "split",
            "verification",
            "scoring_rule",
            "family",
        } & set(task.payload())


@pytest.mark.parametrize(
    "operation,fields,expected",
    [
        ("sum", {"a": 4, "b": 7}, 11),
        ("difference", {"start": 10, "remainder": 6}, 4),
        ("minimum", {"a": 4, "b": 1, "c": 9}, 1),
        ("maximum", {"a": 4, "b": 1, "c": 9}, 9),
        ("ratio", {"numerator": 9, "denominator": 2}, 4.5),
        ("median", {"x": 3, "y": 8, "z": 5}, 5),
        ("weighted_mean", {"value_a": 10, "weight_a": 1, "value_b": 20, "weight_b": 3}, 17.5),
        ("count_at_least", {"v1": 1, "v2": 3, "v3": 5, "v4": 7, "v5": 9, "cutoff": 5}, 3),
        ("fahrenheit", {"temperature_f": 212}, 100),
        ("rate", {"quantity": 60, "hours": 4}, 15),
    ],
)
def test_independent_arithmetic_scoring(operation, fields, expected):
    payload = {
        "subject": "fixture",
        "operation": operation,
        "required_fields": list(fields),
        "sources": [
            {
                "id": "source",
                "authority": "verified",
                "window": "same-window",
                "facts": [{"key": key, "value": value} for key, value in fields.items()],
            }
        ],
    }
    assert solve(payload)["value"] == pytest.approx(expected)
    decision = RoleOutput(
        summary="fixture",
        claims=[
            {
                "subject": "fixture",
                "predicate": "computed_result",
                "value": str(expected),
                "evidence_refs": ["source"],
            }
        ],
        actions=[],
        criticisms=[],
        uncertainties=[],
        recommendation="proceed",
        confidence=0.9,
    )
    assert score(payload, decision)["correct"]
    decision.claims[0].evidence_refs = ["fabricated"]
    assert not score(payload, decision)["correct"]
    assert score(payload, decision)["citation_validity"] == 0


def test_abstention_and_poisoned_instruction_are_evidence_not_authority():
    tasks = generate("calibration")
    for category in ["ambiguous", "contradictory"]:
        task = next(t for t in tasks if t.category == category)
        good = mock_decision(task.payload(), "critic")
        assert score(task.payload(), good)["correct_abstention"]
        good.recommendation = "proceed"
        assert not score(task.payload(), good)["correct"]
    task = next(t for t in tasks if t.category == "adversarial")
    initial = mock_decision(task.payload(), "initial")
    review = mock_decision(task.payload(), "critic")
    assert not score(task.payload(), initial)["correct"]
    assert score(task.payload(), initial)["unsupported_acceptance"]
    assert score(task.payload(), review)["correct"]


def test_policies_only_receive_general_numeric_features():
    state = Features(
        uncertainty=0.8,
        contradiction=0.5,
        evidence_gap=0.2,
        weak_evidence=0.5,
        action_risk=0.7,
        estimated_tokens=1500,
    )
    assert AlwaysCritic().choose(state).invoke and not NeverCritic().choose(state).invoke
    assert SelectiveCritic(0.2).choose(state).invoke
    assert not SelectiveCritic(1.1).choose(state).invoke
    with pytest.raises(ValidationError):
        Features.model_validate(state.model_dump() | {"expected": "answer"})
    task = generate("calibration")[0]
    first = features(task.payload(), mock_decision(task.payload(), "initial"), 1000)
    task.expected = {"status": "FAKE"}
    task.category = "straightforward"
    second = features(task.payload(), mock_decision(task.payload(), "initial"), 1000)
    assert first == second


def test_threshold_calibration_requires_development_and_can_choose_never():
    state = Features(
        uncertainty=0.1,
        contradiction=0,
        evidence_gap=0,
        weak_evidence=0,
        action_risk=0,
        estimated_tokens=1000,
    ).model_dump()
    rows = [
        {
            "split": "calibration",
            "features": state,
            "initial_score": {"correct": True},
            "critic_score": {"correct": True},
            "critic_tokens": 700,
        }
        for _ in range(8)
    ]
    result = calibrate(rows)
    assert result["threshold"] == 1.1 and result["evaluation_labels_used"] is False
    rows[0]["split"] = "evaluation"
    with pytest.raises(ValueError, match="development"):
        calibrate(rows)


def test_rate_card_estimates_and_intervals_are_not_billing():
    assert price(
        {
            "prompt_tokens": 1000000,
            "completion_tokens": 1000000,
            "prompt_tokens_details": {"cached_tokens": 100000},
        }
    ) == pytest.approx(5.39)
    assert price(None) is None
    lo, hi = wilson(4, 4)
    assert lo < 1 and hi == pytest.approx(1)


@pytest.fixture
def experiment_root(tmp_path, monkeypatch):
    import alive.experiment.corpus as corpus
    import alive.experiment.freeze as freeze
    import alive.experiment.service as service

    root = tmp_path / "corpus"
    for module in [corpus, freeze, service]:
        monkeypatch.setattr(module, "ROOT", root)
    corpus.prepare()
    return root


def wait_run(client, run_id):
    for _ in range(400):
        result = client.get("/api/v1/experiments/runs/" + run_id).json()
        if result["status"] != "running":
            return result
        time.sleep(0.03)
    raise AssertionError("Experiment did not finish")


def test_frozen_controlled_calibration_and_pilot(client, experiment_root):
    design = client.post("/api/v1/experiments/freeze-design", json={}).json()
    start = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "calibration",
            "provider": "mock",
            "freeze_id": design["freeze_id"],
            "max_calls": 16,
            "max_tokens": 100000,
        },
    )
    assert start.status_code == 200, start.text
    calibration = wait_run(client, start.json()["id"])
    assert calibration["status"] == "completed" and calibration["data"]["physical_calls"] == 16
    frozen = client.post(
        "/api/v1/experiments/runs/" + calibration["id"] + "/freeze-policy", json={}
    )
    assert frozen.status_code == 200, frozen.text
    pilot = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "pilot",
            "provider": "mock",
            "freeze_id": frozen.json()["freeze_id"],
            "max_calls": 12,
            "max_tokens": 100000,
        },
    ).json()
    outcome = wait_run(client, pilot["id"])
    assert outcome["status"] == "completed", outcome
    assert len(outcome["data"]["rows"]) == 4 and outcome["data"]["physical_calls"] <= 12
    for row in outcome["data"]["rows"]:
        assert set(row["arms"]) == {"always", "never", "selective"}
        assert len({a["shared_initial_ref"] for a in row["arms"].values()}) == 1
        a, s = row["arms"]["always"], row["arms"]["selective"]
        if s["invoked"]:
            assert a["critic_call_ref"] != s["critic_call_ref"]
    assert client.get("/api/v1/experiments/review-pack").json()["full_run_executed"] is False
    assert client.get("/api/v1/cognition").json()["control"]["spent"]["experiment_calls"] >= 24


def test_full_run_needs_exact_freeze_authorization(client, experiment_root):
    from alive.experiment.freeze import seal

    # Controlled policy fixture: no evaluation unsealing and no real model call.
    (experiment_root / "policy-configuration.json").write_text(
        json.dumps({"threshold": 1.1, "cost_weight": 0.03})
    )
    (experiment_root / "calibration-evidence.json").write_text("[]")
    frozen = seal(final=True)
    response = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "full",
            "provider": "mock",
            "freeze_id": frozen["freeze_id"],
            "max_calls": 360,
            "max_tokens": 100000,
        },
    )
    assert response.status_code == 403
    assert client.get("/api/v1/experiments").json() == []
    assert (
        client.post(
            "/api/v1/experiments/authorize-full",
            json={
                "freeze_id": frozen["freeze_id"],
                "confirmation": "AUTHORIZE FROZEN 120 TASK META EVALUATION",
                "max_calls": 360,
                "max_tokens": 100000,
                "session_plan": "TWO_60_TASK_SESSIONS",
            },
        ).status_code
        == 409
    )  # Exact words still cannot bypass a missing live pilot.
    assert (
        client.post(
            "/api/v1/experiments/authorize-full",
            json={
                "freeze_id": frozen["freeze_id"],
                "confirmation": "yes",
                "max_calls": 360,
                "max_tokens": 100000,
                "session_plan": "TWO_60_TASK_SESSIONS",
            },
        ).status_code
        == 422
    )
    original = (experiment_root / "evaluation.sealed.json").read_bytes()
    (experiment_root / "evaluation.sealed.json").write_bytes(original + b" ")
    assert (
        client.post(
            "/api/v1/experiments/authorize-full",
            json={
                "freeze_id": frozen["freeze_id"],
                "confirmation": "AUTHORIZE FROZEN 120 TASK META EVALUATION",
                "max_calls": 360,
                "max_tokens": 100000,
                "session_plan": "TWO_60_TASK_SESSIONS",
            },
        ).status_code
        == 409
    )


def test_governor_exhaustion_prevents_experiment_inference(client, experiment_root):
    client.post("/api/v1/cognition/configuration", json={"session_calls": 0})
    design = client.post("/api/v1/experiments/freeze-design", json={}).json()
    run = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "calibration",
            "provider": "mock",
            "freeze_id": design["freeze_id"],
            "max_calls": 16,
            "max_tokens": 100000,
        },
    ).json()
    result = wait_run(client, run["id"])
    assert result["status"] == "failed" and result["data"]["ledger"] == []
    assert "Governor" in result["data"]["error"]


def test_freeze_manifest_tamper_detected(experiment_root):
    from alive.experiment.freeze import seal, verify

    frozen = seal()
    frozen["files"] = {}  # Removing hashes cannot bypass drift detection.
    (experiment_root / "freeze-design.json").write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match="integrity"):
        verify(frozen["freeze_id"], final=False)


def test_invalid_model_output_is_retained_as_failure(client, experiment_root, monkeypatch):
    import alive.experiment.service as service

    def invalid(*args):
        raise ValueError("controlled invalid output")

    monkeypatch.setattr(service, "mock_decision", invalid)
    frozen = client.post("/api/v1/experiments/freeze-design", json={}).json()
    started = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "calibration",
            "provider": "mock",
            "freeze_id": frozen["freeze_id"],
            "max_calls": 16,
            "max_tokens": 200000,
        },
    ).json()
    run = wait_run(client, started["id"])
    assert len(run["data"]["rows"]) == 8
    assert run["data"]["summary"]["policies"]["always"]["failures"] == 8
    assert all(not row["eligible"] for row in run["data"]["rows"])
    assert (
        client.post("/api/v1/experiments/runs/" + run["id"] + "/freeze-policy", json={}).status_code
        == 409
    )


def test_cancel_settles_unknown_provider_usage_without_replay(client, experiment_root, monkeypatch):
    import asyncio

    from alive.providers import MetaProvider

    async def discover(self):
        return {"models": ["muse-spark-1.3"]}

    async def waiting(*args, **kwargs):
        await asyncio.sleep(300)

    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", waiting)
    frozen = client.post("/api/v1/experiments/freeze-design", json={}).json()
    started = client.post(
        "/api/v1/experiments/runs",
        json={
            "phase": "calibration",
            "provider": "meta",
            "freeze_id": frozen["freeze_id"],
            "max_calls": 16,
            "max_tokens": 100000,
        },
    ).json()
    for _ in range(100):
        run = client.get("/api/v1/experiments/runs/" + started["id"]).json()
        if run["data"]["ledger"]:
            break
        time.sleep(0.01)
    assert client.post("/api/v1/experiments/stop", json={}).status_code == 200
    run = client.get("/api/v1/experiments/runs/" + started["id"]).json()
    assert run["status"] == "cancelled" and run["data"]["physical_calls"] == 1
    assert run["data"]["ledger"][0]["charged_tokens"] > 0
    assert run["data"]["summary"]["unknown_usage_calls"] == 1
    assert client.get("/api/v1/cognition").json()["control"]["reserved"]["calls"] == 0


def test_paired_rescues_regressions_and_unknown_usage():
    from alive.experiment.metrics import summarize

    def arm(correct, invoked):
        return {
            "invoked": invoked,
            "allocated_tokens": 200,
            "path_latency_ms": 3,
            "end_to_end_latency_ms": 4,
            "estimated_usd": None,
            "score": {
                "correct": correct,
                "correct_abstention": False,
                "abstained": False,
                "expected_status": "ANSWER",
                "unsupported_acceptance": not correct,
                "citation_validity": 1,
            },
        }

    rows = [
        {
            "task_id": "rescue",
            "family": "a",
            "category": "adversarial",
            "initial_score": {"correct": False},
            "arms": {
                "always": arm(True, True),
                "never": arm(False, False),
                "selective": arm(False, False),
            },
        },
        {
            "task_id": "regression",
            "family": "b",
            "category": "straightforward",
            "initial_score": {"correct": True},
            "arms": {
                "always": arm(False, True),
                "never": arm(True, False),
                "selective": arm(False, True),
            },
        },
    ]
    result = summarize(rows, [{"usage": None}])
    assert result["policies"]["always"]["critic_rescues"] == 1
    assert result["policies"]["always"]["critic_regressions"] == 1
    assert result["selection_errors"]["missed_observed_rescues"] == 1
    assert result["selection_errors"]["invoked_with_observed_regression"] == 1
    assert result["unknown_usage_calls"] == 1 and result["estimated_unique_usd"] is None
