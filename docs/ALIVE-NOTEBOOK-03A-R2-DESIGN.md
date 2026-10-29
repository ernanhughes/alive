# ALIVE-NOTEBOOK-03A-R2 — design (protocol integrity, blind evaluation)

Base: `b9978da6bededa88ad013952d2c165f85cc8cac` (`origin/main`, PR #46 merged).
Branch: `codex/alive-notebook-03a-r2-blind-protocol`.
Authority: offline experiment infrastructure only. Zero model inference;
no paid spend; no merge authority.

v1.4 (`evaluations/notebook03a/`) and v1.5 (`evaluations/notebook03a_r1/`)
are preserved byte-unchanged as historical evidence. R2 lives in
`evaluations/notebook03a_r2/` + `scripts/notebook03a_r2*.py` under protocol
`notebook03a-v1.6`. v1.5 is a historical draft from here on, not the frozen
protocol.

## Why R2

Independent review of R1 showed three load-bearing defects:

1. `evaluate_progress` reads flat threshold keys with silent defaults while
   the real file nests them — hardening the file changed nothing decisive,
   and a pattern-matching heuristic could still receive `PROGRESS`.
2. The annotation package used public task/family IDs as handles, exposed
   splits, and discussed answers by case name.
3. Category-specific question wording cued the expected category.

R2 repairs the decision procedure, the shortcut family, the annotation
boundary, the question wording, the citation requirement, and CI
enforcement. It adds cases only where blinding demands it (none) and does
not build semantic reasoning.

```
flowchart LR
    T[R2 tasks: 66 neutral-question cases] --> V[Validation + leakage audit]
    O[Pinned Git provenance] --> V
    V --> P[Neutral whitelisted payload]
    V --> R[Core A/B/B0 + S-v1 preserved + V-v2 controls]
    R --> S2[Gated scorer + family bootstrap]
    G[Provisional drafts; independent gold PENDING] --> S2
    S2 --> D[Layered decision: diagnostic / readiness / final]
    P --> F[03B governed adapter: NOT IMPLEMENTED]
    E[Sealed custodian package] --> X[Blind verdict: HOLDOUT_PENDING]
```

## M-A — repaired progress decision

`decide_progress` in `scripts/notebook03a_r2_protocol.py` consumes a flat,
strictly validated threshold contract (`decision_thresholds.json`, v1.6):
every key required, typed, ranged, contradiction-checked; unknown keys
rejected; no defaults anywhere. Tests mutate each threshold and assert a
decisive change; tests delete/corrupt keys and assert rejection.

Four layers, never conflated: engineering validity (freeze/contract),
public diagnostic (per-arm numbers only), blind readiness (holdout,
adjudicated gold, boundary, comparators), final verdict. Public scope can
never yield `PROGRESS`; missing holdout, gold, comparators, or citation
evidence yields `INCONCLUSIVE` naming the missing element. The final D
verdict requires absolute gates plus D-vs-C and D-vs-S margins on both
retention and misleading advances; C is judged against S/A/B0 with its own
reference, so C and D can never share a verdict by thresholds alone.

## Uncertainty

The 66 cases share 39 families. The family is the predeclared unit:
family-level paired bootstrap over precomputed case flags (contract seed,
1000 resamples, 95% percentile intervals), with paired D-vs-S and D-vs-C
differences on the same resamples. Reported: raw counts, family count,
point estimates, intervals, paired differences, category and
authentic/synthetic breakdowns, and predeclared underpowered warnings
(< 20 families or < 20 useful cases forces `INCONCLUSIVE`). Intervals are
sensitivity bounds under family exchangeability, not population inference;
a 3-case shift inside one family is never reported as meaningful.

## M-B — shortcut family v2

`shortcut-control-v2.0` (`scripts/notebook03a_r2_shortcut.py`): lexical
overlap, surface patterns, and small deterministic inference features
(entity overlap, comparator match, replacement language, negation,
universal-vs-limitation asymmetry). No case/family/gold lookup, no answer
tables, no filename dependence, no sabotage branches. Thresholds tuned on
the development split only, frozen before evaluation; version, parameters,
and code hash recorded in replay output before any blind run. v1.0 is
preserved and still replayed for regression. Results reported separately
for legacy families, new families, authentic, synthetic, and (pending)
holdout strata.

## M-C — corpus separation

Development (16 v1.4 cases), public diagnostic (50 R1/R2 cases, exposed),
sealed inputs (pending), independent gold (pending), final outputs. Public
cases keep full regression value but cannot produce the final verdict.
`holdout_contract.md`/`.json` specifies the custodian flow; structural
validation only — a human verifies the access boundary. Current state:
`HOLDOUT_PENDING`.

## M-D — decontaminated annotation package

Opaque handles (`r2-blind-handle:<salt>:<id>`, mapping implementer-side
only and never shipped), no family handles, no splits, no gold field
names, no exact rationale or dev-description strings, generic toy examples
only, self-containment check. `audit-package` CLI fails contaminated
packages. Residual risk documented: repository access defeats renaming;
real blinding needs the sealed boundary.

## M-E — neutral question

One identical instruction on all 66 tasks (pair and claim-support):
assess the relationship, state what is supported and uncertain, and whether
the evidence should influence the current conclusion. The v1.6
transformation (4 templates to 1) is recorded in amendments with affected
fingerprints; a test asserts question uniformity and non-predictiveness.

## Citation, adjudication, CI, deps

- Citation gate (v3): exact spans + full required recall + precision floor
  0.2; failures are misleading advances. Relevance beyond span overlap
  stays pending independent adjudication. Six-scenario tests.
- Adjudication plan: multi-label acceptance, ambiguity flags, predeclared
  category-accuracy exclusions, disagreement records, auditable decision;
  two reviewers + adjudicator required; R2 builds the mechanism only.
- CI: notebook job runs v1.6 validate, leakage audit, provenance,
  baseline replay, normalized comparison, shortcut tests, threshold-contract
  tests, mutation/scoring regressions, and v1.4/v1.5 preservation.
- Notebook-02 narrow-migration spec (7 items + Windows recovery note) in
  `docs/ALIVE-NOTEBOOK-03A-R2-NOTEBOOK02-DEPS.md`; no production rewrite here.

## 03B prerequisites (all incomplete → NOT_READY)

Frozen v1.6; representative diagnostic coverage; provisional labels;
S + V controls; citation gate; validated thresholds; contract migration
specified but not executed; governance adapter, model/settings/pricing
freeze, owner approval, cancellation qualification all pending. No
external inference.
