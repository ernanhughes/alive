# PI-02B-R2 qualification after ARCH-01 integration

This supplements the [initial R2 report](ALIVE-PI-02B-R2.md), not an independent
approval. PR #69 remains draft and unmerged; PI-02C implementation remains gated.

Initial R2 review head: `99f54a7c61da0a491e229349c12747090d0c2873`.
Integrated main: `4088671ece35566c21056199042189405ccc78b0` (ARCH-01).
Main-into-PR merge: `dc9d2eb` (no merge of #69 into main).
Integrated implementation: `580f11d7e87abf35f10a8e19283f267cfea93265`.
Later receipt/documentation and CI timing-output changes do not change application behavior; the exact
delivery head is recorded in the PR body. Date: 2026-10-30.

## Why additional qualification was required

The initial local R2 qualification tested the exact reviewed branch, before the
concurrent ARCH-01 changes on main. GitHub run
[41137656733](https://github.com/ernanhughes/alive/actions/runs/41137656733) tested
the automatic combined tree and exposed two integration issues:

- Formatter checks required two formatting-only adjustments in ARCH-01's
  `alive/living.py` and `tests/test_arch_boundaries.py`.
- The isolated notebook test job failed with a missing `experiment_runs` table.
  ARCH-01 intentionally makes experiment models/services opt-in. The shared opt-in
  fixture created its schema before constructing that opt-in app, so the relevant
  models were not yet registered. Full-suite collection imported those models
  elsewhere, masking the isolated-suite failure.

The notebook defect was reproduced locally: 29 passed, one skipped, one xfailed,
one setup error. The fixture now constructs the explicit opt-in app first, then
creates its schema, then opens TestClient. The default production app still excludes
the experiment service/router. The production initialize/close guards were intact;
no guard repair or new production behavior was needed. No tests were weakened,
skipped or broadened to hide the error.

Main was merged into this task-owned PR branch to test the actual integration;
existing owner/other worktrees were preserved. Only the fixture ordering and two
formatting changes were added beyond the main integration. R2's runner, provenance,
artifact/validation/error logic and authority invariants are unchanged from the
initial R2 implementation. ARCH-01's governance extraction is inherited from main,
not a second workflow Governor or provider client introduced here.

## Integrated qualification

| Check | Result |
| --- | --- |
| Notebook + architecture-boundary + four R2 suites | 72 passed, one skipped, one xfailed, 46 warnings |
| Full Windows backend, integrated source | 1,205 passed, 12 skipped, one xfailed, 947 warnings; 1,006.32 seconds |
| Integrated Linux image, R2/transactions/architecture | 44 passed |
| Original 11 mutation probes after integration | 11 baselines pass, 11 assertion kills |
| Reviewed 20 plus grant-expiry mutation after integration | 21 baselines pass, 20 assertion kills, A10 redundant with B1 |
| New LF Docker image build | PASS |
| Actual pinned Pi/scripted provider + two different workflows + PostgreSQL | PASS, one provider request, zero learning delta |
| Genuine process lease exclusion and successor replay inside Docker | PASS; no lease bypass or distributed stage-race claim |
| Docker smoke / API E2E / process restart | 8 checks / 6 groups / 6 unchanged response bodies and zero new effects |
| Exact LF Git-blob/image parity | PASS, every changed production/migration source file |
| Ruff application/test/script check and formatting | PASS, 300 files including qualification utility |
| Remote CI on integrated source | Ubuntu full backend: 1,205 passed, 12 skipped, one xfailed in 511.09 seconds; dashboard, notebook and PostgreSQL PASS; Windows job in progress at last check |

Image: `sha256:0d1d7be0f6db89ebbefb4bf740d17e2b9092a5a7631dd7e740908352d1d1d880`.
Build context was exported with `git -c core.autocrlf=false archive` from the exact
integrated source. The parity receipt distinguishes raw working-tree bytes from
Git blobs and LF-normalized bytes, rather than silently normalizing a claim of
byte identity. PostgreSQL is the same task-owned disposable service, with a new
isolated database for the integrated demonstration.

An initial attempt to include notebook-history tests in the slim production image
was stopped: that image deliberately has neither Git nor repository history. It
was not counted as a pass or used to weaken those tests. The corrected container
selection tests runtime/architecture boundaries; the notebook suite is tested in
the actual repository and GitHub's full-history notebook job.

All original R1 audit files and initial R2 receipts remain unchanged. Integrated
receipts are retained separately under
[validation/pi02b-r2-integration](validation/pi02b-r2-integration), with their own
integrity manifest. Earlier counts in the initial R2 report remain measurements of
their original source snapshot, not claims about this later combined tree.

## Developer feedback loop

The existing [test strategy](../testing/ALIVE-TEST-STRATEGY.md) already separates
QUICK, AFFECTED, FULL and DOCKER. Routine iteration should use that selector, not
repeated full-suite runs. No second runner, weaker assertions or new test-skipping
policy was added here. For the documentation-only delta after implementation,
`python scripts/test_run.py --mode quick --base HEAD --explain` selected two files:
17 tests passed in 0.69 seconds, 2.6 seconds total runner elapsed. This is a selective
smoke result, not workflow or release qualification.

Use QUICK for ordinary edits and targeted workflow suites/AFFECTED for a completed
slice. Keep the authoritative release gate as `uv run pytest -q`, as CI does, so
pytest discovers both configured test roots. The older selector indexes top-level
`tests/test_*.py` and predates the packaged `alive/intelligence/tests` root; its
explicit FULL file list must not replace configured full discovery. That selector
limitation was not hidden by the quick smoke result or changed in this bounded R2.
AFFECTED intentionally broadens to its FULL selection
for core fixture/app/CI changes; explain that expansion rather than hiding its cost.
The older committed test profile attributes recurring cost to per-test SQLite schema
setup and many timeout/recovery/protocol tests. Its timings predate the enlarged
suite and are not a fresh per-test profile. On a future necessary full run, collect
durations within that run; do not start a second full run just to measure it. The
current full run was retained, not restarted, when this latency concern was raised.
The CI full-suite command now prints its 25 slowest tests automatically using
`--durations=25 --durations-min=0.5`; this adds timing output without changing which
tests execute. No extra full run is started solely to obtain timing data.

## Review and milestone gate

Use this integrated source and the final PR head for the next independent review.
Recheck the parent-state artifact cases, explicit browser provenance, actual egress
bindings, cancellation/recovery and F-002 settlement. The reviewer's controlled
mutations remain static audit data; the replay harness only reads their descriptions
and mutates its own temporary source copy.

No paid inference, new execution authority, automatic resume, semantic truth,
independent feedback, policy promotion or Bespoke routing was added. Unknown cost
remains null. No implementation of PI-02C is present: its supplied section 2 requires
independent R2 approval and merge first. Architecture/API preparation is separate,
with actual dashboard baseline evidence; green tests alone do not open that gate.
