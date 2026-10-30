# ALIVE-INT-02 durable integration delivery

30 October 2026, Europe/London. This report covers the selected **second brief**.
The package-only inquiry brief was not implemented alongside this milestone.

## A. Baseline and provenance

Fetched `origin/main`: `07c0c0663b8e5b1b0b77ec7ed9bde0920805bcfa`.
GitHub metadata independently confirms PRs #66 and #67 merged, with merge commits
`2d82e7eb3b9308bae961a287a9c5f0dcd67880f7` and the baseline above respectively.
PI-02B is absent. No general workflow executor is introduced.

01 candidate: `3b7f6917c08d02bccd0cfca5e1d2d69547b69d1b`, clean original worktree.
The already ported 01 commits `72d9cb8b48f9917f1235cf72e79eeabe3ed12250` and
`a2b20a3713458862bd6efd4f5305d7372188c86c` were reviewed and cherry-picked onto
the freshly created branch `codex/alive-int-02-delivery`, worktree
`C:/Projects/alive-int-02-delivery`. The new local cherry-pick SHAs are `be914a8`
and `767e81d`. Original main and 01 worktrees remain clean.

An existing `C:/Projects/alive-int-02` worktree held substantial uncommitted
integration work. It was inspected and a selected source/test snapshot reused in
this new worktree. It was never edited, reset, stashed or committed by this run.
Its reports were not copied as independent verification. This delivery adds review
corrections and new qualification evidence to that implementation, rather than
claiming all its code was newly authored here.

Implementation commit: `a56dfe4c5c9ddab87cd96c88d88e9c2b20fb25d3`.
The final documentation commit cannot contain its own SHA;
the PR head and `git rev-parse HEAD` give the exact final head.

## B. Review findings

See `REVIEW-01.md` for independently reproduced 01 results and concrete findings.
01 conflicting replay was mislabeled duplicate; canonical outcome hashes now
reject it without changing the algorithm or permitting a second update. Review of
the integration snapshot also led to workflow revalidation before feedback,
conflicting-measurement rejection, strict receipt usage/settlement agreement and
a unique identity-only measurement-consumption ledger. Cancellation and transaction
failure leave no partial learning, feedback, consumption or success audit event.

## C. Implementation

Five tables in migration `0009` follow verified head `0008`: states, immutable
episodes, immutable feedback, immutable learning updates and measurement-consumption
identities. Proposal, frozen decision and revisit linkage share an immutable episode
snapshot. There is no second source-content store. Existing events retain custody
and audit; existing sessions provide the atomic transaction.

`store.py` provides trusted fixture-only state creation, assessment recording,
feedback acceptance, quarantine and read/replay. `fixture.py` supplies the explicit
synthetic demonstration. `receipts.py` inspects existing Pi/invocation records
without dispatch. `api.py` adds authenticated, typed GET access to states/chains
and episodes. `alive/app.py` registers that router. The isolated package-root import
still constructs no provider, database or Pi process.

`pyproject.toml` includes isolated tests in the default suite. The migration test
head advances to `0009`. The existing PostgreSQL CI job runs the explicit Intelligence
harness after workflow qualification. No dependency/lockfile, provider, Pi runtime,
Governor, living algorithm, research artifact or workflow executor was changed.
`changed-paths.txt` gives the exact delivery diff against baseline.

## D. Durable lifecycle

The committed `process-postgresql.json` contains the actual independently controlled
fixture trace and opaque record IDs. Episode one proposes and the frozen active
policy selects `monitor`; no ALIVE action is authorized or executed. A separate
fixture observer event binds its exact decision snapshot and reward `-0.5`.
Candidate monitor samples become one in exactly one atomic learning update.
Episode two proposes `retrieve`, links to episode one and preserves the frozen
`monitor` selection. Its outcome remains unknown. Both real workflow stages stay
PENDING; synthetic reasoning is not relabeled as Pi execution.

The PostgreSQL harness races four independently locked workers: one accepted,
three duplicates, one durable update. It closes and restarts ALIVE, then launches
a separate interpreter to reload the exact chain and hash all five durable tables.
The observed durable identity is recorded in the trace, not claimed as a truth proof.

