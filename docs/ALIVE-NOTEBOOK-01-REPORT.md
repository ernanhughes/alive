# ALIVE-NOTEBOOK-01 — native acceptance report

## Delivery

- Repository: `C:\Projects\alive-worktrees\alive-notebook-01`
- Branch: `codex/alive-notebook-01`
- Base: `933c639d778416b43cb5bd9d050520a2ab8cbc31`
- Implementation commit: `a3fba87f41118d451e4bfae4dc8d98076f126573`
- Draft PR: opened from `codex/alive-notebook-01` against `main`
- Environment: Windows 11, Chrome `156.0.8078.73`, Hugo `v0.165.0`, Python `3.13.3`
- Spend: USD 0.00; no Meta or other external provider was configured or called.

This report qualifies the existing uncommitted ALIVE-NOTEBOOK-01 implementation. It does
not recreate the site or its provenance checker. Canonical `docs/`, `archives/`, the
Governor, approval logic and frozen experiments were not modified. The native harness
records the base commit `933c639` and the uncommitted implementation status at the start
of its run; the implementation was then committed as `a3fba87`.

Evidence: [`python.txt`](validation/alive-notebook-01/python.txt),
[`node.txt`](validation/alive-notebook-01/node.txt),
[`lint.txt`](validation/alive-notebook-01/lint.txt),
[`hugo.txt`](validation/alive-notebook-01/hugo.txt),
[`archive-protocol.txt`](validation/alive-notebook-01/archive-protocol.txt),
[`native/result.json`](validation/alive-notebook-01/native/result.json) and the nine
native screenshots.

## What was reviewed

The uncommitted change adds:

- five Hugo chapters generated verbatim from selected `docs/` sections;
- a deterministic converter and provenance checker (`site/notebook.py`);
- exact notebook URL allowlists in `alive/web_experience.py` and `extension/config.js`;
- tests for provenance, authorisation, retrieval, relationships and capture;
- a native acceptance harness (`scripts/native_notebook_01.py`).

One product integration defect was found and corrected during acceptance: after the live
companion saved a reviewed chapter, the legacy “Find related research” control stayed
disabled because only the legacy send path enabled it. The live companion now enables it
after a successful capture, with a permanent Node regression.

## Native journey

Real Hugo server on `http://127.0.0.1:1313`, isolated SQLite backend, actual unpacked
extension, docked Chrome side panel at 360 px. Screenshots and the full JSON record are in
[`docs/validation/alive-notebook-01/native/`](validation/alive-notebook-01/native/result.json).

| Step | Observed |
|---|---|
| Capture chapter | 1,029 visible characters; navigation, contents and footer excluded |
| Captured hash | `d6d5418b619dec03773136d0bdc3ec55d69e8fd3b26063609256d35b1fe8c300`, matching the saved memory |
| Memories saved | ALIVE-12, ALIVE-11 and ALIVE-14; exact anchors and source hashes recorded |
| R1 retrieval | ALIVE-12 recalled at **rank 1** from the ALIVE-13 “What was wrong” chapter |
| R1 connection | `topic_overlap_candidate`; shared terms include `same_concept`; both quotes exact; explanation says it does not establish agreement, support, contradiction or corroboration |
| R2 retrieval | ALIVE-12 at **rank 2**; ALIVE-14 is rank 1. The measured limitation is recorded, not optimized |
| R3 retrieval | ALIVE-11 at **rank 2** from ALIVE-14 |
| R3 connection | `topic_overlap_candidate` with `paid` and `calls`; no abstention; the strict expected-failure test remains |
| Withdrawal | ALIVE-12 withdrawn; absent from the next retrieval |
| Backend restart | Withdrawn memory still absent; the other memory remains retrievable |
| Revocation | Grant status `revoked`; session capture/selection cleared; a further review is refused |
| Database audit | 0 notes, 0 relationship attempts, 3 memories (2 active, 1 withdrawn), 2 connections |

