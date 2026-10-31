# PI-02B-H / bounded R3 correction

Date: 2026-10-31. Base: `c4257e0393b98c3cd81453903e701de389185fcb`, the
verified merge of PR #69. Reviewed source: `ab066db51d3992905980aa5a1122c6e540bd1335`.
Both have tree `73f4b148316440c03d57e7d7f149771f0bf3a264`; their source is identical.

GitHub and `origin/main` both confirm that #69 is closed and merged. The R3 brief
was written against its earlier reviewed head and says to stay on that branch.
The programme explicitly directs a new isolated hardening branch when #69 is merged.
This work therefore uses `codex/alive-pi02b-h`, targeting main in a separate follow-up
PR. The closed PR and all prior owner/review worktrees are untouched. No merge is
performed as part of this correction.

## Production change

Exactly one production line changes, in `WorkflowRunner._stage`:

```diff
-        except Refused:
+        except (Refused, TimeoutError):
             raise
```

The enclosing run handler again sees TimeoutError and retains the bounded `timeout`
reason. `_abandon` continues to determine terminal state and uncertainty from the
actual Pi/request facts. No Governor, reservation, database, dispatch, cancellation,
recovery, provider client, migration or dependency behavior changes.

The initial unchanged-source probe reproduced three timeout-category failures;
other tested behavior remained conservative. With this one line, the permanent
R3 test file has **19 passing cases** in 99.01 seconds, with inherited Windows ZMQ
warnings. Assertions cover state, uncertainty, actual provider-call counts, settled
invocation/Pi/request state, zero held reservations and effect-free execute/recover.

## Permanent tests and mutation proof

Only `tests/test_workflow_r3_guards.py` is added. Existing tests are neither rewritten
nor loosened. The reviewer's portable drafts were stripped of evidence-folder writes,
prints, environment switches and Docker-specific settings. They use existing fixtures.

| Group | Cases | Protected assertion / mutation |
| --- | --- | --- |
| Stage deadline and whole-run deadline | 4 | Timeout label; FAILED before effect, UNKNOWN/unknown_outcome after dispatch; CANCELLED/rejected before dispatch; no repeat effect. Revert the one-line fix. |
| Goal cancellation through real HTTP route | 3 | Before reservation, before dispatch and in flight; 0/0/1 calls, no held reservation, no redispatch. In flight: invocation validated, Pi SETTLED, workflow UNKNOWN. Remove goal-status clause at context.py:151. |
| One stage, one invocation | 1 | Second original role-adapter call refused; one invocation/Pi/request, one upstream call, UNKNOWN rather than false completion. Remove context.py:245. |
| Approved browser-context contract | 3 | Wrong source IDs/action rejected, valid control admitted; untrusted data never widens the server contract. Remove context.py:211 or :212. |
| Inconsistent internal associations | 2 | Other run's stage / other inquiry's invocation cannot reach upstream. Remove runner.py:159 or :163. |
| Inconsistent run identity | 6 | Definition hash/name/version, input hash, authorization reference, goal binding cannot cross the actual fence. Core UPDATE bypasses ORM immutability only in disposable negative-test databases. Remove runner.py:296–301 or :308 as specified in the brief. |

The existing isolated source-mutation harness now includes the 13 R3 mutations.
Results: **34 passing baselines, 33 assertion kills, one documented redundancy**.
That is the prior 20 kills + A10/B1 redundancy unchanged, plus **all 13 R3 mutants
killed by their named tests**. Setup, import, syntax or teardown failures are not kills.
Receipts retain exact guards, replacements and assertion excerpts. No production
mutation switch exists; source edits occur only in the harness's temporary copy.

The final independent review/classification covers 46 other clause mutants: 10
caught, 36 survivors classified as 12 load-bearing gaps, 16 redundant, six unreachable
through supported interfaces and two unresolved. R3 protects all 12 required gaps;
it does not claim every survivor is a vulnerability or every unprobed clause is safe.

## Lifecycle ownership and deferred labels

`context.py:155` is the sole inquiry-state guard if an inquiry becomes terminal
while its goal remains active and executable workflow authority otherwise survives.
Cognition owns inquiry transitions/settlement; WorkflowRunner uses it atomically with
workflow terminal settlement. The independent review found no supported command
that creates that inconsistent live-workflow state. Real stop/pause also remove the
goal's active authority. A direct-SQL terminal flip can bypass settlement and is not
a valid public lifecycle or reservation-leak reproduction. The guard is retained;
no fake SQL lifecycle test or behavior change is added.

The role-contract clause at context.py:255 remains the review's unprobed watch item;
its redundancy is not asserted here. It is unchanged and belongs in the focused
independent review before broader capabilities. Optional goal/provider reason-label
changes are declined to preserve the requested single-line production boundary.

## Supplemental PostgreSQL evidence and scope correction

The four equivalent one-stage/goal-cancellation probes also passed on disposable
PostgreSQL with the exact one-line runtime: **4 passed**, real Pi/scripted provider,
ordinary production host lease and a fresh UUID database per case. This separate
qualification used an isolated temporary source/test copy; permanent R3 tests retain
the requested SQLite fixtures and no database environment switches. It is not a
distributed-worker or independent-service concurrency qualification.

Before receiving the narrower R3 brief, the broader programme work explored extra
independent-service and identity probes. A concurrency diagnostic using copied
Cognition/kernel service views with independent pools/locks admitted two reservations;
the existing final fence stopped one provider call. A proposed row-lock correction
was **removed**, not included in R3. Another extra inquiry-association experiment hit
the existing unique-consumer constraint and failed setup expectations; it is not a
production guard-bypass finding. That exploratory route was stopped and preserved
outside the branch at `C:/Projects/alive-pi02b-h-diagnostics` rather than changing
production to accommodate it. Neither result is counted as R3 qualification. These
unsupported service views must not become a supported worker topology without a
separate concurrency review. The six bounded R3 test groups all pass without that
proposal or any new behavior.

## Commands, exact-source checks and full qualification

```text
uv run pytest -q -p no:cacheprovider tests/test_workflow_r3_guards.py
uv run python -m scripts.workflows_r2_mutations
uv run pytest --collect-only -q -p no:cacheprovider
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
git diff ab066db -- alive migrations pi-runtime uv.lock
```

Collection: **1,237 tests** across both configured test roots. Focused tests, mutation
replay and Ruff pass. The production-only diff command shows just the one timeout
line. No migrations, Pi, Cognition, locks/dependencies or frozen evidence changed.

Full Windows/Linux execution and the final new total are taken from CI on the exact
pushed head, not inferred from collection or the prior 1,205-test result. At this
document's commit they are pending. The PR description/delivery message records the
subsequent exact-head outcomes and links both workflow runs; this document is not a
claim that pending CI passed. No duplicate local full run is started solely to copy
CI's release evidence. The existing CI command retains full discovery and slow-test
duration reporting. Routine edits use quick/targeted checks; subsets are not full passes.

## Review gate and programme continuation

Use [the R3 handoff](ALIVE-PI-02B-H-R3-REVIEW.md) with the exact PR head. Original
review inputs remain byte-preserved, and receipts have an integrity manifest.
There is no paid inference, no new workflow capability and no GUI change.

PI-02C remains gated on independent hardening approval and normal integration. Its
architecture inventory is in the separate `C:/Projects/alive-pi02c-prep` worktree;
it is preparation, not an implemented observatory. No automatic merge, PI-03,
Bespoke selector or parallel workflow engine is part of this correction.
