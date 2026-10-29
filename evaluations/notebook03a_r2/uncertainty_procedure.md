# ALIVE-NOTEBOOK-03A-R2 — Uncertainty Procedure (predeclared)

## Unit of analysis

The case is **not** the independent unit: 66 cases share 39 template
families, and several families are deliberate near-duplicates or
paraphrases. The family is the predeclared non-independence unit. All
uncertainty below resamples families, so correlated variants always move
together and near-duplicates cannot silently inflate the effective sample.

## Method: family-level paired bootstrap

1. Precompute per-case flags per arm (useful, retained, misleading) once.
2. Resample families with replacement (contract seed; default 1000
   resamples) to the same number of families.
3. Recompute retention (retained / useful) and misleading advances /
   scored per arm on each resample, plus paired D-vs-S and D-vs-C
   differences on the same resample (paired comparison).
4. Report percentile intervals at the contracted level plus the number of
   families and the insufficient-sample warning.

## What is reported

- Raw case counts and the number of independent source/template families.
- Per-arm point estimates (gated retention, gated misleading).
- Percentile intervals per arm and for paired differences.
- Category-level and authentic-versus-synthetic breakdowns (point
  estimates with family counts; intervals only where the stratum holds
  enough families, else an explicit warning).
- Insufficient-sample warnings: fewer families than
  `min_independent_families`, or fewer useful cases than
  `min_useful_cases`, forces `INCONCLUSIVE` under the predeclared rule —
  a 3-case improvement inside one family is never reported as meaningful.

## Why this method, and its limits

Paired family resampling is appropriate because the known dependence
structure is the family: it is conservative exactly where our corpus is
weakest (template variants). It is **not** population inference: families
are few, deliberately selected, and mutually correlated (shared project
vocabulary, same authoring process), so intervals are sensitivity bounds.
They show how much the point estimate wobbles under reweighting of
families — nothing more. No significance or generalization claim follows,
and thresholds were fixed before any model result and are never tuned to
observed outcomes.
