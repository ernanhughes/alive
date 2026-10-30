# ALIVE-PI-02B qualification report

Date: 2026-10-30. Branch: `feat/alive-pi-02b-execution`.
Fetched base: `4fed829aa57245b93796e98808818fcb0aa58e8f` (INT-02 merged).
Implementation: `4de4f86c77fee7567b320965cb1c3b532ba4fa24`.
Subsequent changes are review documentation, receipts and a mutation-script docstring.

During qualification, main advanced to `8e001d6255e53525f0b276c9cb68f910238390cc`
with unrelated documentation moves and logging changes. It remains a descendant of
the recorded base and does not overlap the execution implementation. The review
branch preserves the exact baseline used for the comparisons below.

## Delivered behavior

A trusted owner can execute an immutable, active procedure through a sequential
WorkflowRunner. It uses existing cognition admission/reservation/accounting,
ModelGateway, PiGateway, pinned PiRunner and metered egress. No second inference
client, provider credential path, prompt builder, general artifact store or learning
algorithm was introduced. The operation/authority inventory and exact limitations
are in [the architecture](ALIVE-PI-02B-ARCHITECTURE.md).

The genuine first procedure is `research-review` **v2**: exact approved context →
cognition/Pi role → existing reference validator → retained result. Historical v1
is unchanged. The second is `source-comparison` v1: approved context → existing
deterministic society comparison → retained result. Both use the same runner,
authorization and storage, with four versus three stages, different operations and
contracts. There is no workflow-name branch. Neither fixture directly inserts success.

The local scripted provider returns a RoleOutput through the actual Pi **1.4.0**
subprocess and existing loopback proxy. One actual provider request has the exact
ModelInvocation correlation, no tools and no streaming. Pi settles with confirmed
cleanup. Usage and request facts are retained; unknown dollar cost stays null. The
existing INT-02 receipt resolver resolves that actual workflow stage. Reference
validation is independent deterministic validation of source identities; it is **not
semantic truth**. Scripted content does not demonstrate model reasoning quality.

Three workers with separate database pools and independent Python locks race to
execute the first run: one owner, one model invocation and one provider request.
The second graph adds zero model requests. Both settle Governor reservations, retain
bounded artifacts, restart and replay without dispatch, artifacts or learning writes.
No Intelligence feedback, learning success or policy update is claimed.

## Change inventory

- New literal adapters, owner/context contract and runner in `alive/workflows`;
  explicit controlled examples and trusted lab-only fixture authorization.
- Shared run construction and cognition finishing preserve existing paths; workflow
  role admission links the stage and invocation in the existing reservation transaction.
- Existing Pi dispatch fence receives a fail-closed workflow authority callback;
  revocation between reservation and dispatch prevents upstream transmission.
- `0010` follows actual head `0009`: one execution table plus the stage-to-Pi FK.
  Historical dangling Pi references cause refusal before DDL, without rewritten data.
- Startup reconciles after existing cognition/Pi recovery. Cancellation, crashes and
  failed persistence preserve possible effects as UNKNOWN without automatic retry.
- Existing read APIs add duration, nullable usage/cost, executable operation metadata
  and a hash-checked result route. All nine workflow routes are GET-only.
- New real-runtime fixture and mutation harness; CI runs SQLite and PostgreSQL
  genuine execution. Tests cover authority, rollback, cancellation, receipt integrity,
  races, migrations and exact replay. Old test changes adapt to schema/FK/route count
  and narrowly allow Pi model types while retaining executor/provider import bans.

## Qualification evidence

Receipts are retained under [validation/pi02b](validation/pi02b). They contain local
fixture identities, bounded scripted results and fake-provider receipts, not secrets.
The Windows test interpreter is `C:/Projects/alive/.venv/Scripts/python.exe`
(Python 3.13.3), using locked dependencies. Host Node is 25.8.2; the final Docker
image uses Node 24.22.2. Pi remains lockfile-pinned at 1.4.0. No lockfile changed.

| Check | Result |
| --- | --- |
| Baseline workflow/intelligence/cognition/gateway/Pi tests | 424 passed, 5 skipped, 225 warnings |
| Focused workflow/intelligence/migration qualification | 190 passed, 122 warnings |
| Full Windows backend | 1,161 passed, 12 skipped, 1 xfailed, 906 warnings; 1,164.87 seconds |
| Late transaction fault tests, separate from full-suite collection | 2 passed, 2 warnings; also 2 passed in Linux |
| Windows Pi/gateway/recovery regression selection | 185 passed, 5 skipped, 116 warnings |
| Linux image regression selection | 487 passed, 1 skipped; 2 fixture-mount failures; both rerun passed with complete scripts mount |
| Linux supplemental mount-corrected run including transaction tests | 4 passed |
| Genuine execution, SQLite | PASS: two graphs, 3 independent claim workers, 1 request, restart/replay, zero learning delta |
| Genuine execution, host PostgreSQL | Same PASS |
| Genuine execution, Docker PostgreSQL | Same PASS |
| Actual Docker process restart and three API replays | PASS: 6 identical response bodies; 2 runs, 7 stages, 1 invocation/Pi/request, 0 learning updates unchanged |
| PostgreSQL fresh upgrade → downgrade 0009 → upgrade | PASS: head 0010, execution table and named Pi FK present |
| Dashboard | 15 tests passed; production build passed |
| Extension Node regression | 36 tests passed |
| Docker image build / smoke / API E2E | PASS / 8 checks / 6 groups |
| Source/image parity | PASS: SHA-256 of every changed production Python/migration file matches tested image |
| Ruff | All checks passed; 287 Python files formatted including qualification replay script |
| Mutation baselines and mutations | 11 baselines PASS; 11 guards KILLED by relevant failed assertions |
| Frozen archive/protocol verifiers | PASS; manifests and protocol hashes unchanged |
| Paid inference, live Chrome interaction, model-quality evaluation | NOT_RUN |
| Independent reviewer approval / remote GitHub CI | PENDING at handoff |

