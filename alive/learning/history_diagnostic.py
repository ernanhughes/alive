"""Focused P3 history-aliasing diagnostic. P2 code and results remain unchanged."""

import hashlib
import json
from pathlib import Path

import numpy as np

from alive.experiment.freeze import file_hash
from alive.learning.controller import Controller, arrays
from alive.learning.environment import rng_for
from alive.learning.experiment import canonical

DESIGN = Path("benchmarks/alive03-p3/design.json")
OUTPUT = Path(".alive/prediction-diagnostic")
SOURCES = [
    "alive/learning/history_diagnostic.py",
    "alive/learning/controller.py",
    "alive/learning/environment.py",
    "alive/learning/experiment.py",
    "uv.lock",
]


class HistoryWorld:
    """Same visible page; history says corroborated versus a newly replaced source.

    Current features are deliberately aliased. The history flag is a previous-event
    summary, not hidden truth or a learned recurrent representation.
    """

    def __init__(self, split, pair, fresh, history=True):
        self.split, self.pair, self.fresh, self.history = split, pair, fresh, history
        self.id = hashlib.sha256(f"p3-v1|{split}|{pair}|{fresh}".encode()).hexdigest()[:24]
        rng = rng_for("p3-v1", split, pair)
        self.claim = bool(rng.integers(2))
        self.cost = float(rng.uniform(0.1, 0.5))
        self.embedding = rng.uniform(-1, 1, 4)
        self.truth = not self.claim if fresh and rng.random() < 0.75 else self.claim
        self.belief = 0.9 if self.claim else 0.1
        self.phase, self.retrieved, self.return_value = 0, False, 0.0

    def state(self):
        # Same 18-dimensional architecture; index 12 is the only history ablation.
        return np.array(
            [
                self.belief,
                0.2,
                0,
                0,
                0,
                1,
                1,
                self.cost,
                1 - self.cost * self.retrieved,
                1 - self.phase / 2,
                float(self.retrieved),
                self.phase / 2,
                (1 if self.fresh else -1) if self.history else 0,
                1,
                *self.embedding,
            ],
            dtype=float,
        )

    def mask(self):
        return np.array(
            [self.phase == 0, False, False, self.phase == 1, self.phase == 1, self.phase == 0]
        )

    def step(self, action):
        if not 0 <= action < 6 or not self.mask()[action]:
            raise ValueError("Diagnostic Governor rejected action or replay of terminal state")
        state, mask = self.state(), self.mask()
        reward = 0.0
        if self.phase == 0:
            if action == 0:
                self.retrieved = True
                self.belief = 0.9 if self.truth else 0.1
                reward = -self.cost
        else:
            reward = 1.0 if (action == 3) == self.truth else -1.0
        self.phase += 1
        self.return_value += reward
        return {
            "split": self.split,
            "scenario_id": self.id,
            "state": state.tolist(),
            "valid_actions": mask.tolist(),
            "action": action,
            "reward": reward,
            "next_state": self.state().tolist(),
            "done": self.phase == 2,
            "next_valid_actions": self.mask().tolist(),
        }


def collect(split, pairs):
    """Balanced completed counterfactual transitions, not independent live trials."""
    replay = []
    for pair in range(pairs):
        for fresh in [False, True]:
            for first in [0, 5]:
                world = HistoryWorld(split, pair, fresh)
                replay.append(world.step(first))
                for terminal in [3, 4]:
                    branch = HistoryWorld(split, pair, fresh)
                    branch.step(first)
                    replay.append(branch.step(terminal))
    return replay


def view(rows, history):
    if history:
        return rows
    result = []
    for row in rows:
        masked = row | {"state": list(row["state"]), "next_state": list(row["next_state"])}
        masked["state"][12] = masked["next_state"][12] = 0.0
        result.append(masked)
    return result


def cell(state, action):
    return (state[11], state[0] > 0.5, state[12], state[10], action)


