# ALIVE-03-P1 — Selective Cognition Experiment

This milestone qualifies a reproducible experiment. It does not claim improved intelligence
or authorize execution of the complete paid benchmark. Baseline:
`72b2e4c12b1864bb94136af96a82fd96a6a6bbe2`, branch
`codex/alive-03-p1-selective-cognition`.

## Protocol

Question: can a deterministic, development-calibrated controller preserve correctness while
reducing critical-review cost compared with AlwaysCritic and NeverCritic?

The primary evaluation has 120 synthetic, first-party tasks: 30 straightforward, 30 insufficient,
30 contradictory and 30 adversarial. Calibration contains 48 tasks (12 per category).
Development uses sum, difference, minimum and maximum; evaluation uses ratio, median,
weighted mean, counting, temperature conversion and rate. Families and exact payloads are
disjoint across splits. IDs and numbers derive from a fixed seed. Ground truth is recomputed
deterministically; hand-calculated arithmetic fixtures independently check each operation.
Every task records sources, objective, expected outcome, scoring rule, abstention conditions,
verification and provenance. No ALIVE-02 benchmark task is reused as evaluation evidence.

`split-manifest.json` predeclares eight development pairs for live threshold calibration and
four separate development tasks for the qualification pilot, using deterministic stratified
ID ordering (two and one per category respectively). The other 36 development tasks remain
available for future development, not covertly included as evaluation evidence. The 120-task
evaluation file is procedurally sealed, not encrypted: generator authors can inspect its
synthetic content. No held-out model outcomes are available during policy calibration.

The contamination audit rejects duplicate IDs/payloads, overlapping operation families and
cross-split objective trigram Jaccard similarity at or above 0.65. These lexical checks are
limited: they cannot establish semantic independence, and tasks within a family are correlated.

## Intervention and model controls

All arms receive identical evidence and one shared initial Meta decision. NeverCritic uses it;
AlwaysCritic receives an independent additional Critic review; SelectiveCritic receives a
separately recorded Critic review only when its controller selects one. Review means a revised
final conclusion in the existing structured RoleOutput, with concise criticisms. The existing
Critic role prompt is extended by a versioned experiment instruction. No actions execute.
Arm order is randomized deterministically per task. Shared initial output is one live call,
not three independent trials. Separate Critic outputs preserve sampling differences.

Primary model is pinned to `muse-spark-1.3`, with native structured output, 1,536 maximum
completion tokens, minimal reasoning effort, zero automatic retries and a 90-second total
paired-task deadline. Model availability is checked before starting. No role override or
stronger model is used. Inputs, outputs, usage, correlation IDs, errors and timing are logged.
No private chain of thought is requested or archived.

All policies implement `choose(Features)`. SelectiveCritic receives only numeric uncertainty,
contradiction, evidence gap, weak-evidence fraction, action risk and estimated review tokens.
It has no task ID, category, family or expected-answer access. Fixed weights are
0.30/0.30/0.20/0.10/0.10, minus 0.03 times anticipated tokens/3,000 (capped at one).
Threshold grid is 0, 0.1, …, 0.9, 1.1. Calibration maximizes mean correctness minus
0.05 times review tokens/3,000 (capped at one). Ties prefer fewer calls, then higher threshold.
The eight paired development observations select only this threshold. Selecting Never-like
behavior is valid if calibration shows no benefit. This is parameter selection, not RL.

## Scoring and analysis

A correct answer requires one finite numeric `computed_result` claim for the supplied subject,
`proceed`, absolute tolerance 0.01 or relative tolerance 1e-6, and citations covering every
required verified same-window field. Unknown citations invalidate the answer. Missing required
fields or contradictory equally authoritative readings require abstention with no claims.
Untrusted annotations never override verified facts. Wrong or unsupported accepted claims count
as unsupported claim acceptance. Citation validity separately measures existing source IDs;
the correctness check additionally requires verified coverage.