The full backend collected before the two transaction tests were added; report its
count separately. Production code did not change after its start. Supplemental
transaction tests cover rollback before result commit and a real settled Pi effect
followed by failed stage persistence: no duplicate request, UNKNOWN workflow, charged
validated call. This is not simulated Pi qualification.

The tested Docker image is
`sha256:d309e8d44cbdfa23b871f7ecad7dd65fc574cf01f078c75aad6f70c38c1e1c2e`.
PostgreSQL qualification uses an isolated pgvector/PostgreSQL 17 container; CI's
configured PostgreSQL 18 job remains separately pending. Only task-owned containers
are stopped after qualification; unrelated local services and worktrees are preserved.

## Commands and receipt interpretation

Run from repository root after `uv sync --locked` and pinned Pi `npm ci --ignore-scripts`:

```text
python -B -m pytest -q -p no:cacheprovider
python -B -m pytest -q -p no:cacheprovider tests/test_workflow_transactions.py
python -B -m scripts.workflows_execute_check
python -B -m scripts.workflows_execute_check --database-url <disposable-postgresql-url>
python -B -m scripts.workflows_execution_mutations
python -B -m ruff check alive migrations scripts tests
python -B -m ruff format --check alive migrations scripts tests
node --test tests/extension-background.test.cjs tests/extension-capture.test.cjs tests/extension-live-background.test.cjs tests/extension-live-companion.test.cjs tests/extension-panel.test.cjs
npm test --prefix dashboard
npm run build --prefix dashboard
docker build -t alive-pi02b-execution:qualification .
python -B scripts/docker-smoke-test.py --base-url http://127.0.0.1:18048
python -B scripts/docker-e2e.py
python -B docs/workflows/validation/pi02b/container_replay.py
python -B -m alembic upgrade head
python -B -m alembic downgrade 0009
python -B -m alembic upgrade head
```

API tests use a disposable owner token via environment. The replay script is a
qualification-only utility requiring the task-owned containers and the Docker
fixture receipt; it does not execute a workflow. Backend APIs never start one.

[The mutation report](ALIVE-PI-02B-MUTATIONS.md) records each target and outcome.
Mutation receipts record each target test and failed assertion. Guard removals cover
dispatch fencing, operation authority, definition integrity, database claiming,
budgets, model admission, Pi settlement, ambiguous recovery, output schema, evidence
scope and historical replay. Every probe first runs unchanged and must pass. The
plugin is opt-in under tests, with no production mutation switch.

## Failures encountered and corrected

Early development runs exposed an outdated foundation test that prohibited even Pi
receipt-model imports, missing historical-FK assumptions and response timestamp
normalization breaking exact replay. These were corrected narrowly; executor/provider
imports remain banned, receipt FK tests now require actual identities, and retained
artifact timestamp spelling is preserved. SQLite run claims now perform their
conditional write before reads to avoid a read-to-write upgrade race. Counter tests
exclude unrelated heartbeat events rather than becoming timing-dependent.

Initial mutation detection did not accept pytest's `E assert` form, and raising through
an AnyIO test portal could close the portal before cleanup. Assertions were moved
inside the asynchronous probe and the detector rejects setup/collection failures.
All final 11 probes have passing baselines and actual assertion kills. Obsolete full
runs were stopped after corrections and are not counted as passing qualification.

The Linux image intentionally ships only three operational scripts. Mounting tests
without all source scripts caused two regression failures (missing benchmark/native11
imports/ratchet sites). Mounting the complete unchanged `scripts` directory fixed both;
the supplemental receipt preserves that outcome. A host migration command initially
used system Python without Alembic; rerunning with the locked virtualenv passed.
Windows ZeroMQ emits inherited Proactor/selector warnings. The full run also records
unraisable subprocess finalizer/closed-pipe/closed-event-loop warnings around Pi
tests; these are retained in `backend.txt`, not reported as warning-free qualification.
Actual workflow fixture receipts independently confirm Pi cleanup and settled usage.
Locked Pi installation reports inherited npm advisories; no dependency upgrade or
exploitability assessment was part of this milestone.

## Scope, custody and remaining limits

Implementation took place in a new worktree. The pre-existing dirty PI-02B candidate
and the owner's main checkout were never reset, stashed, cleaned or edited by this
task. The candidate's implementation was not imported. INT-02 learning source,
research archives, existing migrations and dependency locks are unchanged.

Owner identifiers and hashes are audit contracts, not standalone authentication.
Trusted host custody must mint the protected grant and coordinate revocation through
the locking helpers. A provider request already marked dispatched cannot be unsent;
cancellation/recovery records uncertainty. Startup recovery must be quiescent under
the existing kernel lease. Adapters must cooperate with cancellation; database
unavailability and inherited process-containment limits remain.

Only approved finite event context is executable. Memory retrieval, live evidence
qualification, general approval gates, skips, retry/resume, autonomous external tools,
public execution APIs and concurrent runs per instance are unavailable. The bounded
artifact is owner-internal and may contain the approved result; it is not a new public
source repository. Existing raw-versus-parsed Pi receipt proof limitations remain.

No general Bespoke selector, planner, DSL, PI-02C visualizer, feedback loop, automatic
policy promotion or performance advantage is claimed. A future selector can submit
an immutable procedure identity to the same trusted host authorization boundary;
selection itself will not grant execution authority. Stop at draft PR for the
[independent review](ALIVE-PI-02B-REVIEW.md).