class EmpiricalPredictor:
    """Train-only conditional means; copy unchanged fields and known phase/resource updates."""

    def __init__(self, rows):
        if any(r["split"] != "train" for r in rows):
            raise ValueError("Prediction baseline cannot fit held-out outcomes")
        groups = {}
        for row in rows:
            groups.setdefault(cell(row["state"], row["action"]), []).append(
                [row["next_state"][0], row["reward"]]
            )
        self.means = {key: np.mean(values, axis=0) for key, values in groups.items()}

    def predict(self, state, action):
        next_state = np.array(state, dtype=float)
        mean = self.means.get(cell(state, action), [state[0], 0.0])
        next_state[0] = mean[0]
        next_state[11] += 0.5
        next_state[9] -= 0.5
        if state[11] == 0 and action == 0:
            next_state[10] = 1
            next_state[8] -= state[7]
        reward = (-state[7] if action == 0 else 0) if state[11] == 0 else float(mean[1])
        return {"next_state": next_state.tolist(), "reward": reward}


def episode(model, split, pair, fresh, history):
    world = HistoryWorld(split, pair, fresh, history)
    trace = []
    while world.phase < 2:
        state, mask = world.state(), world.mask()
        if model is None:
            action = (
                (0 if state[12] >= 0 else 5) if world.phase == 0 else (3 if state[0] > 0.5 else 4)
            )
        else:
            action = model.choose(state, mask)
        trace.append(world.step(action))
    return {
        "scenario_id": world.id,
        "pair": pair,
        "fresh": fresh,
        "return": world.return_value,
        "retrieve": trace[0]["action"] == 0,
        "trace": trace,
    }


def action_contrasts(pairs):
    rows = []
    for pair in range(pairs):
        for fresh in [False, True]:
            returns = []
            for first in [0, 5]:
                world = HistoryWorld("test", pair, fresh)
                world.step(first)
                world.step(3 if world.belief > 0.5 else 4)
                returns.append(world.return_value)
            cost = HistoryWorld("test", pair, fresh).cost
            rows.append(
                {
                    "pair": pair,
                    "fresh": fresh,
                    "realized_retrieve_minus_monitor": returns[0] - returns[1],
                    "expected_gain_follow_belief_continuation": (1.5 if fresh else 0) - cost,
                    "expected_gain_over_best_no_retrieval": (0.5 if fresh else 0) - cost,
                }
            )
    return rows


def prediction_metrics(predictor, probes):
    predictions = [predictor.predict(np.asarray(r["state"]), r["action"]) for r in probes]
    predicted_state = np.array([p["next_state"] for p in predictions])
    actual_state = np.array([r["next_state"] for r in probes])
    predicted_reward = np.array([p["reward"] for p in predictions])
    actual_reward = np.array([r["reward"] for r in probes])
    error = (predicted_state - actual_state) ** 2
    first = np.array([r["state"][11] == 0 for r in probes])
    return {
        "state_mse": float(error.mean()),
        "belief_mse": float(error[:, 0].mean()),
        "first_step_belief_mse": float(error[first, 0].mean()),
        "reward_mse": float(np.mean((predicted_reward - actual_reward) ** 2)),
    }, {"state": predicted_state, "reward": predicted_reward}


