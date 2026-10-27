# ALIVE-08 - Learning From Experience

Status: **PASS_NO_ADVANTAGE_DEMONSTRATED** for the primary research comparison.
Engineering qualification: **PASS**.

The experiment is a controlled, synthetic sequential-decision study. It is not native Chrome
evidence, a Meta inference run, or a demonstration of open-web autonomy.

## Research question

Does accumulated experience improve ALIVE's decisions on previously unseen but related
situations, compared with appropriate baselines that do not use the same experience?

The critical comparison is not only ALIVE versus a stateless policy. It is ALIVE versus a simple
flat empirical learner using the same observations, costs, feedback and training stream. A system
that merely beats a stateless baseline while matching a trivial contextual table has not shown
useful adaptive advantage.

## Hypotheses

- **H1:** Source-specific experience improves held-out utility over a flat cadence/age contextual
  table.
- **H2:** Correct history improves utility over no history.
- **H3:** Correct history improves utility over shuffled history.
- **H4:** Simple empirical learning is comparable to fixed heuristics only when the hidden
  structure is not learnable.

## Environment

A research assistant monitors sources whose reported measurement may have changed since the last
encounter. It chooses one action per encounter:

| Action | Cost | Changed | Unchanged |
|---|---:|---:|---:|
| `retrieve` | 0.20 | +0.80 utility | -0.20 utility |
| `monitor` | 0.00 | -1.00 utility | 0.00 utility |

`monitor` is the bounded no-action choice. The environment, not a model, calculates the utility.

Each observation contains only:

- `source_id` (random UUID-derived identity; class is not encoded in it);
- `cadence` (hourly/daily/weekly/static);
- `claim_age` (recent/day/week/stale);
- a random `claim` value and the fixed monitoring goal;
- the permitted action list.

Hidden state contains the source class, per-source change probability, whether the source changed,
and the feedback-noise bit. These fields are never passed to the policy. The runner strips them
through `observation()`; tests verify the boundary.

### Hidden source structure

| Class | Base change probability | Cadence bias |
|---|---:|---|
| stable | 0.04 | static/weekly |
| episodic | 0.22 | daily/weekly |
| volatile | 0.45 | hourly/daily |
| novel (evaluation only) | 0.65 | daily/weekly/hourly |

Each source has a hidden offset (`N(0, 0.08)`) so source identities within a class differ. Claim
age multiplies the change probability by `0.5 / 0.8 / 1.2 / 1.8`. This creates recurring class
structure, source-specific variation, misleading cadence overlap and a novel class absent from
training.

Feedback noise is 10% for `monitor`; `retrieve` reveals the current measurement exactly. Learning
uses the observed feedback; scoring uses the hidden truth.

## Baselines and conditions

| Arm | Description |
|---|---|
| `stateless_prior` | Fixed cadence prior: retrieve for hourly/daily, monitor otherwise; no history |
| `fixed_heuristic` | Frozen age+cadence rule; no learning |
| `flat_empirical` | Empirical outcome means by cadence/age; critical simple contextual control |
| `alive_hierarchical` | ALIVE empirical policy with source-specific means and class/global backoff |
| `alive_no_history` | Same ALIVE policy with no training experiences |
| `alive_shuffled` | Same number of updates, but training rewards shuffled across transitions |
| `history_proxy_not_meta` | Offline retrieval baseline using the last eight matching transitions |
| `alive_online_ablation` | ALIVE updated online during evaluation; secondary, not primary |

A paid Meta-history model baseline was **not run**. No paid inference was authorised. The history
proxy is explicitly not a Meta baseline; the actual model comparison remains pending.

## Learning mechanism

The ALIVE arm reuses `alive.living_policy.choose/update`, the same empirical outcome-mean policy
used by the Living runtime. It maintains three context levels:

1. `source:<id>` when the source has enough observations and its best mean exceeds the class mean
   by the selected margin;
2. `class:<cadence>:<claim_age>` otherwise;
3. `global` when neither has evidence.

Completed feedback updates all three contexts. The flat control updates only class/global contexts.
This is a small adapter around the existing policy, not a new neural learner.

Calibration selected `min_source_observations=2` and `source_margin=0.10` from a predeclared grid.
The protocol was frozen before held-out evaluation.

## Split and seeds

| Split | Episodes | Role |
|---|---:|---|
| Development | 200 (5 seeds × 40) | plumbing and causal checks |
| Calibration | 500 (5 seeds × 100) | select the limited learner parameters |
| Training | 1,000 (5 seeds × 200) | final learned-policy training |
| Evaluation | 1,500 (5 seeds × 300) | held-out paired comparison |