The final Docker app reloads the same chain over authenticated HTTP before and
after a real container process restart. Three repeated GETs return the same chain.
Across that restart/replay the dedicated database remains at two feedback rows,
two updates and two consumed measurements (the second pair belongs to the separate
concurrency trial), with **zero model invocations and zero Pi runs**.

## E. Security and authority

Only trusted internal code can write fixture custody. The public browser observation
schema cannot choose its reserved event source/type. Model text cannot certify
feedback. Exact payload, decision, episode, goal, origin, split, timestamps,
measurement identity and workflow references must match. Database uniqueness and
revision/hash CAS protect replay and independent worker races. Corrected/revoked
feedback quarantines future learning without overwriting historical outcomes.

No model or tool executor is added. Live Intelligence admission is unavailable.
The receipt resolver requires settled upstream records and known, consistent usage;
it does not infer success/cost from process exit. Pi stores a raw response hash and
cognition parsed JSON, so this seam cannot reconstruct original response bytes;
it does not certify semantic entailment or complete byte equality.

## F. Learning

Only the existing deterministic empirical `living_policy` algorithm is reused.
Candidate state changes; active policy remains frozen. Unknown/predicted/simulator/
evaluation outcomes do not train. Model interpretations remain opinions and
simulation shadows cannot promote themselves. No quality, generalization,
predictive superiority or semantic-model improvement is claimed.

## G. Verification

Interpreter: existing `C:/Projects/alive/.venv/Scripts/python.exe`, Python 3.13.3,
Pydantic 2.14.1, pytest 9.1.1 and NumPy 2.5.4. Host Node is 25.8.2;
the Dockerfile pins Node 24.22.2 and Pi 1.4.0 remains lockfile-pinned.
Bytecode disabled. No Python dependency upgrade. Pi and dashboard installs use
their existing npm lockfiles; Linux test-only dev dependencies use `uv sync --locked`.
Native PostgreSQL 18 and Docker PostgreSQL 17 were dedicated disposable databases;
no existing application database was used. Provider credentials were empty or
scripted throwaway values. All provider requests in qualification targeted local
scripted upstreams; no paid inference or real Meta request occurred.

Actual commands and receipts:

| Command / check | Result |
| --- | --- |
| Original clean candidate isolated pytest (`--confcutdir=alive/intelligence/tests`) | 65 passed. |
| Original gateway/learning/living/cognition pytest | 67 passed; 34 existing Windows selector warnings. |
| Original example, Ruff check and format | PASS. |
| Initial reviewed integration snapshot focused pytest | 100 passed. |
| Final isolated + durable + receipt + migration pytest | 111 passed, 46 warnings. |
| Final full Windows backend pytest | 1122 passed, 12 skipped, one xfailed; 870 warnings; 1089.69 seconds. |
| Real pinned Pi `tests/test_pi_real.py` | 10 passed, 10 warnings. |
| `python -B -m scripts.pi_integration` | 13/13 checks, two scripted provider calls, unknown cost preserved. |
| Final `scripts.intelligence_check` on Docker PostgreSQL | PASS, one winner/three duplicates, ALIVE and separate-interpreter restart/replay. |
| Final PostgreSQL upgrade / downgrade 0008 / upgrade / current | PASS; `0009 (head)`, five Intelligence tables. |
| Existing PostgreSQL `scripts.workflows_check` | 14/14 passed, including concurrent registration and restart. |
| Final Docker build and eight-group app smoke | PASS. |
| Container process restart and three HTTP replays | PASS; durable counts unchanged; zero model/Pi records. |
| Linux Intelligence/Pi qualification on final image | 244 passed, one platform-specific skip in 280.83 seconds. |
| Dashboard `npm test`, `npm run build` | 15 tests passed; build passed. |
| Five extension Node test files | 36 passed. |
| Ruff check and format over alive/migrations/scripts/tests | PASS, 272 files formatted. |
| Five test-only mutation probes | Five baselines PASS; all five KILLED; zero survivors. |
| Remote Linux/Windows GitHub CI | Triggered by delivery push; results must be read from PR checks, not inferred from local passes. |

