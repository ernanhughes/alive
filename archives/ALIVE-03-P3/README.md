# ALIVE-03-P3 — Focused diagnostic: PASS_WITH_LIMITATIONS

**History information helps both learners in this controlled environment. Predictive
regularization still has no demonstrated policy or sample-efficiency advantage. A simple
conditional-mean predictor has lower held-out belief error than either neural probe.**

This is the one planned diagnostic, not another learner-optimization milestone. No additional
training, tuning or architectural expansion followed the held-out outcomes. P2 remains accepted
as a simulator qualification and preserved independently at `f257cbc`; it is not an MR.Q success.

Branch: `codex/alive-03-p3-prediction-diagnostic`. Frozen implementation before evaluation:
`d6b70bf`. Evidence tooling commit: `e6a9ced6415ca18f4cabd9804ed548010c2f55b7`. All work is local; no P2/P3 push or merge,
no changes to main. Only pre-existing `models.txt` remains untracked after evidence commits.

## Five diagnostic answers

### 1. State quality

All **128/128 held-out history pairs**
have exactly identical current observations. A deterministic current-only policy cannot choose
different first actions between paired worlds. The supplied previous-event summary changes
only feature 12; rewards, actions and the rest of the experience remain matched.

At the largest predeclared replay size, history improves value-only mean return by
**0.14515**, with paired bootstrap interval
**[0.13272973416964565, 0.15642222018129898]**. The analogous history benefit also
appears for predictive learning. At the smallest replay size the history intervals include zero.
This diagnoses information sufficiency in P3, not the cause of P2's negative result. P3 is a new,
deliberately aliased environment; the experiment does not show that P2 lacked the same feature.

### 2. Action consequences

Retrieving consumes a visible cost in [0.1, 0.5) and reveals truth; monitoring does not collect
evidence. With a fixed follow-belief continuation, retrieval wastes resources in every stable
world and improves realized outcomes in 97/128 replaced-source worlds. Remaining fresh
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
| current only | 384 | value_only | 0.11139 | 0.07670 |
| current only | 384 | predictive | 0.11138 | 0.07670 |
| current only | 1,536 | value_only | 0.10800 | 0.07623 |
| current only | 1,536 | predictive | 0.10924 | 0.07623 |
| current only | 6,144 | value_only | 0.10212 | 0.07540 |
| current only | 6,144 | predictive | 0.10242 | 0.07540 |
| history | 384 | value_only | 0.09468 | 0.03216 |
| history | 384 | predictive | 0.09425 | 0.03216 |
| history | 1,536 | value_only | 0.09190 | 0.03120 |
| history | 1,536 | predictive | 0.09066 | 0.03120 |
| history | 6,144 | value_only | 0.08711 | 0.02955 |
| history | 6,144 | predictive | 0.08713 | 0.02955 |

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
| current only | 384 | value_only | 0.69878 | 0.980 | 0.980 |
| current only | 384 | predictive | 0.69741 | 0.983 | 0.983 |
| current only | 1,536 | value_only | 0.70393 | 0.992 | 0.992 |
| current only | 1,536 | predictive | 0.70397 | 0.992 | 0.992 |
| current only | 6,144 | value_only | 0.70814 | 1.000 | 1.000 |
| current only | 6,144 | predictive | 0.70814 | 1.000 | 1.000 |
| history | 384 | value_only | 0.74387 | 0.027 | 0.514 |
| history | 384 | predictive | 0.72553 | 0.013 | 0.433 |
| history | 1,536 | value_only | 0.82746 | 0.008 | 0.770 |
| history | 1,536 | predictive | 0.82487 | 0.006 | 0.764 |
| history | 6,144 | value_only | 0.85330 | 0.014 | 0.986 |
| history | 6,144 | predictive | 0.85064 | 0.005 | 0.980 |

At the largest history-aware budget, predictive minus value-only return is
**-0.00265**, interval
**[-0.011374837283728994, 0.0014887575212796226]**. Every predictive-minus-value interval
includes zero. A zero interval in the largest current-only cell describes identical observed
behavior, not general equivalence. Prediction regularization has not shown extra decision value.

The fixed visible-history rule returns **0.85407**; its
current-only version (always retrieve) returns **0.70814**.
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

- Frozen identity: `9a541523b28e5688006aa79c5d2993c6104b78628f92421beefaba85b6368101`. Same unchanged P2 Controller, encoder size,
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
