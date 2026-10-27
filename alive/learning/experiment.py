"""Frozen, matched-experience simulator experiment; no Meta requests or live actions."""

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from alive.experiment.freeze import file_hash
from alive.learning.controller import Controller, arrays
from alive.learning.environment import (
    ACTIONS,
    FEATURES,
    EvidenceWorld,
    collect,
    heuristic,
    scenarios,
)

DESIGN = Path("benchmarks/alive03-p2/design.json")
SOURCES = [
    "alive/learning/environment.py",
    "alive/learning/controller.py",
    "alive/learning/experiment.py",
    "uv.lock",
]
ARMS = {"value_only": (0, 0), "predictive": (0.2, 0.2), "reward_only_ablation": (0, 0.2)}


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def freeze():
    if DESIGN.exists():
        raise ValueError("Design already frozen; refusing replacement")
    split = {
        name: scenarios(name, n)
        for name, n in [("train", 2000), ("development", 200), ("test", 400)]
    }
    data = collect(split["train"])
    assert not ({s.id for s in split["train"]} & {s.id for s in split["test"]})
    identity = {
        "version": "predictive-cognition-simulator-v1",
        "simulation_only": True,
        "sources": {p: file_hash(p) for p in SOURCES},
        "features": FEATURES,
        "actions": ACTIONS,
        "splits": {k: [s.id for s in v] for k, v in split.items()},
        "training_transition_count": len(data),
        "training_data_sha256": hashlib.sha256(canonical(data)).hexdigest(),
        "training_seeds": [11, 29, 47, 71, 97],
        "updates": 2500,
        "batch_size": 64,
        "checkpoints": [0, 250, 1000, 2500],
        "arms": ARMS,
        "learning_rate": 0.002,
        "discount": 0.95,
        "target_update": 100,
        "hidden_units": 32,
        "selection": "Fixed final checkpoint, no hyperparameter tuning or test-based selection",
        "primary_metric": "paired realized net episodic return",
        "prediction_metrics": "next-observation MSE and reward MSE on completed transitions",
        "decision_reference": "Full-information terminal oracle, not available to the policy",
        "inference_cost": "Synthetic resource units only; no Meta calls or live browsing",
        "research": "MR.Q-inspired predictive encoder gradients, not an MR.Q reproduction",
        "reference": "https://arxiv.org/abs/2501.16142",
        "baseline": "Fixed heuristic implementation hashed before any held-out policy outcome",
    }
    identity["freeze_id"] = hashlib.sha256(canonical(identity)).hexdigest()
    DESIGN.parent.mkdir(parents=True, exist_ok=True)
    DESIGN.write_bytes(json.dumps(identity, indent=2).encode() + b"\n")
    return identity


def verify():
    design = json.loads(DESIGN.read_text())
    identity = {k: v for k, v in design.items() if k != "freeze_id"}
    assert hashlib.sha256(canonical(identity)).hexdigest() == design["freeze_id"]
    for path, expected in design["sources"].items():
        if file_hash(path) != expected:
            raise ValueError("P2 frozen source changed: " + path)
    return design


def rollout(scenario, model=None, trace=False):
    world = EvidenceWorld(scenario)
    steps = []
    while not world.done:
        state, mask = world.observation(), world.valid_actions()
        action = heuristic(state, mask) if model is None else model.choose(state, mask)
        prediction = model.predict(state, action) if model else None  # Before observed outcome.
        transition = world.step(action)
        if prediction:
            transition["prediction"] = prediction
            transition["state_prediction_mse"] = float(
                np.mean((np.asarray(prediction["next_state"]) - transition["next_state"]) ** 2)
            )
            transition["reward_prediction_squared_error"] = (
                prediction["reward"] - transition["reward"]
            ) ** 2
        steps.append(transition)
    outcome = world.outcome(action) | {
        "scenario_id": scenario.id,
        "family": scenario.family,
        "steps": len(steps),
        "action_counts": {a: sum(t["action"] == i for t in steps) for i, a in enumerate(ACTIONS)},
        "state_prediction_mse": float(np.mean([t["state_prediction_mse"] for t in steps]))
        if model
        else None,
        "reward_prediction_mse": float(
            np.mean([t["reward_prediction_squared_error"] for t in steps])
        )
        if model
        else None,
    }
    if trace:
        outcome["transitions"] = steps
    return outcome


def aggregate(rows):
    return {
        "episodes": len(rows),
        **{
            key: float(np.mean([r[key] for r in rows]))
            for key in ["return", "cost", "factual_correct", "decision_correct", "monitor", "steps"]
        },
        "actions": {a: sum(r["action_counts"][a] for r in rows) for a in ACTIONS},
        "state_prediction_mse": float(
            np.mean(
                [r["state_prediction_mse"] for r in rows if r["state_prediction_mse"] is not None]
            )
        )
        if any(r["state_prediction_mse"] is not None for r in rows)
        else None,
        "by_family": {
            family: {
                "n": sum(r["family"] == family for r in rows),
                "return": float(np.mean([r["return"] for r in rows if r["family"] == family])),
            }
            for family in sorted({r["family"] for r in rows})
        },
    }


