# ALIVE-03-P2 — Simulator qualification: PASS_WITH_LIMITATIONS

Actual value learning and predictive representation training work. **The predictive auxiliary
losses have not demonstrated an advantage over matched value-only learning.** This is a local,
simulation-only result, not a claim of successful MR.Q replication or live adaptive intelligence.

P1 is closed and published through `2d6a4d4`, with its original results and all frozen evidence
unchanged. P2 branch: `codex/alive-03-p2-predictive-learning`.
Implementation before training/test: `2327448`. Evidence tooling HEAD: `dfa07c6787071b01a7c007972810d5c466ab328a`.
No P2 push, merge or changes to main. Only the pre-existing `models.txt` remains untracked.

## Experiment

- Frozen identity: `5baaf48e31efe94f00b961c015a4e75fea6b8faf72b51a792361d30a2cd7777c`.
- Scenarios: 2,000 training, 200 development, **400 unique held-out**, four families each.
- Shared training experience: **3,124 completed transitions**;
  identical replay hash, initialization and minibatch ordering for each learner seed across arms.
- Five seeds, 2,500 updates each, fixed final checkpoint. No held-out selection or tuning.
- Arms: fixed heuristic, value-only, predictive (latent+reward) and reward-only ablation.
- Zero-predictive-loss equivalence is tested parameter-for-parameter against value-only.
- Wall time: 16.92s.
- **Meta calls: 0; live browser actions: 0; paid inference: $0.**

| Policy | Mean net return | Resource cost | Factual belief accuracy | Decision correctness |
|---|---:|---:|---:|---:|
| heuristic | 0.03362 | 0.19114 | 76.00% | 74.25% |
| value_only | 0.08322 | 0.26038 | 88.30% | 74.45% |
| predictive | 0.06578 | 0.26116 | 88.25% | 72.95% |
| reward_only_ablation | 0.07238 | 0.25993 | 89.15% | 73.20% |

Net return is the primary outcome. Costs are virtual resource units. Factual accuracy measures
the final belief against hidden truth. Decision correctness is a privileged full-information
terminal diagnostic; it is not a claim that the agent had enough evidence to know the truth.
Complete per-family results and action frequencies are in `artifacts/result.json`.

Predictive minus value-only mean return: **-0.01744**;
hierarchical paired bootstrap 95% interval: **[-0.06406345823013081, 0.017249100950501816]**.
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
