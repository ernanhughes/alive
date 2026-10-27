# ALIVE-10 closeout qualification

Qualified runtime/extension source: `8e1b65ab4ac82c8a1bde5189e936aab145485ca4`, based on PR #14 head `f222a06`.
The review found and corrected an additional stale-response UI race: a delayed
note completion could re-enable feedback after Stop or a changed observation.

137 backend tests, 27 focused companion tests, 7 frontend tests and 5 extension
race tests pass. Ruff check, whole-project Python format check, JavaScript syntax
and production build pass. The full suite was rerun for closeout despite unchanged
backend files. The extension tests execute shipped panel handlers with delayed
Chrome replies; they are not a substitute for a native Chrome test.

A fresh headful Chrome journey used an isolated migrated SQLite database, local
page/provider servers and a temporary unpacked extension. It made five synthetic
provider calls with 750 synthetic tokens, an application price estimate of
$0.0016875, and $0 paid. It used the extension-page fallback: docked side-panel and
Meta qualification remain unclaimed. Restart preserved policy v11 and five notes,
rejected the old grant and replayed no calls. Negative authority checks passed.

All 334 earlier payloads across 15 manifests verified unchanged. The primary
checkout's 25 inventoried changed/untracked files were preserved. Unrelated file
contents, local credentials/profiles and absolute test paths are not exported.
Windows ZeroMQ selector-thread warnings remain in the test transcript.

See docs/ALIVE-10-CLOSEOUT.md for the full review and merge recommendation.
ALIVE-11 is preparation only, subject to ALIVE-10 integration and separate paid
approval. ALIVE-12 is a proposal only. No automatic merge was performed.

Reproduce: `uv run pytest -q`, `node --test tests/extension-panel.test.cjs`,
`npm test --prefix dashboard`, `npm run build --prefix dashboard`,
`uv run ruff check alive migrations scripts tests`,
`uv run ruff format --check alive migrations scripts tests`,
`node --check extension/panel.js`, and `uv run python -m scripts.native10 --headful`.
Do not rerun historical archive builders over frozen evidence.
