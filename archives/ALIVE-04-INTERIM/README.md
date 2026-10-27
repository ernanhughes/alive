# ALIVE-04 interim engineering evidence: PASS_WITH_LIMITATIONS

This archive records the OpenCode interim branch's controlled regression evidence for ALIVE-04.
It is **not** a native Chrome/Meta requalification and it does **not** replace
`archives/ALIVE-04`. The original native qualification remains frozen at implementation commit
`62be48adcc63794ceb65263cfccbf84d0b662cc5`.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Starting commit | `0809f3788b521328e37d0bb41e87a6aefde76ef3` |
| Branch | `opencode/alive-04-interim` |
| Interim implementation commit | `b6aad7df88a2b5a1bd217a91dc0b977960c30311` |
| Evidence kind | Controlled test-harness fixture |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |
| Provider recorded in journey | `mock` (`controlled-living-v1`) |
| Browser adapter | Synthetic in-process test adapter, not Playwright/Chrome |

The live local run was deliberately not attempted. Ports `8000` and `5173` were occupied by the
owner's primary `C:\Projects\alive` worktree, which contains uncommitted ALIVE-05 work. This
archive was generated in an isolated SQLite database, and the primary worktree was not touched.

## What the controlled journey shows

The evidence file `evidence/controlled-fixture-journey.json` contains the complete persisted
journey, including both browser observations, both deterministic choices before their fixture
reasoning calls, the recalled transition, the policy before/after hashes, and the feedback.

| Encounter | Recalled transitions | Action | Reward | Factual support | Feedback corroborates source | Goal resolved |
|---|---:|---|---:|---|---|---|
| First | 0 | Monitor | -0.50 | No claim | Not applicable | No (safe abstention) |
| Related | 1 | Retrieve | +0.85 | Yes | Yes | Yes |

Both observations project to the same feature hash. The second original-policy counterfactual
still selects **monitor**; the updated policy selects **retrieve** and recalls the first
transition. The first after-policy hash equals the second before-policy hash. These are
deterministic policy comparisons, not model sampling differences.

The second transition now stores `sources[0].value = "20"`, `outcome.source_value = "20"`,
`outcome.feedback_confirms_source = true`, `outcome.factual_correct = true` and
`outcome.resolved = true`. The first transition has no sources and is a recorded safe
abstention.

## What changed in this branch

- Factual support now compares a model claim with the value of the source it cites. Previously
  the claim was compared with the end-of-episode feedback, so a claim could match feedback while
  contradicting the evidence reference it claimed to use.
- Goal resolution now requires both factual support and independent feedback corroboration of
  the source. Feedback cannot make a contradictory claim factual.
- The inference path rechecks the persisted controlled-read grant immediately before reserving
  tokens.
- A journey interrupted by a backend restart has its grant revoked, its reservation settled
  conservatively, and a `living.interrupted` event recorded. It cannot be replayed.
- The Living dashboard shows the deterministic choice reason, the recalled prior outcome,
  Governor-permitted operations, separate source and feedback measurements, factual support,
  feedback corroboration, conclusion-contract status and the Governor envelope.
- `numeric_equal` returns `False` for malformed non-numeric values instead of raising.

## Verification

| Check | Result | Transcript |
|---|---|---|
| Backend suite | 86 passed | `validation/backend.txt` |
| Living-focused suite | 10 passed | `validation/living-focused.txt` |
| Frontend unit suite | 5 passed | `validation/frontend-tests.txt` |
| Production dashboard build | Passed | `validation/frontend-build.txt` |
| Ruff check and format check | Passed | `validation/ruff.txt` |
| Whitespace diff check | Clean | `validation/whitespace.txt` |
| Frozen ALIVE-04 classification replay | Both episodes match | `evidence/frozen-archive-replay.json` |

The frozen replay compares only `resolved`, `safe_abstention` and `factual_correct`. The original
archive was not modified and its new fields were not backfilled. The interim dashboard labels
missing legacy fields as "Not recorded for this legacy journey".

## Reproduce the controlled evidence

The fixture uses an in-process synthetic browser adapter and an isolated SQLite database. It
makes no network inference calls. The generation approach is the same one exercised by
`tests/test_living.py::test_controlled_journey_has_causal_memory_and_real_counterfactual`, which
is the durable reproducible check.

```powershell
uv run pytest -q tests/test_living.py
npm test --prefix dashboard
npm run build --prefix dashboard
```

A native Chrome/Meta requalification still requires free ports, owner authorization and a cold
qualification database. Do not reset an existing policy to obtain a favorable demonstration.

## Limits

- This is **not** evidence of native Chrome behavior, Meta reasoning, provider usage or paid
  qualification.
- The two-encounter fixture is inspectable and synthetic. It is not a blinded benchmark.
- The action policy is a tiny exact-context empirical outcome mean. It is not deep RL, MR.Q,
  general self-improvement or open-web autonomy.
- Two outcomes do not establish generalization; the dashboard reports small-sample uncertainty.
- The new dashboard fields were validated by a React component test and production build, not a
  new native browser screenshot.
- Existing ALIVE-01/02/03 archives and benchmarks are untouched.