Seeds: `17, 23, 31, 43, 59`.

Evaluation composition: 750 seen sources, 500 unseen identities from seen classes, and 250 novel
class episodes. Training and evaluation use separate source pools except for intentionally shared
seen-source identities.

Data-leakage controls:

- candidate code receives only `observation()`;
- hidden class/change/noise fields are excluded and unit-tested;
- labels and future outcomes are read only by the evaluator;
- all arms receive the same scenario stream and hidden outcomes;
- the protocol and corpus hashes were frozen before held-out evaluation;
- no held-out tuning was performed after results were read.

## Primary metric

`mean independent task utility per held-out episode`.

Predeclared primary comparison: `alive_hierarchical` minus `flat_empirical`.

Advantage requires a paired 95% cluster-bootstrap confidence interval with lower bound above zero
and a mean difference of at least 0.01. The bootstrap resamples source/seed clusters to respect
dependence among repeated encounters.

## Results

### Primary comparison

| Comparison | Mean difference | 95% cluster bootstrap CI | Clusters | Episodes |
|---|---:|---|---:|---:|
| ALIVE hierarchical - flat empirical | **-0.0248** | **[-0.0442, -0.0090]** | 229 | 1,500 |

The primary criterion is **not met**. The flat empirical control is better than the source-specific
ALIVE policy on held-out utility.

### Arm means

| Arm | Mean utility | Success | Missed changes | Unnecessary retrievals | Retrieval rate |
|---|---:|---:|---:|---:|---:|
| stateless_prior | 0.0153 | 0.586 | 114 | 507 | 0.537 |
| fixed_heuristic | -0.0208 | 0.688 | 167 | 301 | 0.364 |
| **flat_empirical** | **0.0723** | 0.348 | 16 | 962 | 0.905 |
| **alive_hierarchical** | **0.0475** | 0.389 | 47 | 869 | 0.823 |
| alive_no_history | -0.2747 | 0.725 | 412 | 0 | 0.000 |
| alive_shuffled | -0.0944 | 0.512 | 203 | 529 | 0.492 |
| history_proxy_not_meta | 0.0108 | 0.462 | 95 | 712 | 0.686 |
| alive_online_ablation | 0.0711 | 0.390 | 25 | 890 | 0.851 |

The online ALIVE ablation recovers most of the flat table's utility, but it is not the frozen
primary arm and still does not exceed the flat control.

### Paired secondary comparisons

| Comparison | Mean difference | 95% CI |
|---|---:|---|
| ALIVE vs flat empirical | -0.0248 | [-0.0442, -0.0090] |
| ALIVE vs stateless prior | +0.0321 | [0.0045, 0.0595] |
| ALIVE vs fixed heuristic | +0.0683 | [0.0358, 0.1030] |
| ALIVE vs no history | +0.3221 | [0.2576, 0.3875] |
| ALIVE vs shuffled history | +0.1419 | [0.1005, 0.1843] |
| ALIVE vs history proxy | +0.0367 | [0.0086, 0.0654] |

Correct experience clearly helps relative to no history and shuffled history. The strongest simple
contextual learner still wins.

### Per-seed utility

| Seed | ALIVE | Flat | Difference |
|---:|---:|---:|---:|
| 17 | 0.1400 | 0.1400 | 0.0000 |
| 23 | 0.0100 | 0.0573 | -0.0473 |
| 31 | 0.0327 | 0.0513 | -0.0186 |
| 43 | 0.0160 | 0.0867 | -0.0707 |
| 59 | 0.0387 | 0.0260 | +0.0127 |

ALIVE wins on one seed, ties on one, and loses on three.

### Utility by source status

| Arm | Seen | Unseen | Novel |
|---|---:|---:|---:|
| flat_empirical | 0.0181 | 0.0180 | 0.3432 |
| alive_hierarchical | 0.0077 | -0.0052 | 0.2720 |
| alive_online_ablation | 0.0131 | 0.0236 | 0.3400 |

The source-specific arm is worse on seen, unseen and novel groups. The result is not explained by
a single composition change.

### Utility by hidden class

| Arm | Stable | Episodic | Volatile | Novel |
|---|---:|---:|---:|---:|
| flat_empirical | -0.1349 | -0.0146 | 0.2014 | 0.3432 |
| alive_hierarchical | -0.1237 | -0.0520 | 0.1794 | 0.2720 |

### Ablations

