"""Preserve simulator qualification, models and complete transition evidence."""

import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from alive.config import Settings
from alive.experiment.freeze import verify as verify_p1
from alive.learning.experiment import verify


def main():
    root = Path("archives/ALIVE-03-P2-SIM")
    if root.exists():
        raise SystemExit("Archive already exists; refusing evidence replacement")
    runtime = Path(".alive/learning")
    design = verify()
    p1 = json.loads(Path("benchmarks/alive03-p1/freeze-final.json").read_text())
    verify_p1(p1["freeze_id"])
    manifest = json.loads((runtime / "manifest.json").read_text())
    for name, expected in manifest.items():
        assert hashlib.sha256((runtime / name).read_bytes()).hexdigest() == expected
    before = json.loads((runtime / "trained-before-test.json").read_text())
    for name, expected in before["checkpoints"].items():
        assert hashlib.sha256((runtime / name).read_bytes()).hexdigest() == expected
    result = json.loads((runtime / "result.json").read_text())
    raw = json.loads((runtime / "heldout-trajectories.json").read_text())
    predictions = {}
    for policy in result["policies"]:
        rows = [row for seed in raw.values() for row in seed[policy]]
        predictions[policy] = {
            "mean_reward_prediction_mse": float(np.mean([r["reward_prediction_mse"] for r in rows]))
            if policy != "heuristic"
            else None,
            "mean_observable_state_prediction_mse": result["policies"][policy][
                "state_prediction_mse"
            ],
            "seed_mean_returns": {
                seed: float(np.mean([r["return"] for r in values[policy]]))
                for seed, values in raw.items()
            },
        }
    root.mkdir(parents=True)

    def write(name, value):
        (root / name).write_bytes(json.dumps(value, indent=2).encode() + b"\n")

    write("prediction-and-seed-analysis.json", predictions)
    artifacts = root / "artifacts"
    artifacts.mkdir()
    compressed = {}
    for p in sorted(runtime.iterdir()):
        if p.is_file():
            data = p.read_bytes()
            if len(data) > 1000000:
                destination = artifacts / (p.name + ".gz")
                destination.write_bytes(gzip.compress(data, mtime=0))
                compressed[destination.name] = {
                    "restored_name": p.name,
                    "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                    "uncompressed_bytes": len(data),
                }
            else:
                shutil.copyfile(p, artifacts / p.name)
    write("compressed-evidence.json", compressed)
    shutil.copyfile("docs/ALIVE-03-P2.md", root / "protocol.md")
    shutil.copyfile("docs/ALIVE-03-P1-CLOSURE.md", root / "p1-closure.md")
    for source, target in [
        ("p2-backend-tests.txt", "backend-tests.txt"),
        ("p2-browser-tests.txt", "browser-tests.txt"),
        ("p2-frontend-tests.txt", "frontend-tests.txt"),
        ("p2-frontend-build.txt", "frontend-build.txt"),
        ("p2-acceptance.png", "acceptance.png"),
    ]:
        shutil.copyfile(Path(".alive") / source, root / target)
    policy_table = []
    for name, metrics in result["policies"].items():
        policy_table.append(
            f"| {name} | {metrics['return']:.5f} | {metrics['cost']:.5f} | "
            f"{metrics['factual_correct'] * 100:.2f}% | "
            f"{metrics['decision_correct'] * 100:.2f}% |"
        )
    paired = result["paired_intervals"]["predictive_minus_value_only"]
    implementation = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    readme = f"""# ALIVE-03-P2 — Simulator qualification: PASS_WITH_LIMITATIONS

Actual value learning and predictive representation training work. **The predictive auxiliary
losses have not demonstrated an advantage over matched value-only learning.** This is a local,
simulation-only result, not a claim of successful MR.Q replication or live adaptive intelligence.

P1 is closed and published through `2d6a4d4`, with its original results and all frozen evidence
unchanged. P2 branch: `codex/alive-03-p2-predictive-learning`.
Implementation before training/test: `2327448`. Evidence tooling HEAD: `{implementation}`.
No P2 push, merge or changes to main. Only the pre-existing `models.txt` remains untracked.

## Experiment

- Frozen identity: `{design["freeze_id"]}`.
- Scenarios: 2,000 training, 200 development, **400 unique held-out**, four families each.
- Shared training experience: **{design["training_transition_count"]:,} completed transitions**;
  identical replay hash, initialization and minibatch ordering for each learner seed across arms.
- Five seeds, 2,500 updates each, fixed final checkpoint. No held-out selection or tuning.
- Arms: fixed heuristic, value-only, predictive (latent+reward) and reward-only ablation.
- Zero-predictive-loss equivalence is tested parameter-for-parameter against value-only.
- Wall time: {result["seconds"]:.2f}s.
- **Meta calls: 0; live browser actions: 0; paid inference: $0.**

| Policy | Mean net return | Resource cost | Factual belief accuracy | Decision correctness |
|---|---:|---:|---:|---:|
{chr(10).join(policy_table)}

Net return is the primary outcome. Costs are virtual resource units. Factual accuracy measures
the final belief against hidden truth. Decision correctness is a privileged full-information
terminal diagnostic; it is not a claim that the agent had enough evidence to know the truth.
Complete per-family results and action frequencies are in `artifacts/result.json`.

Predictive minus value-only mean return: **{paired["mean_return_difference"]:.5f}**;
hierarchical paired bootstrap 95% interval: **{paired["hierarchical_paired_bootstrap_95"]}**.
It includes zero. All four predeclared return comparisons have intervals including zero.
Do not present either learner as established superior to the fixed heuristic, or predictive
representation training as an improvement over value-only learning.

## Learning versus prediction benefit

Development mean return changes from approximately -0.2045 before training to 0.0783 for
value-only and 0.0681 for predictive at 2,500 updates. Parameters and actions change through
experience. Intermediate 1,000-update development returns were higher, but the predeclared
2,500-update checkpoint was retained; no retrospective checkpoint selection was performed.
Prediction heads generate forecasts before actions and record observed next states, rewards
and errors. The supplemental `prediction-and-seed-analysis.json` aggregates reward MSE from
the preserved trajectories; it does not alter scores, select models or rerun evaluation.

This distinguishes learning from proving the extra predictive losses useful. The latter is
unsupported here. Predictive learning also has worse next-observable-state MSE than value-only
in this run. A small latent prediction error alone would not establish useful representation
learning, because latent spaces differ and collapse is possible.

The demonstration is the first frozen held-out scenario and seed, not a favorable-case search.
Before training it invokes Critic then monitors (return -0.05390); after predictive training it
invokes Critic, retrieves, then rejects (return 0.01894). Full before/after forecasts and
observations are preserved in `artifacts/demonstration.json` and the dashboard. This one example
does not substitute for aggregate held-out results.

## Controls and limitations

The simulator deliberately assigns action-specific evidence quality. A simulated Critic can
repair a misleading prior; this does not reverse P1 or demonstrate that a real Meta Critic can.
Topic coordinates are synthetic, not browser embeddings. Four shared simulator families and
five training seeds limit external validity. Splits use different scenario seeds, not unseen
dynamics families. Goals vary across episodes, not within an episode.

Training uses completed transitions, Double-Q targets and stop-gradient target encodings.
Probes/capacity/replay are matched; next-observation probe gradients do not enter the encoder.
This is original small NumPy code inspired by predictive representation objectives described in
[Fujimoto et al.](https://arxiv.org/abs/2501.16142), not a reproduction of the full MR.Q algorithm.
The upstream noncommercial implementation and weights were not copied.

The same 400 heuristic outcomes are reused across learner seeds for pairing, not counted as
2,000 independent heuristic trials. Each learned arm has 400 rollouts per seed. Hierarchical
intervals resample learner seeds and paired scenario IDs with family balance. No live retrieval,
Meta reasoning, browser control, policy promotion or live learning was enabled. The existing
Governor retains authority over actual runtime permissions.

Runtime criticism defaults off for fresh instances and default configuration submissions;
explicit experimental opt-in still works. The owner's saved local workflow is now off. P1's
original schema, policy, evaluator and archive remain intact. Backend: **70 tests passing**,
including 10 new simulator/learning/default/API tests. Frontend tests/build and browser results
are preserved beside this report. The browser tests check actual persisted data and predictions.

## Evidence and reproduction

`artifacts/` retains every initial/trained NumPy checkpoint, checkpoint hashes captured before
test rollouts, complete training transitions, complete held-out trajectories, design, curves,
scores and demonstration. Large JSON files are losslessly gzip-compressed with deterministic
timestamps; `compressed-evidence.json` records their original byte hashes and filenames.
`artifacts/manifest.json` is the original runtime manifest for restored contents.

To inspect in the dashboard, restore the artifact files into a fresh `.alive/learning`
directory, expanding the `.json.gz` files to their recorded names, and verify every original
hash before starting the app. Restoring evidence does not train, execute a policy or invoke
Meta. Re-execution from the frozen design requires a fresh output directory and refuses silent
overwrites; checkpoint files restore inference, not optimizer continuation.

All archived data is first-party synthetic; no credentials or personal browsing data.
`manifest.json` covers every archive payload except itself. The archive commit follows this
tooling commit. Original P1 and ALIVE-02 payload checksums were reverified.
"""
    (root / "README.md").write_bytes(readme.encode())
    (root / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")
    key = Settings().alive_meta_api_key
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in {".json", ".txt", ".md"} and key:
            assert key not in p.read_text(), p
    files = {
        p.relative_to(root).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    write("manifest.json", {"freeze_id": design["freeze_id"], "files": files})
    print(f"Archived {len(files)} payloads; predictive benefit remains unproven")


if __name__ == "__main__":
    main()
