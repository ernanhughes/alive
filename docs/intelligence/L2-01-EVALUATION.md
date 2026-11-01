# L2-01 — Evaluation

## What this can and cannot show

Every model answer here is **scripted**. The labels (which recipe a careful owner would accept, or
that no recommendation is appropriate) were written first, in `tests/intent_benchmark.py`, and are
independent of any model output. But the scripted "faithful" answers were written by the same
author as the labels, so its perfect score is **by construction**. It shows that the pipeline can
carry a correct interpretation through to a correct, governed recommendation. It shows nothing about
how well a real model interprets goals. No live model has been run, so no claim of improved
interpretation is made.

## Three strategies, nine tasks

A: one fixed recipe whatever is asked. B: the existing deterministic selector (needs an explicit
intent kind). C: hybrid (scripted interpretation, then the same eligibility).

| Outcome (of 9) | A fixed | B deterministic | C hybrid, faithful script |
| --- | --- | --- | --- |
| correct recommendation | 2 | 3 | 6 |
| correct abstention | 0 | 3 | 3 |
| missed (abstained, should have recommended) | 0 | 2 | 0 |
| unsupported (recommended something unsuitable) | 7 | 1 | 0 |

Why the baselines fail, measured not asserted: B cannot choose when the owner gave no explicit
intent (release readiness, safe to deploy) and cannot tell "list the files" from "review the files"
(it picked the higher-scoring model procedure). A recommends the inspection recipe for everything.
Task families: straightforward (2), complex objective (2), ambiguous (2), unavailable (2: no claims
procedure; provider down), adversarial (1: hostile file names). Eligibility is shown to be
authoritative: with the provider unavailable the hybrid does not recommend the model procedure and
reports `deployment_policy_conflict` with the reason.

## Negative controls (a fake "intelligence" must not qualify)

| Scripted model | Result on the same labels |
| --- | --- |
| recommends the analysis workflow whatever is asked | 4 correct, 1 missed, **4 unsupported**: eligibility cannot catch a relevance error |
| names a procedure that does not exist | 0 recommendations; every invented id reported as `unknown_recipe`, none recommended |
| quietly replaces the goal | every interpretation `rejected_interpretation`; nothing recommended |

The first row is the honest limit: deterministic eligibility guarantees that a recommendation is
executable, not that it is appropriate. Only a labelled evaluation of a real model can show whether
relevance is good.

## Ablation: what each context condition costs

Exact request sizes (bytes, Governor's unit, including a 1,536-token output reservation): goal
only 7,539; goal plus source names 7,608; goal plus catalogue 10,334; full 10,403. All fit the
default 18,000 ceiling. The fixed instructions and schema account for most of the size. **Which
condition interprets best has not been measured**: it needs a live, independently labelled study.

## What a live study needs (not done)

A pinned model and role, an authorised budget, a larger independently labelled task set, repeated
runs, and the same three strategies. Downstream usefulness (did the chosen workflow produce the
needed evidence) must be scored separately from interpretation accuracy. Self-reported confidence
is not used.
