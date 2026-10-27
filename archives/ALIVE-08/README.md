# ALIVE-08 - Learning From Experience

Status: **PASS_NO_ADVANTAGE_DEMONSTRATED** for the primary research comparison.
Engineering qualification: **PASS**.

This is a frozen, controlled synthetic experiment. It is not native Chrome evidence, a Meta
inference run, or a claim of open-web autonomy. No paid calls were made.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Base | `origin/main` at `ef99a827aec2f335952f9370cae4f57fb5db8942` (ALIVE-07 merged) |
| Branch | `opencode/alive-08-experience-learning` |
| Policy | `alive08-contextual-experience-v1` |
| Seeds | `17, 23, 31, 43, 59` |
| Evidence kind | Controlled synthetic sequential simulator |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |

## Question

Does accumulated experience improve ALIVE's held-out decisions over appropriate baselines,
including a strong flat contextual empirical learner?

The critical control is not a stateless agent. It is the flat learner using the same observations,
costs, feedback and training stream.

## Environment

Each encounter presents a source identity, cadence hint, claim age, claim value and a fixed goal.
The agent chooses `retrieve` or `monitor` (the bounded no-action choice). The hidden environment
holds the source class, source-specific change probability, whether the claim changed and a
feedback-noise bit. The policy never receives those hidden fields.

| Action | Cost | Changed | Unchanged |
|---|---:|---:|---:|
| retrieve | 0.20 | +0.80 | -0.20 |
| monitor | 0.00 | -1.00 | 0.00 |

Source classes: stable, episodic, volatile, plus a novel class in evaluation. Each source has a
hidden offset; claim age changes the change probability. Monitor feedback is 10% noisy; retrieval
is exact. Utility is calculated by the environment, not by a model.

## Splits and calibration

| Split | Episodes | Role |
|---|---:|---|
| development | 200 | plumbing/causal checks |
| calibration | 500 | select `min_source_observations` and `source_margin` |
| training | 1,000 | fit learned arms |
| evaluation | 1,500 | held-out paired comparison |

Evaluation composition: 750 seen, 500 unseen identities from seen classes, 250 novel-class episodes.
Calibration selected `min_source_observations=2`, `source_margin=0.10`. The protocol was frozen
before held-out evaluation.

## Primary result

| Comparison | Mean utility difference | 95% cluster bootstrap CI | Episodes |
|---|---:|---|---:|
| ALIVE hierarchical - flat empirical | **-0.0248** | **[-0.0442, -0.0090]** | 1,500 |

The primary advantage criterion was not met. The flat empirical control achieved mean utility
**0.0723**; ALIVE hierarchical achieved **0.0475**.

Correct experience did beat no history and shuffled history:

| Comparison | Difference | 95% CI |
|---|---:|---|
| ALIVE vs no history | +0.3221 | [0.2576, 0.3875] |
| ALIVE vs shuffled history | +0.1419 | [0.1005, 0.1843] |
| ALIVE vs stateless prior | +0.0321 | [0.0045, 0.0595] |
| ALIVE vs fixed heuristic | +0.0683 | [0.0358, 0.1030] |
| ALIVE vs history proxy | +0.0367 | [0.0086, 0.0654] |

Per-seed ALIVE vs flat utility:

| Seed | ALIVE | Flat | Difference |
|---:|---:|---:|---:|
| 17 | 0.1400 | 0.1400 | 0.0000 |
| 23 | 0.0100 | 0.0573 | -0.0473 |
| 31 | 0.0327 | 0.0513 | -0.0186 |
| 43 | 0.0160 | 0.0867 | -0.0707 |
| 59 | 0.0387 | 0.0260 | +0.0127 |

## Arm means

| Arm | Mean utility | Success | Missed changes | Unnecessary retrievals | Retrieval rate |
|---|---:|---:|---:|---:|---:|
| stateless_prior | 0.0153 | 0.586 | 114 | 507 | 0.537 |
| fixed_heuristic | -0.0208 | 0.688 | 167 | 301 | 0.364 |
| flat_empirical | 0.0723 | 0.348 | 16 | 962 | 0.905 |
| alive_hierarchical | 0.0475 | 0.389 | 47 | 869 | 0.823 |
| alive_no_history | -0.2747 | 0.725 | 412 | 0 | 0.000 |
| alive_shuffled | -0.0944 | 0.512 | 203 | 529 | 0.492 |
| history_proxy_not_meta | 0.0108 | 0.462 | 95 | 712 | 0.686 |
| alive_online_ablation | 0.0711 | 0.390 | 25 | 890 | 0.851 |

