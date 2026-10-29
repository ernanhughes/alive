# ALIVE-F002 — a cancelled model invocation must never stay `reserved`

Status: **draft correction**. Scope is exactly ALIVE-AUDIT-01 finding F-002 in `alive/cognition.py`. Not changed: budget accounting, the `ModelGateway`, any other module's reserve-then-dispatch code, Pi. No inference, no spend.

Baseline: `origin/main` `df7866eb9222e8f539b8b138353b2bb532e65559`.

## Problem

`Cognition.call_role` commits the model reservation (a `ModelInvocation` row plus the run's worst-case charge) inside `async with k.lock, k.db.sessions.begin()`. The `try`/`except BaseException` that settles a cancelled invocation started *after* that block. A cancellation delivered while the transaction exits therefore bypassed it, and `finish()` made the run terminal without reconciling its invocations. The result was a `FAILED` or `CANCELLED` investigation whose invocation stayed `reserved` (the audit's reproduction: `'reserved' != 'cancelled'`). The conservative charge was retained, so this is a lifecycle and reporting defect, not undercharging. Restart recovery later marks such rows `interrupted`, which is a backstop, not timeout settlement.

This is also the cause of the red Ubuntu run `40882738081` (`test_provider_timeout_is_bounded_and_recorded`) on `1b6da07`, which was first mislabelled a timing flake. It is a real race that rarely loses.

I reproduced the audit's probe on `df7866e` before changing anything (receipt below).

## Correction

1. **One owner for the invocation.** `call_role` wraps a new `_invoke_role`; a single outer handler settles the invocation on any exit from the start of the reservation to the end of settlement. The invocation id is recorded in a ledger *inside* the reservation transaction, so a cancel during the commit still finds it. If the transaction rolled back, the row is absent and nothing is settled.
2. **Shielded settlement.** Settlement runs under `complete_despite_cancel`, so a second cancellation cannot abort it; the cancel is re-raised once settlement finishes.
3. **Never rewrite a settled row.** Settlement only acts on a row that is still `reserved`.
4. **Terminal safety net.** `finish()` settles any remaining `reserved` invocation of the run in the same transaction as the terminal transition, as `interrupted` (completion is genuinely unknown, matching restart recovery), keeping the conservative charge.
5. **Honest rejection label.** A response is recorded as `rejected` only when parsing or reference validation failed, not when a valid response was merely not yet settled.

Charging is unchanged: every settled invocation that did not validate records `charged_tokens == reserved_tokens`.

## Evidence (Windows, local; Ubuntu runs in CI)

| Check | Result |
|---|---|
| Audit probe on `df7866e` | **FAILED** `reserved != cancelled` |
| New barrier tests on `df7866e` | **6 failed**, 12 controls passed |
| Same tests with the correction | 20 passed in `tests/test_recovery_budgets.py` |
| Audit probe with the correction (scratch, verbatim) | passed; also promoted into the suite |
| Full suite | 719 passed, 7 skipped, 1 xfailed, 0 failed |
| Stress: the originally red test, 4 parallel workers x 25 under load | 100 / 100 passed |

The five stranding windows reproduced before the fix: cancel before the reservation commits, at the commit's exit, after a response is received, at the success settlement, and a second cancel during settlement.

**Mutation probes** (each safeguard removed must fail a test):

| Mutant | Result |
|---|---|
| No outer handler | 8 tests fail |
| Settlement not shielded | 2 fail |
| `finish()` safety net removed | 1 fails |
| Handler rewrites already-settled rows | initially **survived**; a test was added; now caught |
| Charge not retained | 7 fail |
| Invocation id recorded only after the transaction exits | 8 fail |

The stress run is not discriminating by itself (the race rarely wins); the deterministic barrier tests are the evidence.

## Decision for the owner

Any `CancelledError` is labelled `cancelled`, including one that lands while a provider request may be in flight (unchanged from before). ALIVE-PI-01B wants "cancelled before dispatch" and "ambiguous after possible dispatch" separated. This correction keeps `cancelled`; the distinction is proposed for PI-01B's own request records, or as a durable `dispatch_started` marker on `ModelInvocation`.

## Limits

* The same reserve-then-dispatch pattern is written inline in `living.py`, `experiment/service.py`, `research_relationships.py` and `web_experience.py`. They were not audited for F-002 here.
* Linux was not run locally. A cancellation raced against a real network call was not exercised; the barriers simulate it at exact awaits.
* The earlier statement in `docs/demo/ALIVE-DEMO-INTEGRATION-01-REPORT.md` that the timing failure "has not recurred" still needs a docs correction.