| Ablation | Mean utility | Difference vs correct | 95% CI |
|---|---:|---:|---|
| Correct history | 0.0475 | 0.0000 | [0.0000, 0.0000] |
| No history | -0.2747 | +0.3221 | [0.2576, 0.3875] |
| Shuffled history | -0.0944 | +0.1419 | [0.1005, 0.1843] |
| Fixed heuristic | -0.0208 | +0.0683 | [0.0358, 0.1030] |

The experience signal is real under this protocol: correct history beats no history and shuffled
history. It does not establish that ALIVE's hierarchical source memory is the best use of that
experience.

## Failure case

The preserved counterfactual example is a seen stable source with `cadence=weekly`,
`claim_age=day`, and no actual change. The trained ALIVE policy chooses `retrieve` (utility -0.20),
while the no-history policy chooses `monitor` (utility 0.00). The environment records the actual
outcome; the counterfactual is simulator-defined and not a real-world claim.

This illustrates the observed problem: source-level estimates can overfit noisy history and
over-retrieve, while the flat cadence/age table is more robust.

## Validity checks

All checks passed:

- protocol frozen before evaluation;
- selected parameters present;
- corpus SHA-256 hashes match;
- observations exclude hidden fields;
- all arms use the same scenarios;
- zero provider calls and tokens;
- every action passed the controlled action envelope.

Resource use: provider calls **0**, tokens **0**, estimated provider cost **$0.000000**.
Mean decision latency: **0.108 ms** in the local simulator.

## Interpretation

This is a valid negative primary result, not a failed run.

- **Engineering:** the reproducible environment, baselines, paired scoring, ablations, evidence
  and safety checks are qualified.
- **Research:** the primary claim that ALIVE's source-specific experience beats a flat contextual
  learner is **not supported**. No post-hoc tuning was performed.
- **What is supported:** recorded correct experience improves decisions over no history, shuffled
  history, a fixed heuristic and a stateless prior in this environment.
- **What is not supported:** superiority over a simple flat empirical learner, generalisation to
  arbitrary browser tasks, or any live Meta/Chrome benefit.

The next technical obstacle is source-level overfitting and variance control, not the absence of
memory. The online ablation and flat table suggest that stronger shrinkage, hierarchical priors or
a larger source-history budget may be needed before claiming adaptive advantage.

## Threats to validity

- The environment is synthetic and small; source classes and reward weights are designed by us.
- Cadence and claim age are informative, so a flat table has a strong advantage.
- Feedback is noisy, but the noise model is simple and known to the evaluator.
- Only five seeds and 1,500 held-out episodes; the confidence interval is cluster-aware but not a
  substitute for broad replication.
- The ALIVE arm uses a small empirical adapter, not the full live Living/WebCompanion runtime.
- No paid Meta-history baseline was run; the model-with-history comparison remains pending.
- No native Chrome qualification was run.
- The history proxy is an offline diagnostic, not a Meta model.

## Reproduction

```powershell
uv run python -m scripts.alive08 generate
uv run python -m scripts.alive08 calibrate
uv run python -m scripts.alive08 evaluate
```

The evaluation command refuses a second held-out run after `results.json` exists.

## Verification

```powershell
uv run pytest -q
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
npm test --prefix dashboard
npm run build --prefix dashboard
node --check extension/background.js
node --check extension/panel.js
```

Results: **121 backend tests**, **11 experience-lab tests**, **7 frontend tests**, production build,
Ruff check/format, extension JavaScript syntax and whitespace checks passed. Held-out evaluation was
run once on the frozen protocol; the command refuses a second run.

## Evidence

- `archives/ALIVE-08/README.md`
- `archives/ALIVE-08/protocol.json`
- `archives/ALIVE-08/environment.json`
- `archives/ALIVE-08/seeds.json`
- `archives/ALIVE-08/corpus/`
- `archives/ALIVE-08/evidence/transitions.jsonl`
- `archives/ALIVE-08/evidence/paired.json`
- `archives/ALIVE-08/evidence/ablations.json`
- `archives/ALIVE-08/evidence/counterfactual_examples.json`
- `archives/ALIVE-08/evidence/restart_proof.json`
- `archives/ALIVE-08/reports/results.json`
- `archives/ALIVE-08/reports/results.md`
- `archives/ALIVE-08/reports/cumulative-utility.svg`
- `archives/ALIVE-08/manifest.json`

## Conclusion

ALIVE-08 did not demonstrate an advantage over the strongest simple contextual control. It did
demonstrate that independently scored prior experience changes later decisions and outperforms no
history, shuffled history, a fixed heuristic and a stateless prior on this frozen corpus.

The honest conclusion is: **experience matters here, but ALIVE's source-specific policy is not yet
the best way to use it.** That is the next engineering problem, not a reason to add a larger model.