The three relationship readings in `site/notebook/relations.json` remain **human readings
of verified quotes**, not ALIVE findings. ALIVE's deterministic layer produced lexical
candidates only. No semantic supersession or validity judgement is claimed.

## Engineering results

- Affected Python modules (`test_notebook_01.py`, `test_demo_live_01.py`,
  `test_demo_live_01_r1.py`): **29 passed, 1 skipped, 1 xfailed**.
- Five existing extension Node suites plus the notebook capture suite: **38 passed, 0 failed**.
- Full Python suite: **397 passed, 7 skipped, 1 xfailed** in 329.34s.
- Scoped Ruff check and format: **PASS**; 168 files already formatted.
- Hugo build and `site/notebook.py check --public site/public`: **PASS** (`provenance OK`).
- Six ALIVE-14 archive verifiers and three protocol verifiers: **PASS**.
- Protected-path check: archives, experiment/living/approval logic and migrations unchanged.
- Real Chrome native run: **PASS**; docked side-panel target, 360 px, zero external calls.

## Security and provenance checks

- The notebook allowlist is exact: five chapters × `127.0.0.1`/`localhost` on port 1313.
  There is no wildcard entry. Unlisted paths, wrong ports and bare-origin URLs are refused
  by the existing grant endpoint.
- `extension/manifest.json` is unchanged: no persistent 1313 host permission and no
  wildcard were added to the shipped extension.
- Automatic model submission is not reachable from the notebook: `autoSend` is limited to
  the local demo pages, the notebook is not a local demo, Meta is disabled, and the
  database audit records zero notes and zero relationship analyses.
- Capture and retrieval still require an explicit owner grant; withdrawal and revocation
  were exercised natively and persisted across restart.
- The native harness adds a **test-copy only** `http://127.0.0.1:1313/*` host permission
  because CDP `Extensions.triggerAction` opens the panel but does not grant `activeTab`.
  A real toolbar click grants `activeTab`; the shipped manifest is untouched. This is a
  harness limitation, not a product permission change.
- No symlinked or shared site dependencies. The site is static; the Node capture test uses
  the existing `dashboard/node_modules/jsdom`, and the native harness uses the project
  virtual environment.

## Fixes made during acceptance

1. `extension/live-companion.js`: enable `#find-research` after a successful
   `#live-authorise` or `#live-review`; permanent Node regression added.
2. `scripts/native_notebook_01.py`: new committed native harness with isolated Hugo,
   backend, extension and database; reuses the supported CDP/Playwright panel helpers.
3. Documentation: `site/README.md` now records the native qualification and removes the
   stale “native Chrome deferred” claim.

No changes were made to the Task B fixture, oracle, scorer, canonical docs or archives.

## Remaining limitations

- The demonstration is deterministic and lexical. R1/R2 are human readings; R3 remains a
  candidate for the next evidence-qualification milestone. No semantic validity judgement
  exists.
- R2's rank-2 result is a measured limitation, not tuned for this demonstration.
- One native run on Windows Chrome 156 is one observation; it is not a statistical claim.
- Linux, other Chrome versions and hosted CI were not run.
- The harness-only host permission means native `activeTab` grant behaviour is inferred,
  not directly exercised by CDP.

## Reproduction

```powershell
uv sync --locked
uv run pytest -q tests/test_notebook_01.py tests/test_demo_live_01.py tests/test_demo_live_01_r1.py
node --test tests/extension-background.test.cjs tests/extension-panel.test.cjs `
  tests/extension-capture.test.cjs tests/extension-live-background.test.cjs `
  tests/extension-live-companion.test.cjs tests/notebook-capture.test.cjs
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
hugo --source site
uv run python site/notebook.py check --public site/public
uv run python -m scripts.native_notebook_01
```

## Recommendation

**READY FOR REVIEW** once the full Python result above is green and the draft PR is opened.
Do not merge without independent review.