Report correctness, correct abstention (precision/recall), unsupported claim acceptance, review
invocation, allocated tokens, rate-card cost per correct result, and end-to-end policy path
latency. Report category results, citation validity, rescue/regression counts, observed selection
errors, failures/timeouts and paired task-level correctness differences. A rescue changes an
incorrect initial result into a correct reviewed result; a regression does the reverse.
Always-arm outcomes are observed proxies for selection errors, not guaranteed counterfactuals
for an independently sampled Selective Critic.

Wilson accuracy intervals are descriptive. Paired differences use deterministic 2,000-resample
family-cluster bootstrap intervals (seed 3031). Only six evaluation families and four pilot
tasks limit uncertainty estimation. Pilot outcomes cannot establish superiority. Future full
results should assess Selective versus both alternatives, including uncertainty, accuracy,
abstention, cost and failure tradeoffs; no superiority conclusion is precommitted.

Policy path latency includes initial inference, its own review and Governor I/O, excluding
competing-arm queue time. Actual paired task wall time is recorded separately. Reusing initial
artifacts means these are not independent deployments. Shared initial costs appear in each
policy path for comparison but are paid once physically. Never sum policy allocations as billing.
Missing provider usage stays unknown; Governor charges the full reservation conservatively.
Incomplete tasks and run errors remain visible; they must not silently become successes or be
ignored when qualifying the full experiment.

## Freeze and authorization lifecycle

Design freeze hashes corpus, schema, scoring, policy, prompts, runner, metrics, relevant model
code and dependency lock before calibration. Final freeze adds calibration evidence and policy
parameters before the pilot. UTF-8 text hashes normalize checkout newlines; archive manifests
also preserve exact byte hashes. The freeze manifest hashes its own identity. Source drift stops
execution. Finalization verifies the original calibration freeze. After any full run starts,
API design/policy changes are forbidden. There is no automatic tuning from evaluation outcomes.

Each request reserves existing Governor call/token budgets in the database before inference
and settles reported usage transactionally. Per-request, task, session, experiment and run
ceilings apply. One worker and no browser/tool actions. Pausing, stopping and configuration
changes cannot reset budgets around an active experiment. Restart marks unfinished runs
interrupted, conservatively settles unknown reservations, and never replays paid inference.

The authorized qualification is at most 16 calibration calls plus 12 pilot calls, with 100,000
tokens per phase, constrained further by existing Governor budgets. A deliberate new session
before calibration preserves cumulative experiment expenditure. No full-run budget is silently
raised. The full run requires a completed error-free four-task live Meta pilot for the exact
freeze, an exact owner confirmation and a one-use persisted authorization. Its plan explicitly
covers two 60-task sessions (at most 180 calls each), preserving cumulative experiment counters.

## Reproduce locally

```powershell
uv sync --locked
./scripts/dev.ps1
uv run pytest -q
uv run python -m scripts.experiment03 prepare       # fresh checkout only, before freezing
uv run python -m scripts.experiment03 freeze-design
uv run python -m scripts.experiment03 calibrate
uv run python -m scripts.experiment03 freeze-policy --run-id <calibration-id>
uv run python -m scripts.experiment03 pilot
uv run python -m scripts.experiment03 review
```

An already frozen corpus refuses regeneration through the CLI. Use the existing cognitive
control to pause autonomy and deliberately open a session if needed, preserving cumulative
budgets. The Cognition dashboard displays persisted experiment records and decision reasons.
Mock runs are marked controlled fixtures and cannot qualify a primary Meta pilot or full run.
The runner stops at a budget or provider failure; inspect/export evidence before retrying.
Full execution is deliberately not part of this sequence. After owner review, configure the
Governor and use `authorize-full` with the exact confirmation and explicit ceilings, then
`full --authorization-id … --max-calls 360 --max-tokens 1500000` for that freeze.

Archive and review evidence: [`archives/ALIVE-03-P1`](../archives/ALIVE-03-P1/README.md).
Published model rates are estimates, not confirmed billing:
[Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits).