def freeze():
    if DESIGN.exists():
        raise ValueError("Diagnostic already frozen")
    replay = collect("train", 512)
    identity = {
        "version": "history-diagnostic-v1",
        "sources": {p: file_hash(p) for p in SOURCES},
        "pairs_per_training_budget": [32, 128, 512],
        "test_pairs": 128,
        "test_scenario_ids": [
            HistoryWorld("test", p, fresh).id for p in range(128) for fresh in [False, True]
        ],
        "training_seeds": [11, 29, 47, 71, 97],
        "updates": 1500,
        "batch_size": 64,
        "views": ["current_only", "with_history"],
        "policies": {"value_only": [0, 0], "predictive": [0.2, 0.2]},
        "replay_sha256": hashlib.sha256(canonical(replay)).hexdigest(),
        "feature_12": (
            "Previous source-replacement event (+1) or corroboration (-1); zero if masked"
        ),
        "feature_11": "Episode phase / 2; all other slots are current-page features or resources",
        "expected_action_gain": (
            "Versus best no-retrieval decision: stable -cost; fresh 0.5-cost. "
            "Versus blindly trusting the current claim: fresh 1.5-cost. Cost lies in [0.1,0.5)."
        ),
        "primary_questions": [
            "state sufficiency",
            "causal action contrast",
            "held-out prediction versus conditional-mean baseline",
            "paired decision return",
            "data size at fixed optimization budget",
        ],
        "prediction_probes": (
            "Same balanced held-out transitions for every policy, not on-policy MSE"
        ),
        "selection": "No checkpoint or hyperparameter selection; one fixed diagnostic run",
        "scope": "Synthetic browser-like histories; no real browser embeddings or Meta calls",
    }
    identity["freeze_id"] = hashlib.sha256(canonical(identity)).hexdigest()
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    DESIGN.write_bytes(json.dumps(identity, indent=2).encode() + b"\n")
    return identity


def verify():
    design = json.loads(DESIGN.read_text())
    expected = hashlib.sha256(
        canonical({k: v for k, v in design.items() if k != "freeze_id"})
    ).hexdigest()
    if design["freeze_id"] != expected:
        raise ValueError("Diagnostic manifest identity changed")
    for path, checksum in design["sources"].items():
        if file_hash(path) != checksum:
            raise ValueError("Frozen diagnostic source changed: " + path)
    return design


def interval(differences):
    # Shape: learner seeds, paired histories, two worlds. Preserve both members.
    rng = np.random.default_rng(33027)
    samples = []
    for _ in range(2000):
        s = rng.integers(differences.shape[0], size=differences.shape[0])
        p = rng.integers(differences.shape[1], size=differences.shape[1])
        samples.append(float(differences[np.ix_(s, p)].mean()))
    return {
        "mean": float(differences.mean()),
        "paired_seed_and_history_bootstrap_95": np.quantile(samples, [0.025, 0.975]).tolist(),
    }


