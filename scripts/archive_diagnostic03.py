"""Archive the single P3 diagnostic and its full matched prediction/control evidence."""

import gzip
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from alive.config import Settings
from alive.experiment.freeze import verify as verify_p1
from alive.learning.experiment import verify as verify_p2
from alive.learning.history_diagnostic import OUTPUT, verify


def main():
    root = Path("archives/ALIVE-03-P3")
    if root.exists():
        raise SystemExit("Archive exists; refusing replacement")
    design = verify()
    verify_p2()
    p1 = json.loads(Path("benchmarks/alive03-p1/freeze-final.json").read_text())
    verify_p1(p1["freeze_id"])
    prior = {}
    for name in ["ALIVE-02", "ALIVE-03-P1", "ALIVE-03-P1-FULL", "ALIVE-03-P2-SIM"]:
        archive = Path("archives") / name
        manifest = json.loads((archive / "manifest.json").read_text())
        for path, expected in manifest["files"].items():
            data = (archive / path).read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected["sha256"]
            assert len(data) == expected["bytes"]
        prior[name] = {"payloads": len(manifest["files"]), "unchanged": True}
    manifest = json.loads((OUTPUT / "manifest.json").read_text())
    for name, expected in manifest.items():
        assert hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest() == expected
    trained = json.loads((OUTPUT / "trained-before-test.json").read_text())
    for name, expected in trained["weights"].items():
        assert hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest() == expected
    result = json.loads((OUTPUT / "result.json").read_text())
    root.mkdir(parents=True)
    artifacts = root / "artifacts"
    artifacts.mkdir()
    compressed = {}
    for p in sorted(OUTPUT.iterdir()):
        if p.is_file():
            data = p.read_bytes()
            if p.suffix == ".json" and len(data) > 1000000:
                (artifacts / (p.name + ".gz")).write_bytes(gzip.compress(data, mtime=0))
                compressed[p.name + ".gz"] = {
                    "original_name": p.name,
                    "bytes": len(data),
                    "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                }
            else:
                shutil.copyfile(p, artifacts / p.name)

    def write(name, value):
        (root / name).write_bytes(json.dumps(value, indent=2).encode() + b"\n")

    write("prior-evidence-integrity.json", prior)
    write("compressed-evidence.json", compressed)
    shutil.copyfile("docs/ALIVE-03-P3.md", root / "protocol.md")
    shutil.copyfile("docs/LIVE-DEMONSTRATION-NEXT.md", root / "live-product-handoff.md")
    shutil.copyfile(".alive/p3-backend-tests.txt", root / "backend-tests.txt")
    returns, predictions = [], []
    for row in result["summaries"]:
        label = "history" if row["history"] else "current only"
        returns.append(
            f"| {label} | {row['training_transitions']:,} | {row['policy']} | "
            f"{row['mean_return']:.5f} | {row['retrieve_stable']:.3f} | "
            f"{row['retrieve_fresh']:.3f} |"
        )
        predictions.append(
            f"| {label} | {row['training_transitions']:,} | {row['policy']} | "
            f"{row['prediction']['first_step_belief_mse']:.5f} | "
            f"{row['empirical_baseline_prediction']['first_step_belief_mse']:.5f} |"
        )
    comparison = result["contrasts"]["history=True,pairs=512,predictive_minus_value"]
    history_gain = result["contrasts"]["pairs=512,value_only,history_minus_current"]
    values = result["action_contrasts"]
    changed = sum(v["fresh"] and v["realized_retrieve_minus_monitor"] > 0 for v in values)
    source = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    report = f"""# ALIVE-03-P3 — Focused diagnostic: PASS_WITH_LIMITATIONS

**History information helps both learners in this controlled environment. Predictive
regularization still has no demonstrated policy or sample-efficiency advantage. A simple
conditional-mean predictor has lower held-out belief error than either neural probe.**

This is the one planned diagnostic, not another learner-optimization milestone. No additional
training, tuning or architectural expansion followed the held-out outcomes. P2 remains accepted
as a simulator qualification and preserved independently at `f257cbc`; it is not an MR.Q success.

Branch: `codex/alive-03-p3-prediction-diagnostic`. Frozen implementation before evaluation:
`d6b70bf`. Evidence tooling commit: `{source}`. All work is local; no P2/P3 push or merge,
no changes to main. Only pre-existing `models.txt` remains untracked after evidence commits.

## Five diagnostic answers

### 1. State quality

All **{result["current_state_alias_pairs"]}/{result["heldout_pairs"]} held-out history pairs**
have exactly identical current observations. A deterministic current-only policy cannot choose
different first actions between paired worlds. The supplied previous-event summary changes
only feature 12; rewards, actions and the rest of the experience remain matched.

At the largest predeclared replay size, history improves value-only mean return by
**{history_gain["mean"]:.5f}**, with paired bootstrap interval
**{history_gain["paired_seed_and_history_bootstrap_95"]}**. The analogous history benefit also
appears for predictive learning. At the smallest replay size the history intervals include zero.
This diagnoses information sufficiency in P3, not the cause of P2's negative result. P3 is a new,
deliberately aliased environment; the experiment does not show that P2 lacked the same feature.

### 2. Action consequences

Retrieving consumes a visible cost in [0.1, 0.5) and reveals truth; monitoring does not collect
evidence. With a fixed follow-belief continuation, retrieval wastes resources in every stable
world and improves realized outcomes in {changed}/128 replaced-source worlds. Remaining fresh
worlds happen not to have changed truth. These are controlled cloned interventions, not
independent live observations.

Accounting for an optimal no-retrieval decision, expected retrieval value is **-cost** for stable
history and **0.5-cost** for fresh history. The agent can reverse a stale claim based on the
known 0.75 change probability; ignoring that possibility would overstate value of information.
Both the realized fixed-continuation contrast and generative expectation are recorded.

### 3. Prediction quality

All predictors see identical balanced held-out transition probes, avoiding policy-induced
distribution differences. The table shows MSE for the consequential belief coordinate at the
first step, not an average dominated by easy unchanged fields. Lower is better.

| View | Training transitions | Learner probe | First-step belief MSE | Simple empirical MSE |
|---|---:|---|---:|---:|
{chr(10).join(predictions)}

The simple baseline is fit only on training outcomes. It uses conditional means for belief
changes and terminal rewards and copies known unchanged fields/phase/resource updates. This
structured inductive bias is explicit; it does not read hidden truth. Both neural probes fail
to match its observed belief MSE at every tested budget/view. No general statistical claim
about prediction superiority is made from these point estimates alone.

The neural observation probe is detached from encoder training. Predictive encoder gradients
optimize latent/reward objectives, not this observation probe directly. The probe tests whether
the representation supports an observable forecast. This result alone does not identify which
loss, architecture or optimization choice limits it. Better latent fit would not itself prove
better decisions.

### 4. Decision quality

Retrieval frequencies show whether policies distinguish useful from wasteful actions.

| View | Training transitions | Policy | Mean return | Retrieve stable | Retrieve fresh |
|---|---:|---|---:|---:|---:|
{chr(10).join(returns)}

At the largest history-aware budget, predictive minus value-only return is
**{comparison["mean"]:.5f}**, interval
**{comparison["paired_seed_and_history_bootstrap_95"]}**. Every predictive-minus-value interval
includes zero. A zero interval in the largest current-only cell describes identical observed
behavior, not general equivalence. Prediction regularization has not shown extra decision value.

The fixed visible-history rule returns **{result["fixed_policy_return"]["True"]:.5f}**; its
current-only version (always retrieve) returns **{result["fixed_policy_return"]["False"]:.5f}**.
The learned history-aware policies approach that simple rule. The state improvement benefits
value-only learning too, so this is not evidence that explicit prediction is necessary.
Value-only still learns expected future return through bootstrapping; the name means no
explicit predictive encoder objective, not an inability to anticipate action consequences.
Because a reliable forecast improvement was not established here, the experiment cannot
demonstrate an improved-prediction → improved-decision chain. It also does not compare
planning with forecasts against direct Q-based action selection.

### 5. Sample efficiency

Replay sizes are nested: 384, 1,536 and 6,144 unique completed transitions. Every arm uses the
same 1,500 optimizer updates and batch size 64, so smaller datasets are reused more often.
All three sizes are reported; no favorable checkpoint or budget was selected. The predictive
learner has no demonstrated sample-efficiency advantage over value-only at these sizes.

## Controls, limits and interpretation

- Frozen identity: `{design["freeze_id"]}`. Same unchanged P2 Controller, encoder size,
  learning rate, discount and target updates. Only supplied state information and the existing
  predictive-gradient weights vary between comparison arms.
- Five learner seeds, 128 paired histories / 256 distinct held-out worlds, 60 small networks.
  Whole history pairs and learner seeds are resampled together in 2,000 bootstrap draws.
- The twelve predeclared return intervals are exploratory and unadjusted for multiple
  comparisons. They condition on this synthetic two-step environment and compressed history cue.
- History is an engineered summary, not learned temporal memory. Embeddings are synthetic,
  not real browser embeddings. No live-history extractor or deployed memory system is proven.
- The predictive arm changes both latent and reward gradients together; it cannot isolate the
  two contributions. P2's reward-only ablation remains preserved.
- Empirical prediction is strong here because the designed state admits a small conditional
  table. This does not establish that it scales to open-world browsing.
- Net return includes costs and errors; it does not assert broad factual competence or safety.
- **Meta calls: 0. Paid inference: $0. Live learner-controlled browser actions: 0.**

The supported next priority is a visible, history-aware feedback loop with a simple prediction
baseline and Governor-controlled actions, not another attempt to optimize the auxiliary learner.
See `live-product-handoff.md` for the concrete observe → predict → choose → act → learn demo.
No live product implementation or further learner run is smuggled into this diagnostic.

## Preservation and evidence

P2's complete mean returns were heuristic 0.033623, value-only 0.083224, predictive 0.065783,
reward-only 0.072382. Those original results, the model files and all P1/P2 freezes are unchanged.
Prior archive payload checksums were reverified. Backend tests: **76 passing** (70 prior + six
diagnostic tests). No runtime UI, provider permissions or autonomous execution path was changed.

`artifacts/` preserves all 60 checkpoints, hashes captured before held-out evaluation, complete
training experience, matched held-out probes, every saved observable/reward forecast, policy
trajectories, fixed-policy trajectories, design, all metrics and paired intervals. Large JSON
files are losslessly gzip-compressed; `compressed-evidence.json` records original names/hashes.
`artifacts/manifest.json` verifies the original uncompressed runtime contents. All model loads
use NumPy arrays without pickle. Credentials and personal browsing data are excluded.

`manifest.json` covers every archive payload except itself. The evidence commit follows this
tooling commit. The original experiment refuses silent reruns or replacement of its design.
"""
    (root / "README.md").write_bytes(report.encode())
    (root / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")
    secret = Settings().alive_meta_api_key
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in {".json", ".md", ".txt"} and secret:
            assert secret not in p.read_text()
    payloads = {
        p.relative_to(root).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    write("manifest.json", {"freeze_id": design["freeze_id"], "files": payloads})
    print(f"Archived {len(payloads)} payloads; no further optimization or paid calls")


if __name__ == "__main__":
    main()
