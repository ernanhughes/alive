# ALIVE-AUDIT-01 — Executive verdict

**NOT READY.** Current main is pinned to `1b6da07b856e497b3a44a9e1b9794e94adff55ab`. Release-blocking defects are confirmed, and the requested exhaustive full-system semantic assurance is not complete.

## What determines this verdict

1. **P0: authentication can fail open.** With an empty persisted `.alive/token` file and no configured token, missing credentials authorize a protected read, creation of a goal, and WebSocket event history. All were reproduced against temporary data. No owner token was accessed and no real credential leaked. This is a conditional local-runtime failure, not proof of a remote compromise. It requires correction before release.
2. **P1: cancellation leaves incorrect durable invocation status.** A deadline during exit from a committed reservation produces a failed investigation whose invocation remains reserved. The independent controlled probe establishes the gap; the exact pinned Ubuntu CI run independently failed the same expected-versus-observed invariant. Local success of the original timing test does not exonerate it. Conservative charges remain; no unauthorized paid call was demonstrated.
3. **P1: current main's default Docker evidence-lifecycle demo is broken.** The shipped extension expects8000 while main publishes8080, and the local claim fixture provider is disabled. Main's lifecycle preview was independently observed to return403. Draft PR54 addresses this, but it is not main and is not release-qualified by itself.

Additional confirmed issues: incomplete provider-envelope handling, an import-alias bypass in the test ratchet, gateway/request operation mismatch acceptance, and silent replacement of an explicit zero output cap. See [severity-ranked findings](02-FINDINGS.md) for scope, lines, reproduction and minimal corrections. There are **seven finding groups**, supported by eight failing independent test cases plus the Docker reproduction.

## What passed

* Main backend: **619 passed, 7 skipped, 1 xfailed**. The independent audit suite: **12 passed, 8 failed** across20 cases. Passing the baseline plainly did not prove the system correct.
* Dashboard:7 tests and production build. Extension/notebook:38 Node tests. Lint/format pass. Six frozen archive manifests and three protocol verifiers pass; frozen material unchanged.
* Main Docker build, fresh-volume PostgreSQL migrations/readiness, eight printed smoke groups and six API E2E groups pass. The complete claim demo is a different path and fails on main.
* **PR54 real Chrome156 docked side panel with the unchanged unpacked extension passed:** actual DOM capture and anchoring, changed recommendation while behavior remains, source withdrawal, container restart without resurrection, and no-change abstention. Demo-off refuses the fixture provider with403. Audit DB interruption degrades readiness/secured API correctly and recovery after restart succeeds.
* PR55's32 gateway tests and three independent scanner/operation probes pass on its exact pinned head. It is a promising specific correction, not an approved merge or a test of a combined release candidate.
* Two targeted in-memory mutations removing real reference/hash protections were caught by their existing tests, with unmodified controls passing.

## What remains unknown

The inventory covers1,409 tracked files and210 Python modules structurally. Detailed semantic review and selected critical-path review are explicitly distinguished in [coverage.csv](coverage.csv); not every production module, test body or operational script received complete semantic examination. Exhaustive mutation coverage, a literal clean-clone/empty-machine installation, full dashboard Playwright suite, real Pi execution, live Meta reasoning, arbitrary-source semantics and all concurrent crash/settlement windows were not established. PR54 and PR55 were not combined or merged. No assertion of no further P0/P1 defects is justified.

The contributor's dropped-tool-parameter allegation remains externally unverified. ALIVE's nested sentinel data survived the tested transport. The matching `walk(tree, None)` in ALIVE belongs to a model-construction scanner and is correctly inside its file loop; an independent multi-file test confirms all-file traversal. No source for the alleged credential-scanner defect was found, so its ownership and impact remain unknown. The scanner does have a different alias-handling defect on main.

## Recommendation

Proceed with **controlled remediation and independent verification**, starting with persisted-token authentication and durable cancellation settlement. Keep release/demo-readiness claims and nonessential feature development on hold. Review PR54/55 independently, then qualify a pinned combined candidate only after blockers are corrected. Complete the outstanding full-system source/test review and commission separate external tool-interface and evaluation/scientific-method review where evidence is still missing.

No P0/P1 issue is accepted as release risk. No production changes, merges, remote comments, real-model inference, or paid operations were performed. The original checkout's uncommitted work is preserved. Reports, reproducible audit probes and receipts are retained on local branch `codex/alive-audit-01` in the isolated audit worktree.
