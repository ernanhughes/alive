# PI-02B retained qualification receipts

See the [report](../../ALIVE-PI-02B-REPORT.md) for scope, commands and failure history.
`manifest.json` hashes this receipt set; it is an integrity inventory, not a signature.
Saved text logs use normalized LF endings and omit trailing whitespace/blank lines.

| Receipt | Meaning |
| --- | --- |
| `sqlite.json`, `postgresql.json`, `docker-postgresql.json` | Genuine pinned Pi + local scripted HTTP provider, different four/three-stage workflows, exact receipt linkage and replay |
| `container-replay.json` | Actual Docker restart, identical response bodies and unchanged effect/learning counts |
| `image-parity.json` | Changed production source hashes equal tested Docker image files |
| `postgresql-migration.json` | Fresh isolated PostgreSQL upgrade/downgrade/upgrade observation |
| `mutations.json` | Eleven unchanged baselines and eleven assertion kills, including actual Pi dispatch revocation |
| `baseline.txt`, `focused.txt`, `pi-regressions.txt` | Baseline and focused Windows pytest outcomes with retained warnings |
| `backend.txt`, `transactions.txt` | Full Windows suite and two separately collected late transaction tests |
| `linux-initial.txt`, `linux-supplement.txt` | Initial Linux run including two missing-script-mount failures, followed by corrected-mount reruns and transaction tests |
| `dashboard-*`, `extension.txt` | Dashboard unit/build and five extension Node test files |
| `docker-build.txt`, `docker-smoke.txt`, `docker-e2e.txt` | Final production image, eight smoke checks and six API groups |
| `archives.txt` | Original frozen archive manifest verification |

The Python replay utility is qualification-only. It requires the task-owned Docker
containers and `ALIVE_API_TOKEN`, plus the original `.pi02b-docker-workflows.log` (or
copy `docker-postgresql.json` there). It only restarts the app and reads retained data.
Task-owned containers were stopped after qualification; unrelated containers remain.

JSON results use scripted public test inputs and fake provider credentials; no paid
provider was called. Artifact assessments are structural/reference validation, not
semantic truth or independent feedback. These are local results; remote CI and an
independent reviewer are separate checks.