The online ALIVE ablation approaches the flat table, but it is not the frozen primary arm.

## Source status

| Arm | Seen | Unseen | Novel |
|---|---:|---:|---:|
| flat_empirical | 0.0181 | 0.0180 | 0.3432 |
| alive_hierarchical | 0.0077 | -0.0052 | 0.2720 |
| alive_online_ablation | 0.0131 | 0.0236 | 0.3400 |

The flat control wins on all three groups; this is not a composition artifact.

## Ablations

| Ablation | Mean utility | Difference vs correct | 95% CI |
|---|---:|---:|---|
| Correct history | 0.0475 | 0.0000 | [0.0000, 0.0000] |
| No history | -0.2747 | +0.3221 | [0.2576, 0.3875] |
| Shuffled history | -0.0944 | +0.1419 | [0.1005, 0.1843] |
| Fixed heuristic | -0.0208 | +0.0683 | [0.0358, 0.1030] |

## Validity and resources

All validity checks passed:

- protocol frozen before held-out evaluation;
- selected learner parameters present;
- corpus hashes match;
- observations exclude hidden fields;
- all arms use the same scenarios;
- zero provider calls and tokens;
- all actions passed the controlled action envelope.

Provider calls: **0**; tokens: **0**; estimated provider cost: **$0.000000**.
Mean simulator decision latency: **0.108 ms**.

## Counterfactual example

`evidence/counterfactual_examples.json` records a seen stable source where ALIVE retrieves
(utility -0.20) and no-history monitors (utility 0.00). The counterfactual utilities are
simulator-defined, not real-world outcomes. This is a concrete failure case, not a success story.

## Evidence map

```
archives/ALIVE-08/
  README.md
  protocol.json
  environment.json
  seeds.json
  calibration.json
  corpus/
    development.jsonl
    calibration.jsonl
    training.jsonl
    evaluation.jsonl
  evidence/
    transitions.jsonl
    paired.json
    ablations.json
    by_status.json
    by_class.json
    per_seed.json
    counterfactual_examples.json
    restart_proof.json
    validity.json
  reports/
    results.json
    results.md
    summary.json
    cumulative-utility.svg
  validation/
  manifest.json
```

`transitions.jsonl` contains 12,000 actual arm/episode transitions with observations, actions,
independent truth, observed feedback, utility, costs, policy hashes and zero provider usage. It is
large; the paired summaries and results are the primary reading material.

`restart_proof.json` verifies a JSON policy round-trip and identical decisions on 20 scenarios. It
is simulator persistence, not a live runtime restart; ALIVE-04/05 restart tests remain the live
runtime evidence.

## Verification

| Check | Result | Transcript |
|---|---|---|
| Backend suite | 121 passed | `validation/backend.txt` |
| Experience-lab focused | 11 passed | `validation/experience-lab-focused.txt` |
| Frontend suite | 7 passed | `validation/frontend-tests.txt` |
| Production build | Passed | `validation/frontend-build.txt` |
| Ruff check and format | Passed | `validation/ruff.txt` |
| Extension JavaScript syntax | Passed | `validation/extension-js.txt` |
| Whitespace diff | Clean | `validation/whitespace.txt` |

## Limitations

- Synthetic environment; hidden class and reward weights are designed by us.
- Cadence and claim age are informative, which favours the flat contextual learner.
- No paid Meta-history baseline was run; that comparison remains pending.
- No native Chrome qualification was run; standard ports were occupied by the primary worktree.
- Five seeds and 1,500 held-out episodes are useful but not a broad benchmark.
- The ALIVE arm is a small adapter around the existing empirical policy, not the full live
  Living/WebCompanion runtime.
- Source-specific estimates overfit despite the confidence margin; the flat learner is stronger.

## Conclusion

The engineering milestone passes. The primary research claim does **not**: ALIVE's source-specific
experience policy is worse than a flat contextual empirical learner on this frozen corpus. Correct
experience still beats no history and shuffled history, so the next problem is variance control and
source-level overfitting, not the absence of memory.
