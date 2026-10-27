# ALIVE-10 post-review validation

Tested source: `0ca6290873d64c2e2b66d0201229b5936bd7df4a` (based on reviewed PR head `2686a80`).

The two independent-review defects are fixed: old paused snapshots cannot borrow
probe eligibility, and v1 migration preserves effective feedback revision order.
The regression tests cover blocked old snapshots, exactly one probe dispatch,
duplicate dispatch rejection, budget rejection/retry, and revision migration with
and without retained timestamp history. See `docs/ALIVE-10-REFINEMENT.md`.

Validation: 137 backend tests, 7 frontend tests, production build, Ruff check,
format checks for changed Python files, extension JavaScript syntax and a fresh
headful stable Chrome synthetic journey pass. All 326 prior payloads across
14 manifests verified; original archives remain byte-for-byte unchanged.

The isolated native journey on this committed source made five synthetic local
provider calls, 750 synthetic tokens, $0.0016875 model-price estimate and **$0 paid**.
It preserved policy v11 and five notes across restart, revoked the stale grant,
and rejected duplicate analysis, wrong origin, modified hash and budget exhaustion.
The synthetic estimate is not a Meta charge or observed Meta usage.

Chrome used the extension-page fallback. This is not docked side-panel or native
Meta qualification, and does not demonstrate an adaptive research advantage.
Absolute local paths and profile configuration are excluded from the native export.
Existing Windows ZeroMQ selector-thread warnings remain in the backend transcript.

Reproduce with locked dependencies: `uv run pytest -q`, `npm test --prefix dashboard`,
`npm run build --prefix dashboard`, `uv run ruff check alive migrations scripts tests`,
`uv run ruff format --check alive/web_experience.py tests/test_web_policy_recovery.py`,
`node --check extension/background.js`, `node --check extension/panel.js`,
`node --check extension/config.js`, and `uv run python -m scripts.native10 --headful`.
The native harness uses a fresh database, loopback servers and test profile. It does
not use the owner's running backend or invoke Meta. Do not rerun old archive builders
over frozen evidence. This directory is a separate post-review qualification.