def run():
    design = verify()
    if OUTPUT.exists():
        raise ValueError("Output exists; no automatic held-out rerun")
    OUTPUT.mkdir(parents=True)
    replay = collect("train", 512)
    assert hashlib.sha256(canonical(replay)).hexdigest() == design["replay_sha256"]
    (OUTPUT / "training-transitions.json").write_bytes(canonical(replay))
    (OUTPUT / "design.json").write_bytes(DESIGN.read_bytes())
    models, logs = {}, []
    for history in [False, True]:
        for pairs in design["pairs_per_training_budget"]:
            rows = view(replay[: pairs * 12], history)
            data = arrays(rows)
            for seed in design["training_seeds"]:
                for policy, weights in design["policies"].items():
                    model = Controller(seed, *weights)
                    rng = np.random.default_rng(seed + 1000)
                    for _ in range(design["updates"]):
                        indices = rng.integers(0, len(rows), design["batch_size"])
                        model.update(tuple(x[indices] for x in data))
                    name = f"{int(history)}-{pairs}-{seed}-{policy}"
                    model.save(OUTPUT / (name + ".npz"))
                    models[history, pairs, seed, policy] = model
                    logs.append(
                        {
                            "model": name,
                            "transitions": len(rows),
                            "updates": model.updates,
                            "replay_view_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
                        }
                    )
    weights = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUTPUT.glob("*.npz")}
    (OUTPUT / "trained-before-test.json").write_bytes(canonical({"weights": weights, "logs": logs}))
    verify()
    probes = collect("test", design["test_pairs"])
    (OUTPUT / "heldout-probes.json").write_bytes(canonical(probes))
    summaries, scores, traces, forecasts = [], {}, {}, {}
    for history in [False, True]:
        viewed_probes = view(probes, history)
        for pairs in design["pairs_per_training_budget"]:
            baseline = EmpiricalPredictor(view(replay[: pairs * 12], history))
            baseline_metrics, baseline_predictions = prediction_metrics(baseline, viewed_probes)
            forecasts[f"{int(history)}-{pairs}-empirical-state"] = baseline_predictions["state"]
            forecasts[f"{int(history)}-{pairs}-empirical-reward"] = baseline_predictions["reward"]
            for policy in design["policies"]:
                returns, prediction_rows, retrieval = [], [], []
                for seed in design["training_seeds"]:
                    model = models[history, pairs, seed, policy]
                    metrics, predicted = prediction_metrics(model, viewed_probes)
                    name = f"{int(history)}-{pairs}-{seed}-{policy}"
                    forecasts[name + "-state"], forecasts[name + "-reward"] = (
                        predicted["state"],
                        predicted["reward"],
                    )
                    episodes = [
                        episode(model, "test", pair, fresh, history)
                        for pair in range(design["test_pairs"])
                        for fresh in [False, True]
                    ]
                    returns.append([e["return"] for e in episodes])
                    retrieval.append([e["retrieve"] for e in episodes])
                    traces[name] = episodes
                    prediction_rows.append(metrics)
                values = np.array(returns).reshape(len(design["training_seeds"]), -1, 2)
                scores[history, pairs, policy] = values
                rates = np.mean(np.array(retrieval).reshape(values.shape), axis=(0, 1))
                summaries.append(
                    {
                        "history": history,
                        "training_pairs": pairs,
                        "training_transitions": pairs * 12,
                        "policy": policy,
                        "mean_return": float(values.mean()),
                        "retrieve_stable": float(rates[0]),
                        "retrieve_fresh": float(rates[1]),
                        "prediction": {
                            k: float(np.mean([r[k] for r in prediction_rows]))
                            for k in prediction_rows[0]
                        },
                        "empirical_baseline_prediction": baseline_metrics,
                    }
                )
    contrasts = {}
    for history in [False, True]:
        for pairs in design["pairs_per_training_budget"]:
            contrasts[f"history={history},pairs={pairs},predictive_minus_value"] = interval(
                scores[history, pairs, "predictive"] - scores[history, pairs, "value_only"]
            )
    for pairs in design["pairs_per_training_budget"]:
        for policy in design["policies"]:
            contrasts[f"pairs={pairs},{policy},history_minus_current"] = interval(
                scores[True, pairs, policy] - scores[False, pairs, policy]
            )
    fixed = {
        str(h): [
            episode(None, "test", p, fresh, h)
            for p in range(design["test_pairs"])
            for fresh in [False, True]
        ]
        for h in [False, True]
    }
    # Check exact observation aliasing without inspecting/altering any learner decision.
    aliases = sum(
        np.array_equal(
            HistoryWorld("test", p, False, False).state(),
            HistoryWorld("test", p, True, False).state(),
        )
        for p in range(design["test_pairs"])
    )
    result = {
        "freeze_id": design["freeze_id"],
        "meta_calls": 0,
        "simulation_only": True,
        "current_state_alias_pairs": aliases,
        "heldout_pairs": design["test_pairs"],
        "action_contrasts": action_contrasts(design["test_pairs"]),
        "summaries": summaries,
        "contrasts": contrasts,
        "fixed_policy_return": {
            k: float(np.mean([e["return"] for e in v])) for k, v in fixed.items()
        },
        "limitation": "Hand-designed two-step simulator, compressed history flag, five seeds; "
        "not evidence of learned temporal memory, real browser or MR.Q superiority. "
        "Exploratory intervals are not corrected for multiple comparisons.",
    }
    (OUTPUT / "policy-trajectories.json").write_bytes(canonical(traces))
    (OUTPUT / "fixed-policy-trajectories.json").write_bytes(canonical(fixed))
    np.savez_compressed(OUTPUT / "matched-probe-forecasts.npz", **forecasts)
    (OUTPUT / "result.json").write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(OUTPUT.iterdir())
        if p.is_file()
    }
    (OUTPUT / "manifest.json").write_bytes(canonical(manifest))
    return result
