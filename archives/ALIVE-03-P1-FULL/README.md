# ALIVE-03-P1 — Authorized full evaluation

**Never and Selective scored 120/120; Always scored 119/120. No adaptive-routing advantage over Never was demonstrated.**

Run `966bce12-4260-4100-ac5c-5aa5f56630b5`: **completed**, 120/120 completed tasks.
Run error: `None`. Incomplete tasks: 0.
Execution commit: `a4adcb9b0f64a2e1f4214df3b83a9b58bd5eae41` on `codex/alive-03-p1-selective-cognition`.
No push, merge, deployment, main changes or predictive-policy training.

## Frozen experiment and execution controls

Original freeze `549774ba2c72105b0c075ac9dc2eb486a2b21dd59d911aeb83bbaa080f80cd5d` is unchanged from the qualification archive.
Corpus (120 held-out tasks, 30/category), schema, policy threshold 1.1, scorer, prompts,
model `muse-spark-1.3` and frozen runner were not changed. No policy tuning followed
pilot or evaluation outcomes. The dollar guard is a separately hashed execution overlay,
committed and tested before the first held-out inference. It only restricts calls.

Owner explicitly authorized **$1.00, 350 calls, 500,000 tokens**. The larger account balance
was not treated as permission to bypass these experiment limits. Authorization was persisted
and consumed once. Calls were sequential, with zero automatic retries and the original
90-second paired-task deadline. Two planned 60-task sessions preserved cumulative counters.

Every physical call has a persisted pre-inference USD reservation check; 240 checks
verified within the ceiling. Known usage uses the published rates; unknown/failed usage is
charged conservatively at the maximum rate against reserved tokens. Reservations and upward
rounding can stop a run below $1.00. This is an application rate-card guard, not account billing.

## Outcomes

| Policy | Correct | Abstentions | Critic calls | Path tokens | Path USD (est.) | Mean seconds |
|---|---:|---:|---:|---:|---:|---:|
| always | 119/120 | 60 | 120 | 322,956 | $0.568976 | 4.240 |
| never | 120/120 | 60 | 0 | 149,993 | $0.265740 | 2.078 |
| selective | 120/120 | 60 | 0 | 149,993 | $0.265740 | 2.078 |

| Category | Always | Never | Selective |
|---|---:|---:|---:|
| adversarial | 30/30 | 30/30 | 30/30 |
| ambiguous | 30/30 | 30/30 | 30/30 |
| contradictory | 30/30 | 30/30 | 30/30 |
| straightforward | 29/30 | 30/30 | 30/30 |

The full machine-readable analysis includes unsupported claim acceptance, citation validity,
abstention precision/recall, failure and timeout rates, rescue/regression rates and opportunities,
median/p95 latency, selection errors and paired uncertainty intervals. `paired-outcomes.csv`
preserves each arm's score, invocation reason, cost, latency and error. A null rescue rate
means no incorrect initial decisions supplied rescue opportunities; it does not mean measured
rescue probability is zero.

Correctness transitions after criticism: **1**;
see `analysis.json` for task IDs and outcomes. Selection errors are observed Always-arm proxies,
not guaranteed counterfactuals for an independently sampled Selective Critic.

### The single regression is a recommendation-contract failure

Task `669bf5d00df69e42be3a49e5` (straightforward, median) supplies verified values
34, 81 and 67. An independent arithmetic check orders these as 34, 67, 81, so the median
is 67. Both the initial and reviewed decisions give 67.0 with the same three valid citations.
The Critic changes `proceed` to `investigate` and adds uncertainty including
"No permission granted for action". This is a read-only numerical task, with no action requested.

The frozen scorer requires `proceed` for an answer and therefore returns
`answer_requires_proceed_recommendation`. We retain the original 119/120 score and regression
classification. It is **not a numerical error or invalid citation**. The frozen
`unsupported_acceptance` metric also flags this contract failure; that label should not be
interpreted as evidence that the number itself lacked support. Full decisions and source
facts are retained in `correctness-transition-audit.json`. No scoring rule was changed.

The observed accuracy gap is 1/120 (0.83 percentage points). The predeclared family-cluster
bootstrap interval for Selective minus Always is [0, 0.025], including zero. One discordant
case on this synthetic corpus does not establish a general accuracy advantage.

## Actual usage, cost and latency

- Physical calls: **240 / 350**.
- Provider-reported tokens: **322,956**;
  Governor-charged tokens: **322,956 / 500,000**.
- Estimated unique physical cost: **$0.568976**;
  conservative spending-guard charge: **$0.569077 / $1.00**.
- Unknown-usage calls: **0**.
- Wall time including database accounting and scheduling: **526.5s**;
  summed paired-task wall time: **508.8s**.
- Remaining cumulative Governor budget: **110 calls, 177,044 tokens**.

Rate-card estimates use [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), rechecked
before execution: $1.25/M input, $0.15/M cached input and $4.25/M output. Reasoning tokens are
included in completion tokens. **Confirmed provider billing is unavailable.**

One initial decision is shared across all three arms; it is paid once physically but included
in each path comparison. Do not add policy path costs to estimate billing. Policy latency
includes its own initial/review and Governor I/O, excluding competing-arm queue time; paired
task wall time includes both arms. These are not independently timed deployments.

## Interpretation and limits

The calibrated threshold is 1.1, so Selective behaves exactly like Never on every possible
feature vector. Their shared-artifact outcomes are mechanically identical, not independent
replication. This experiment can measure the incremental value of the Always Critic and
the consequence of calibration choosing no criticism; it cannot demonstrate adaptive routing
across situations when the selected policy never invokes its Critic.

The numerical corpus is narrow, with explicit source-authority rules and synthetic adversarial
annotations. Disjoint operation families and lexical audits reduce contamination but do not
prove semantic independence. The evaluation file was procedurally sealed plaintext, not blind
to generator authors. Only six task families limit uncertainty estimation. Wilson intervals
are descriptive; paired intervals use the predeclared 2,000 family-cluster bootstrap resamples.
Degenerate zero-difference intervals are conditional on this corpus, not guarantees of
equivalence on new distributions. Calibration used only eight development pairs.

Failure rows and incomplete tasks are preserved; scheduled-task accuracy and unresolved rates
use 120 as the denominator. Other arm rates describe completed rows. No failure was retried
to replace an unfavorable outcome. Negative or tied
findings do not establish that criticism is generally useless. Further research should test
an independently developed evidence-backed criticism mechanism or a harder, newly frozen
corpus before adding policy learning. No P2 work was started automatically.

## Evidence

`results.json` contains all recorded decisions and per-call data. `redacted-usage-ledger.json`
retains synthetic inputs, structured outputs, prompts, correlation IDs, usage and latency.
`authorization-and-budget-audit.json` records the one-use authorization, all USD checks,
Governor reservations/settlements, session boundary and completion. Credentials, request
headers, runtime identity and personal browser data are excluded. `execution-plan.json`
contains the pre-unsealing overlay hashes and budget settings. The original qualification
archive remains intact. Pre-execution backend suite: 58 passing (55 prior + 3 spending tests).
Two additional postprocessing tests pass, checking retained failures, unknown costs and
scheduled-task denominators. They do not change the experiment or its inference decisions.

`manifest.json` hashes every evidence payload except itself. The evidence commit follows the
execution commit; use `git log` for final HEAD. The pre-existing untracked `models.txt` remains
outside the commits.
