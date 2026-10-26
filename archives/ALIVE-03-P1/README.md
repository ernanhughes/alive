# ALIVE-03-P1 qualification — PASS_WITH_LIMITATIONS

Gates A–F completed. Full evaluation has **not run** and remains subject to explicit owner
authorization and increased configured Governor budgets. No MR.Q or RL training was added.

Branch: `codex/alive-03-p1-selective-cognition`. Tested implementation: `87e723276e5fc00ed432fab6bb52744bcda79128`.
The following archive commit adds evidence only; use `git log` for the final branch HEAD.
Worktree at qualification contains only the pre-existing untracked `models.txt` after commits.
No push, merge, deployment or changes to main were performed.

- All 15 ALIVE-02 payload checksums verified; frozen evidence unchanged.
- Regressions: 33 existing backend tests, 4 frontend tests, 2 existing Chrome E2E tests.
- New: 22 backend tests and 1 policy-comparison Chrome E2E test. Total backend: 55 passing.
- Production dashboard build, Ruff lint and formatting pass.
- Corpus: 48 development tasks (12/category), 120 held-out tasks (30/category).
- Live calibration: 8 development pairs, 16 Meta calls, 20,616 tokens, estimated $0.042567.
- Distinct live pilot: 4 development tasks, 8 Meta calls, 10,747 tokens, estimated $0.02027745.
- Total qualification inference: 24 calls, 31,363 tokens, estimated $0.06284445.
- Always/Never/Selective pilot correctness: 4/4 each; Critic calls: 4/0/0 respectively.
- Calibration selected threshold 1.1: Selective currently behaves like NeverCritic. No Critic
  rescue or regression was observed. This result is preserved rather than tuned away.

Freeze identity: `549774ba2c72105b0c075ac9dc2eb486a2b21dd59d911aeb83bbaa080f80cd5d`.
Dataset/evaluator hashes: `freeze-final.json` (canonical UTF-8 source identities) and
`manifest.json` (exact archived bytes). Schema, scorer, dependency lock, policy, model and
prompt identities are frozen. Full-run entry verifies the same identity and consumes a one-use
authorization. Design/policy re-freezing is forbidden after evaluation unsealing.

## Full paid evaluation review

Pilot-scaled projection: **240 calls,
322,410 tokens, estimated
$0.608324**. Conservative run ceilings proposed:
360 calls and 1,500,000 charged tokens, across two explicitly authorized 60-task sessions.
At the current maximum published token rate, that token ceiling corresponds to a $6.375
rate-card bound; it is not an invoice or a guarantee about account billing.

Remaining Governor budget at snapshot:
{
  "session_calls": 27,
  "session_tokens": 200000,
  "experiment_calls": 37,
  "experiment_tokens": 430903
}

The existing experiment call ceiling cannot cover even the projected 240 calls.
No budget was raised for the full run. The review pack suggests 180 calls/1,000,000 tokens
per session and 500 calls/2,000,000 tokens cumulative, preserving already spent counters.
Review these settings and give explicit full-run authorization before executing anything.
Ready **for owner review**, conditional on those two prerequisites; not automatically runnable.

## Interpretation and limitations

The pilot qualifies the pipeline, not unseen performance or selective-policy superiority.
Only eight pairs calibrated one threshold; all initial answers were already correct. The
controller may be underpowered or the development tasks too easy. Deterministic signal weights
are designed, not learned. No evaluation outcome was used for threshold selection.

The first-party numerical corpus is narrow. Operation families are separated across splits,
but lexical audits cannot prove semantic independence; templates within families are correlated.
The evaluation file is procedurally sealed plaintext, not blind to generator authors. It has
not been submitted for model inference. Prompts and scorer share an explicit evidence contract,
which may make these tasks easier than open-world investigations.

Shared initial outputs are not independent live trials. Critic outputs are separate when
invoked, although this live threshold never invokes Selective's Critic; controlled tests verify
the distinct-review path. Path latency excludes competing-arm queue time; task wall time is
recorded separately. Shared initial cost is attributed to every policy path but paid once.
Never add path totals to estimate provider billing.

Wilson intervals and family-cluster bootstrap intervals are descriptive; the four-task pilot
has weak uncertainty estimates. Full-run failure/timeout or budget interruption must be
reported with incomplete-task counts, not silently omitted. Source drift requires renewed
development qualification before evaluation; after unsealing, the policy remains frozen.

Costs use [Meta's published rate card](https://dev.meta.ai/docs/pricing-rate-limits), checked
2026-10-26: $1.25/M input, $0.15/M cached input, $4.25/M output. Reasoning is included in
completion usage. **Confirmed provider billing is unavailable.** Projection varies with task
length, sampling, caching and failures. Existing Governor request reservations are conservative
UTF-8 estimates, not provider-side guaranteed quotas.

See `protocol.md`, `review-pack.json`, `results/`, `usage/redacted-ledger.json`, `validation/`
and `acceptance.png`. The manifest covers every archive payload except itself.
