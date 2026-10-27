import copy

import numpy as np
import pytest

from alive.learning.controller import Controller, arrays
from alive.learning.environment import ACTIONS, FEATURES, EvidenceWorld, collect, scenarios


def test_simulator_splits_reproducible_and_action_dependent():
    train, test = scenarios("train", 40), scenarios("test", 40)
    assert not {s.id for s in train} & {s.id for s in test}
    assert collect(train) == collect(train)
    a, b = EvidenceWorld(train[0]), EvidenceWorld(train[0])
    assert len(a.observation()) == len(FEATURES)
    ta, tb = a.step(0), b.step(5)
    assert ta["next_state"] != tb["next_state"] and ta["reward"] != tb["reward"]
    assert not ta["done"] and tb["done"]
    assert not {"truth", "family", "expected", "oracle"} & set(ta)


def test_simulator_governor_and_terminal_no_replay():
    w = EvidenceWorld(scenarios("train", 4)[0])
    w.step(0)
    with pytest.raises(ValueError, match="Governor"):
        w.step(0)
    w.budget = 0.001
    assert list(np.flatnonzero(w.valid_actions())) == [5]
    w.step(5)
    assert w.outcome(5)["monitor"]
    with pytest.raises(ValueError):
        w.step(5)
    with pytest.raises(ValueError):
        EvidenceWorld(scenarios("train", 4)[0]).step(-1)


def test_training_rejects_heldout_transitions_and_preserves_action_masks():
    with pytest.raises(ValueError, match="training-split"):
        arrays(collect(scenarios("test", 4)))
    model = Controller()
    state = EvidenceWorld(scenarios("train", 4)[0]).observation()
    mask = np.array([False] * 5 + [True])
    assert ACTIONS[model.choose(state, mask)] == "monitor"


def test_predictive_gradients_and_zero_loss_ablation():
    data = arrays(collect(scenarios("train", 40)))
    data = tuple(v[:32] for v in data)
    baseline, zero = Controller(11), Controller(11, 0, 0)
    predictive = Controller(11, 0.2, 0.2)
    for _ in range(10):
        baseline.update(data)
        zero.update(data)
        predictive.update(data)
    assert all(np.array_equal(baseline.p[k], zero.p[k]) for k in baseline.p)
    assert not np.allclose(baseline.p["E"], predictive.p["E"])
    assert all(np.isfinite(v).all() for v in predictive.p.values())


def test_shared_encoder_gradient_matches_finite_difference():
    model = Controller(7, 0.2, 0.2)
    data = tuple(v[:16] for v in arrays(collect(scenarios("train", 20))))
    grads, _ = model.gradients(data)
    key, index = "E", (0, 0)
    original = model.p[key][index]

    def objective():
        _, losses = model.gradients(data)
        return losses["td_huber"] + 0.1 * losses["T_mse"] + 0.1 * losses["R_mse"]

    model.p[key][index] = original + 1e-6
    plus = objective()
    model.p[key][index] = original - 1e-6
    minus = objective()
    model.p[key][index] = original
    assert grads[key][index] == pytest.approx((plus - minus) / 2e-6, abs=1e-6)


def test_actual_learning_and_checkpoint_roundtrip(tmp_path):
    transitions = [t for t in collect(scenarios("train", 100)) if t["done"]]
    data = arrays(transitions)
    model = Controller(29)
    initial = copy.deepcopy(model.p)
    initial_loss = model.gradients(data)[1]["td_huber"]
    for _ in range(100):
        model.update(data)
    assert model.gradients(data)[1]["td_huber"] < initial_loss
    assert not np.array_equal(initial["E"], model.p["E"])
    model.save(tmp_path / "model.npz")
    restored = Controller()
    restored.restore(tmp_path / "model.npz")
    assert np.array_equal(model.q(data[0]), restored.q(data[0]))


def test_runtime_default_skips_critic_but_explicit_opt_in_works(client):
    from tests.test_cognition import completed, observe, start

    assert client.get("/api/v1/cognition").json()["control"]["configuration"]["use_critic"] is False
    configured = client.post("/api/v1/cognition/configuration", json={}).json()
    assert configured["control"]["configuration"]["use_critic"] is False
    start(client)
    observe(client)
    run = completed(client)
    assert run["usage"]["calls"] == 2
    assert "critic" not in [m["sender"] for m in run["messages"]]


def test_factual_and_decision_measurements_are_separate():
    a, b = [EvidenceWorld(scenarios("train", 4)[0]) for _ in range(2)]
    for w in [a, b]:
        w.importance, w.multiplier = 0.1, 1.0
        w.truth, w.log_odds = True, 3.0
    a.step(5)
    b.step(3)
    assert a.outcome(5)["factual_correct"] and b.outcome(3)["factual_correct"]
    assert a.outcome(5)["decision_correct"] and not b.outcome(3)["decision_correct"]
    assert a.total_reward > b.total_reward


def test_rollout_prediction_precedes_observation_and_evaluation_does_not_train():
    from alive.learning.experiment import rollout

    model = Controller(11, 0.2, 0.2)
    before = {k: v.copy() for k, v in model.p.items()}
    result = rollout(scenarios("development", 4)[0], model, trace=True)
    assert result["transitions"] and model.updates == 0
    assert all(np.array_equal(before[k], model.p[k]) for k in before)
    for t in result["transitions"]:
        expected = model.predict(np.array(t["state"]), t["action"])
        assert t["prediction"] == expected
        assert t["state_prediction_mse"] == pytest.approx(
            float(np.mean((np.array(expected["next_state"]) - t["next_state"]) ** 2))
        )


def test_learning_api_read_only_and_checksum_guard(client, tmp_path, monkeypatch):
    import hashlib
    import json

    from alive.learning import api

    monkeypatch.setattr(api, "ROOT", tmp_path)
    assert client.get("/api/v1/learning").json()["available"] is False
    payload = b'{"simulation_only":true,"meta_calls":0}'
    (tmp_path / "result.json").write_bytes(payload)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"result.json": hashlib.sha256(payload).hexdigest()})
    )
    assert client.get("/api/v1/learning").json()["simulation_only"] is True
    (tmp_path / "result.json").write_bytes(payload + b" ")
    assert client.get("/api/v1/learning").status_code == 409
    assert client.post("/api/v1/learning", json={"action": "browse"}).status_code == 405
