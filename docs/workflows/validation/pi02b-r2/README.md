# PI-02B-R2 evidence inventory

See the [R2 report](../../ALIVE-PI-02B-R2.md) and
[review handoff](../../ALIVE-PI-02B-R2-REVIEW.md). `manifest.json` hashes committed
receipt bytes, not assertions of correctness. Text logs use LF with trailing whitespace
removed; the entire `r1-original` tree preserves original bytes without normalization.

- `r1-original`: unchanged independent report, probes, mutation scripts and observations.
  The scripts contain original output paths and must not be executed unchanged.
- `r1-custody.json`: byte identity with all 52 original evidence files.
- `reproduction-observations`, `reproduction.txt`: selected probes at original b2d06ca
  with only their output location redirected in the scratch pytest plugin.
- `original-mutations.json`: original eleven probes rerun, all unchanged baselines pass
  and all mutants fail relevant assertions.
- `mutations.json`: 20 reviewed mutations plus grant expiry, exact guard replacements,
  passing baselines, 20 relevant assertion kills, one explicit A10/B1 redundancy.
- `focused.txt`, `fence-final.txt`, `provenance.txt`: new regression tests; final fence
  selection additionally asserts the bounded authority category.
- `backend.txt`: full Windows backend log. A late uncited-claim test and B4 fixture
  adjustment are covered by the final focused selection separately.
- `api-migrations.txt`, `postgresql-migrations.txt`: baseline API/FK/import guard and
  schema cycles; no migration source changed.
- `sqlite.json`, `postgresql.json`, `docker-postgresql.json`: real pinned Pi with a
  scripted provider, two graphs, actual receipt/usage linkage, no paid inference or
  learning writes. PostgreSQL additionally runs independent child-process lease probes.
- `image-parity.json`: final image bytes equal LF Git blobs; working-tree bytes and LF
  hashes are separate fields. R1's older CRLF-based receipt remains unchanged.
- `container-replay.json`: actual final-image restart and three replays, six response
  bodies unchanged and no additional effect/artifact/learning records.
- `docker-build-lf.txt`, `docker-smoke.txt`, `docker-e2e.txt`: corrected final image,
  smoke and API E2E checks. The initial startup transport failure is retained separately.
- `linux.txt`: initial image selected regression result, same normalized source;
  `linux-lf.txt` covers final LF image with R2 and transaction tests.
- `initial-*`: disclosed test harness/import/startup failures, not qualification passes.

`container_check.py` is a qualification-only replay utility for the task-owned named
containers, port 18049 and `.r2-docker-workflows-lf.log` (copy `docker-postgresql.json`
there if reconstructing). It requires `ALIVE_API_TOKEN` via environment. It only
restarts and reads; it never starts a workflow. The containers are stopped at handoff.

Remote CI on the final pushed SHA is separate from these local receipts. Independent
R2 approval remains pending. No semantic truth, policy improvement, general browser
qualification, distributed worker safety or model-quality advantage is claimed.