Exact common pytest command: `$py -B -m pytest -q -p no:cacheprovider`.
`COMMANDS.md` records the main baseline, build, fixture, platform and regression
commands. Committed text receipts normalize line endings/trailing whitespace only.
Focused selection adds `alive/intelligence/tests tests/test_intelligence_durable.py
tests/test_intelligence_receipts.py tests/test_intelligence_migration.py`.
Mutation command: `$py -B -m scripts.intelligence_mutations`.
Ruff commands: `$py -B -m ruff check --no-cache alive migrations scripts tests`
and the same paths with `ruff format --no-cache --check`.
Docker build: `docker build -t alive-int02-delivery:qualification .`.
Final image ID: `sha256:4b72e8eac5b9043fe691325b547ce41bb7f886f532c115a3af4cf32f0e347aa6`.
Scripted-provider tests are distinct from live model qualification.

The Linux command installs locked dev dependencies into a throwaway final-image
container, mounts the unchanged test suite and package tests read-only, then runs
isolated/durable/receipt/migration tests and all seven Pi test files. The platform
skip is the Windows-specific process containment case. Local Linux containers are
not a substitute for remote Linux/Windows CI; those results remain separate.
The earlier full backend run completed with 1101 passed, 22 skipped and one xfailed
in 1030.17 seconds. It began before the final corrections and Pi installation;
the final-source full run is reported separately when complete. Its skip count
must not be used to qualify real Pi.
The pinned Pi npm install reported two existing advisories (one moderate, one
high); lockfiles were unchanged and exploitability was not assessed in INT-02.

Recorded failures/corrections: the new conflicting-measurement test initially used
`session.get(Event, event_id)`, but Event's primary key is its sequence number.
The test now selects its unique opaque ID explicitly; it passes. Ruff import/format
issues were corrected. A Linux run was started against the previous image while
the final build was finishing; image IDs exposed the mismatch, so that run was
aborted and excluded, and qualification restarted against the final image. An
automatic policy review blocked a command containing temporary cluster deletion;
the stopped native cluster was instead moved reversibly into ignored `.alive/`.
No original worktree or database was deleted. Historical interrupted/earlier runs
are not represented as final-source passes.

## H. Limits and decision

The live Intelligence-to-Pi reserved invocation and PI-02B executor remain
**BLOCKED BY DEPENDENCY**; fixture fallback is implemented as explicitly allowed.
Live evidence/feedback authority, automatic quarantine rebuild and production action
execution are not implemented. ORM guards and hashes do not defeat privileged
database administrators or arbitrary hostile Python inside the process. Cross-record
source withdrawal races require the trusted host to coordinate its custody writes;
this is not a general distributed evidence-authority protocol.

No paid model call, automatic action, policy promotion or merge occurred. The
isolated engine retains its session-local 256-episode limitations; durable feedback
must use the new transactional store. A fixture proves orchestration and durability,
not model intelligence. Independent reviewer instructions are in `REVIEWER-HANDOFF.md`.

Decision: **GO for independent review of the fixture-backed durable milestone**.
**NOT qualified for live model
admission, autonomous execution or policy promotion.** Stop at draft PR delivery.

## Delivery metadata and final verification

Branch: `codex/alive-int-02-delivery`; worktree `C:/Projects/alive-int-02-delivery`.
Base: `07c0c0663b8e5b1b0b77ec7ed9bde0920805bcfa`.
Implementation: `a56dfe4c5c9ddab87cd96c88d88e9c2b20fb25d3`.
The following documentation-only commit carries these final receipts; its exact
head and the draft PR URL are returned in the final delivery message and PR metadata.

Final full Windows result: **1122 passed, 12 skipped, one expected failure**,
870 warnings, 1089.69 seconds. Warnings include existing Proactor/ZeroMQ selector
fallback and late event-loop callback/unraisable warnings; no test failure was
suppressed. Full output is in `backend-tests.log`. The final-source Linux targeted
Intelligence/Pi suite has **244 passed, one Windows-only skip**. Live external
integrations remain NOT RUN; the separate scripted Pi tests are not paid inference.

All local qualification is complete. Remote CI is triggered on push and must be
checked on the draft PR; it is not claimed passed here. The original main and 01
worktrees remain clean, and the existing dirty integration worktree was left alone.
Only task-owned containers were stopped; they and the final image are retained for
inspection. No merge or subsequent production/live milestone is begun.
