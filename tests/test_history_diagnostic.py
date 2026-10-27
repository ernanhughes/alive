import numpy as np
import pytest

from alive.learning.controller import Controller
from alive.learning.history_diagnostic import (
    EmpiricalPredictor,
    HistoryWorld,
    collect,
    episode,
    interval,
    prediction_metrics,
    view,
)


def test_history_aliasing_and_no_truth_in_current_state():
    for pair in range(20):
        a, b = [HistoryWorld("train", pair, fresh, False) for fresh in [False, True]]
        assert np.array_equal(a.state(), b.state())
        assert a.id != b.id
        rich_a, rich_b = [HistoryWorld("train", pair, fresh) for fresh in [False, True]]
        diff = np.flatnonzero(rich_a.state() != rich_b.state())
        assert diff.tolist() == [12]
        assert rich_a.state()[12] == -1 and rich_b.state()[12] == 1


def test_action_consequences_have_opposite_realized_value_for_a_changed_claim():
    pair = next(
        p
        for p in range(100)
        if HistoryWorld("train", p, True).truth != HistoryWorld("train", p, True).claim
    )

    def result(fresh, first):
        world = HistoryWorld("train", pair, fresh)
        world.step(first)
        world.step(3 if world.belief > 0.5 else 4)
        return world.return_value

    cost = HistoryWorld("train", pair, True).cost
    assert result(False, 0) - result(False, 5) == pytest.approx(-cost)
    assert result(True, 0) - result(True, 5) == pytest.approx(2 - cost)


def test_matched_history_ablation_and_nested_experience():
    rows = collect("train", 8)
    assert rows == collect("train", 8) and len(rows) == 96
    assert rows[:48] == collect("train", 4)
    masked = view(rows, False)
    for a, b in zip(rows, masked, strict=True):
        for field in ["action", "reward", "done", "valid_actions", "next_valid_actions"]:
            assert a[field] == b[field]
        assert b["state"][12] == b["next_state"][12] == 0
        assert a["state"][:12] == b["state"][:12]
        assert a["state"][13:] == b["state"][13:]
    assert not {r["scenario_id"] for r in rows} & {r["scenario_id"] for r in collect("test", 8)}


def test_empirical_baseline_heldout_protection_and_critical_metrics():
    rows = collect("train", 32)
    predictor = EmpiricalPredictor(rows)
    with pytest.raises(ValueError):
        EmpiricalPredictor(collect("test", 2))
    metrics, predictions = prediction_metrics(predictor, collect("train", 2))
    assert predictions["state"].shape == (24, 18)
    assert all(np.isfinite(v) and v >= 0 for v in metrics.values())
    initial = HistoryWorld("train", 1, False).state()
    assert predictor.predict(initial, 0)["reward"] == -initial[7]


def test_current_only_policy_cannot_distinguish_paired_histories():
    model = Controller(29, 0.2, 0.2)
    for pair in range(20):
        stable, fresh = [episode(model, "train", pair, flag, False) for flag in [False, True]]
        assert stable["retrieve"] == fresh["retrieve"]


def test_two_step_governor_and_preserved_pair_bootstrap():
    world = HistoryWorld("train", 0, False)
    with pytest.raises(ValueError):
        world.step(3)
    world.step(5)
    with pytest.raises(ValueError):
        world.step(0)
    world.step(3)
    with pytest.raises(ValueError):
        world.step(5)
    values = np.zeros((5, 20, 2))
    values[:, :, 0], values[:, :, 1] = -1, 1
    assert interval(values)["paired_seed_and_history_bootstrap_95"] == [0, 0]