def paired_intervals(results, seeds):
    rng = np.random.default_rng(32027)
    comparisons = [
        ("value_only", "heuristic"),
        ("predictive", "heuristic"),
        ("predictive", "value_only"),
        ("predictive", "reward_only_ablation"),
    ]
    intervals = {}
    for a, b in comparisons:
        differences = np.array(
            [
                [
                    x["return"] - y["return"]
                    for x, y in zip(results[str(seed)][a], results[str(seed)][b], strict=True)
                ]
                for seed in seeds
            ]
        )
        samples = []
        # Same environment sample for every learner seed; preserve four-family balance.
        for _ in range(2000):
            seed_index = rng.integers(0, len(seeds), len(seeds))
            scenario_index = np.concatenate(
                [
                    rng.choice(np.arange(i, differences.shape[1], 4), differences.shape[1] // 4)
                    for i in range(4)
                ]
            )
            samples.append(float(differences[np.ix_(seed_index, scenario_index)].mean()))
        intervals[a + "_minus_" + b] = {
            "mean_return_difference": float(differences.mean()),
            "hierarchical_paired_bootstrap_95": np.quantile(samples, [0.025, 0.975]).tolist(),
            "training_seeds": len(seeds),
            "unique_evaluation_scenarios": differences.shape[1],
        }
    return intervals


def run(output=Path(".alive/learning")):
    design = verify()
    if output.exists():
        raise ValueError(
            "Learning output exists; refusing to overwrite or silently rerun held-out test"
        )
    output.mkdir(parents=True)
    data = collect(scenarios("train", 2000))
    assert hashlib.sha256(canonical(data)).hexdigest() == design["training_data_sha256"]
    (output / "training-transitions.json").write_bytes(canonical(data))
    (output / "design.json").write_bytes(DESIGN.read_bytes())
    batch_data = arrays(data)
    development = scenarios("development", 200)
    curves, results, training = [], {}, []
    started = time.monotonic()
    # All training completes before the first test rollout. Same replay order per learner seed.
    models = {}
    for seed in design["training_seeds"]:
        for arm, (latent_weight, reward_weight) in ARMS.items():
            model = Controller(seed, latent_weight, reward_weight)
            rng = np.random.default_rng(seed + 1000)
            elapsed = time.monotonic()
            initial = {k: v.copy() for k, v in model.p.items()}
            model.save(output / f"initial-{seed}-{arm}.npz")
            for update in range(design["updates"] + 1):
                if update in design["checkpoints"]:
                    score = aggregate([rollout(s, model) for s in development])
                    curves.append({"seed": seed, "policy": arm, "updates": update, **score})
                if update == design["updates"]:
                    break
                indices = rng.integers(0, len(data), design["batch_size"])
                loss = model.update(tuple(v[indices] for v in batch_data))
            model.save(output / f"trained-{seed}-{arm}.npz")
            models[seed, arm] = model
            training.append(
                {
                    "seed": seed,
                    "policy": arm,
                    "updates": model.updates,
                    "replay_sha256": design["training_data_sha256"],
                    "seconds": time.monotonic() - elapsed,
                    "last_minibatch_losses": loss,
                    "encoder_change_l2": float(np.linalg.norm(model.p["E"] - initial["E"])),
                }
            )
            print(f"Trained {seed} {arm} on {len(data)} shared transitions", flush=True)
    # Hash checkpoints before unsealing any held-out interaction results.
    weights = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.npz")}
    (output / "trained-before-test.json").write_bytes(
        canonical({"checkpoints": weights, "training": training})
    )
    verify()
    test = scenarios("test", 400)
    fixed = [rollout(s, trace=True) for s in test]
    for seed in design["training_seeds"]:
        results[str(seed)] = {"heuristic": fixed}
        for arm in ARMS:
            results[str(seed)][arm] = [rollout(s, models[seed, arm], trace=True) for s in test]
    policies = {}
    for arm in ["heuristic", *ARMS]:
        combined = [r for seed in design["training_seeds"] for r in results[str(seed)][arm]]
        policies[arm] = aggregate(combined) | {
            "unique_scenarios": 400,
            "training_seeds": len(design["training_seeds"]),
        }
    result = {
        "freeze_id": design["freeze_id"],
        "simulation_only": True,
        "meta_calls": 0,
        "live_actions": 0,
        "estimated_inference_usd": 0,
        "policies": policies,
        "training": training,
        "learning_curves": curves,
        "paired_intervals": paired_intervals(results, design["training_seeds"]),
        "seconds": time.monotonic() - started,
        "limitation": "Synthetic dynamics, five learner seeds and shared scenario families; "
        "not evidence of live Meta/browser or general MR.Q performance. Fixed heuristic repeats "
        "are not independent trials; hierarchical intervals preserve paired scenario identity.",
    }
    (output / "heldout-trajectories.json").write_bytes(canonical(results))
    # Predetermined demonstration, never selected for the most favorable outcome.
    demonstration = {
        "scenario_id": test[0].id,
        "selection": "first frozen held-out scenario",
        "before": rollout(test[0], Controller(design["training_seeds"][0]), trace=True),
        "after": results[str(design["training_seeds"][0])]["predictive"][0],
    }
    (output / "demonstration.json").write_bytes(canonical(demonstration))
    (output / "result.json").write_bytes(json.dumps(result, indent=2).encode() + b"\n")
    manifest = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.iterdir())
        if p.is_file()
    }
    (output / "manifest.json").write_bytes(canonical(manifest))
    return result
