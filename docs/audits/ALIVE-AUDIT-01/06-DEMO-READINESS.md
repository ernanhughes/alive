# ALIVE-AUDIT-01 — Demo readiness

## Result by pinned revision

| Candidate | Result |
|---|---|
| Main `1b6da07b856e497b3a44a9e1b9794e94adff55ab` | **NOT READY**: authentication/recovery defects plus shipped Docker demo configuration mismatch |
| PR54 `7bff18aab6db50e6b62a1c36529042d877af647f` | Tested fixture demo works through real Chrome, but inherits baseline authentication/recovery defects; **not release-qualified** |
| PR55 `b0a77c11aeb94f8ca16072ee07c69323f570021a` | Gateway suite and independent focused probes pass; not a combined Docker/demo release candidate |

PR54 and PR55 were checked independently. They were not merged together, and no combined release candidate was tested or implicitly approved.

## Installation and isolation

The audit branch and detached PR worktrees use committed source with no copied owner `.env`. `uv sync --locked` created a new Python environment; `npm ci` installed dashboard dependencies; production dashboard build passed. This is a clean tracked-source **worktree installation**, not a literal independent Git clone or an empty-machine installation. Shared package/Docker caches existed. A fresh-volume PostgreSQL stack tests initialization state, not repeatability of all upstream base-image tags across dates.

Docker29.8.0 was available. Main image built successfully from pinned source. Base images/uv tags are floating, so byte-identical future image reproducibility is not established even with `uv.lock` and package-lock. Audit-created Docker projects use only fake local tokens and blank provider credentials. Owner stacks were left alone.

Main's normal port8080 was already occupied by an unrelated existing stack. `compose.audit.yaml` uses Docker Compose's explicit port override to expose main on18081, with no change to production compose or application files. PR54 was run with its shipped default port8000. This distinction matters: main's port mismatch is source-verified, and its disabled fixture path was independently reproduced despite the audit transport override.

## Executed checks

| Check | Main | PR54 | Evidence / interpretation |
|---|---|---|---|
| Locked Python install / fresh tracked checkout | PASS | Shared audit interpreter for host tests | Host environment cache used |
| Docker image build | PASS | PASS | [Main build](receipts/docker-main-build.txt), [PR54 build/start](receipts/docker-pr54-up.txt) |
| Fresh PostgreSQL volumes and migrations/readiness | PASS | PASS | [Main start](receipts/docker-main-up.txt), PR54 start receipt |
| Built dashboard and fixture mirrors served | PASS | PASS | Main smoke/API E2E, PR54 browser navigation |
| API auth negative / goal/memory/mock-agent/events smoke | PASS with explicit fake token | Exercised by lifecycle/browser | [Main smoke](receipts/docker-main-smoke.txt); printed8 check groups include multiple subchecks |
| HTTP E2E groups | 6 groups PASS | Lifecycle separately | [Main E2E](receipts/docker-main-e2e.txt) |
| Full claim demo on main configuration | **FAIL**, fixture preview403 | PASS | [Main negative](receipts/main-lifecycle-negative.txt), [PR54 lifecycle](receipts/pr54-lifecycle.txt) |
| Real Chrome + unchanged unpacked extension + docked side panel | Default main configuration blocked; no misleading main pass claimed | **PASS** | [Browser report](receipts/chrome-docker.json), [log](receipts/chrome-docker.txt) |
| Real DOM capture-v2 and selected reliance sentence persisted | Not qualified | PASS | Native flow sends actual rendered capture through extension and API |
| Changed recommendation while behavior sentence retained | Not qualified | PASS | One candidate, exact deprecation quote, fixture provider identity checked |
| Withdrawal removes finding from API and panel | Not qualified | PASS | Native flow asserts no active connection |
| App/container restart preserves retired state | Not qualified | PASS | Docker app restarted while same isolated browser profile/panel remained |
| No-change mirror honest abstention | Not qualified | PASS | Native flow asserts insufficient_evidence and no connection |
| Demo off refuses fixture provider | Not qualified | **PASS**, HTTP403 | [Demo-off receipt](receipts/pr54-demo-off.txt) |
| Database failure and recovery | Not executed separately | **PASS** | Stop only audit DB → health degraded, secured API503; restore DB + restart app → health ok. [Receipt](receipts/dependency-failure.json) |
| Real Meta reasoning / paid inference | **NOT EXECUTED** | **NOT EXECUTED** | Prohibited by audit; browser flow is deterministic local fixture |
| Combined PR54+55 + future fixes release qualification | **NOT EXECUTED** | **NOT EXECUTED** | Requires separately pinned candidate after corrections |
| Full dashboard Playwright suite / native Pi / clean empty-machine clone | **NOT EXECUTED** | **NOT EXECUTED** | Consequential scope limits remain |

## Native browser evidence

Chrome **156.0.8078.73**, isolated persistent profile. The browser CDP reports a native side-panel target and `panel_opened_as_ordinary_tab: false`. The extension loaded directly from PR54's unchanged `extension/`; per-file hashes are in the report. No rewritten backend/host-permission config, frontend mock state, or extension-tab substitute was used. Existing repository CDP test helpers drove the explicit UI controls; the application read the real rendered DOM and persisted through the actual container API to PostgreSQL.

The independently written harness is [chrome_docker.py](chrome_docker.py). It checks candidate identity/retained quote, withdraws the source, restarts the Docker app and verifies continued absence, then exercises the no-change pair in a new goal. This establishes the specific user-facing fixture lifecycle. It does not establish arbitrary model reasoning, all dashboard behavior or all failure/concurrency cases.

[Changed recommendation screenshot](receipts/chrome-change.png) · [Abstention screenshot](receipts/chrome-abstention.png). The changed-state screenshot was visually inspected for the local-fixture labels and retained behavior/deprecation distinction.

## CI failure diagnosis

The supplied CI run is genuinely red on pinned main: the Ubuntu provider-timeout test sees a terminal investigation with a reserved invocation. It is **not independently justified to call that unrelated test noise**. The main full suite passes locally, but an independent deterministic transaction-exit cancellation probe reproduces that invariant failure. See F-002. Historical Windows CI was cancelled after the Linux failure. Passing dashboard/notebook/PostgreSQL jobs do not override the backend failure.

## Cleanup and retained state

Audit-owned containers/networks are taken down after collecting evidence; audit named volumes are retained, not deleted, for review. Detached worktrees and the audit branch remain available. The isolated browser context is closed. No existing owner container, profile, token, database or uncommitted work was changed. [Resource-closeout receipt](receipts/resources-closeout.txt) records the resulting audit and existing Docker state.
