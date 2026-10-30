# Integrated R2 receipts

Runtime source: `580f11d7e87abf35f10a8e19283f267cfea93265`, incorporating main
`4088671ece35566c21056199042189405ccc78b0`. See the
[integration report](../../ALIVE-PI-02B-R2-INTEGRATION.md) for commands, failure
reproduction and qualification limits. Later documentation and CI duration-output
changes do not alter runtime behavior or test selection.

- `backend.txt`: full integrated Windows run, 1,205 passed, 12 skipped, one xfailed.
- `isolated-reproduction.txt` / `isolated-qualified.txt`: missing opt-in model-table
  reproduction, followed by notebook/ARCH-01/R2 tests after correcting fixture order.
- `linux-core.txt`: 44 tests in the integrated production image.
- `original-mutations.json` / `mutations.json`: eleven original kills and the reviewed
  set plus expiry (20 kills, one redundant); every unchanged baseline passes.
- `docker-postgresql.json`: actual pinned Pi, scripted HTTP provider, two graphs,
  independent-process lease exclusion/handover and no paid inference/learning delta.
- `container-replay.json`: actual restart, six unchanged response bodies and zero new
  effect/artifact/learning records over three replays.
- `image-parity.json`: exact LF Git blob/image byte hashes; raw working-tree hashes
  are separate. `docker-build.txt`, `docker-smoke.txt` and `docker-e2e.txt` qualify
  that same image, not the earlier pre-ARCH-01 image.
- `quick-receipt.json` / `quick.txt`: documentation-only QUICK delta, 17 tests in
  0.69 seconds and 2.6 seconds total runner elapsed. Not a release qualification.
- `ci.json`: observed remote source-CI status, separate from local results and from
  subsequent documentation-head CI. Original failed run 41137656733 remains visible.

Text logs normalize LF/trailing whitespace. The separate original R1 audit copies
and initial R2 manifests remain unchanged. `manifest.json` hashes these receipt bytes
and is an integrity inventory, not an independent review approval.

The replay utility requires the task-owned containers, the qualification token via
environment and `.r2-integrated-docker.log` (copy `docker-postgresql.json` there to
reconstruct). Those containers were stopped; unrelated services were preserved.
