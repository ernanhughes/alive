# ALIVE-NOTEBOOK-01-R1 — integrity and qualification corrections

Recommendation: **READY_FOR_REVIEW**. Hosted CI status is recorded below.
Shipped toolbar acceptance remains **NOT QUALIFIED** under the explicitly permitted
manual-qualification fallback. This is not a release claim for that path.

## Scope and delivery

Base: current `origin/main`, `8737adf1e91d89cc772cd32cd56a8a4fe9370116`, containing
merged PR #40. Branch: `codex/alive-notebook-01-r1-integrity`. Worktree:
`C:\Projects\alive-notebook-01-r1`; the original checkout and its untracked `.vscode/`
were left intact. No ALIVE-NOTEBOOK-02 work was started. No automatic merge is authorized.
Draft correction PR: https://github.com/ernanhughes/alive/pull/41.

## Root causes and corrections

**M1.** The workflow did not build or validate the notebook or run its Node capture suite,
and shallow checkout caused four provenance tests to skip. Backend checkout now fetches
full history. A dedicated notebook job installs Hugo **0.165.0**, verifies the release
archive against the published checksum list, performs a clean production build, runs
`check --public`, notebook Python tests and Node capture tests. Existing jobs are retained.
Provenance tests no longer have shallow-history skip decorators: shallow/missing history
fails. Missing Hugo fails capture validation instead of skipping it.

**M2.** Only selected metadata fields were checked; body/source hashes did not bind the
visible title or other front matter. Generation and validation now share canonical metadata
rules. Every permitted key and value/type must match, including the source heading title,
manifest-selected parts, stage, generator, slug, IDs, commit and both hashes. Unknown keys
are refused. The checker verifies both the built article H1 and document title, allowing
only the template's fixed site-title suffix. A recomputed body hash cannot legitimize a body
that differs from the manifest's canonical slices. LF-normalized generation is unchanged.

Adversarial tests cover the five review attack categories (title, parts, stage, generator,
injected metadata), with both `summary` and `draft` injections, and additionally every
other permitted metadata field, rehashed removal of the ALIVE-12 qualification, rendered
H1/document-title attacks, shallow-history failure and byte-identical repeated generation.

**M3.** The earlier report disclosed only an added host permission. The initial harness
actually replaced all `config.js`: backend defaults became an isolated random port,
`AUTHORISED_PAGES` became the five 127.0.0.1 notebook URLs and `isLocalDemo` always
returned false. It replaced the entire manifest host list with the isolated backend origin
and `http://127.0.0.1:1313/*`, removing shipped localhost and external origins. Backend
`ALIVE_NATIVE_TEST_PAGES` was also set to the five chapter URLs. CDP triggered the
action rather than a physical toolbar click. The preserved harness now records each
substitution, lexical fallback mode and its restricted qualification scope in JSON; an
optional evidence directory preserves original evidence when rerunning it.

A separate native load smoke copies **all shipped extension files byte for byte**, records
their SHA-256 hashes, loads the extension in Chrome, checks its runtime manifest/config
and absence of persistent 1313 access, and loads an actual Hugo chapter. It starts no
backend, touches no database and invokes no provider. It makes no toolbar/capture claim.
The CDP harness does not provide reliable authentic toolbar interaction; it is not used to
fake `activeTab`. Capture, unlisted-URL rejection and revocation using shipped authorization
remain **NOT QUALIFIED** until the manual procedure below is completed.

## Validation evidence

All paths below are relative to `docs/validation/alive-notebook-01-r1/`.

| Check | Result | Evidence |
|---|---|---|
| Targeted Python (notebook + demo/live R1) | 46 passed, 0 failed, 1 skipped, 1 xfailed | `python-targeted.txt` |
| Notebook Python | 30 passed, 0 failed, 1 skipped, 1 xfailed | included in targeted and hosted notebook output |
| Full Python | 414 passed, 0 failed, 7 skipped, 1 xfailed; 419.84s | `python-full.txt` |
| Six Node suites | 38 passed, 0 failed, 0 skipped | `node.txt` |
| Ruff check and format | PASS; 170 files formatted | `lint.txt` |
| Hugo production build / built provenance | PASS; provenance OK | `hugo.txt` |
| Six archive and three protocol verifiers | PASS | `archive-protocol.txt` |
| Protected runtime/authorization/archive paths | unchanged | `protected-paths.txt` |
| Substituted native journey | PASS; 0 external calls, USD 0.00 | `substituted-native/result.json`, nine screenshots, `substituted-native.txt` |
| Byte-identical shipped-extension load smoke | PASS; 0 external calls, USD 0.00 | `shipped-smoke/result.json`, `chapter.png`, `shipped-smoke.txt` |
| Authentic shipped toolbar capture/rejection/revocation | NOT QUALIFIED | manual procedure below |
| Hosted notebook job | SUCCESS: 30 passed, 1 skipped, 1 xfailed; Node 2 passed, 0 skipped | `hosted-notebook.txt` |
| Hosted full workflow (push) | SUCCESS; all five jobs | run 40776438791; `hosted-ci.json` |

The targeted skip is the existing unimplemented semantic validity judgement, not provenance.
The strict R3 xfail remains: terminology overlap cannot establish a meaningful relationship.
Native runs used Windows 11 / Chrome 156.0.8078.73 and Hugo 0.165.0. Their JSON records
the base commit and working state; execution preceded the correction commit.

Hosted push run [40776438791](https://github.com/ernanhughes/alive/actions/runs/40776438791)
concluded **success** on implementation commit `0213deb`: dashboard, Ubuntu backend,
Windows backend, notebook and PostgreSQL first-contact jobs all passed. The Ubuntu
backend result was 414 passed / 7 skipped / 1 xfailed in 275.13s in the parallel PR run;
the Windows push job recorded 414 passed / 7 skipped / 1 xfailed in 429.93s. No failures.
The final evidence commit changes documentation/evidence only; these conclusions identify
the tested implementation commit, not an unobserved subsequent run.

Hosted pull-request run [#234 / 40776465685](https://github.com/ernanhughes/alive/actions/runs/40776465685)
tests implementation commit `0213deb0f8603451386ba62c8cebdd814bf71510` merged with
base `8737adf` (test merge `9c888f4`). The
[notebook job](https://github.com/ernanhughes/alive/actions/runs/40776465685/job/123126970323)
concluded **success**: full-history fetch, checksum-verified Hugo installation, production
build, built provenance, Python and Node capture checks all executed. The sole skipped
Python test is semantic validity judgement; all four formerly skipped provenance tests ran.
The separate PR run was still finishing its Windows backend at the evidence checkpoint;
no conclusion is inferred for an in-progress run.

## Security consequences and limits

No shipped extension configuration, permissions, authorization/backend code or retrieval
code changes. ALIVE-12 memory behavior and the R1/R2/R3 ranks are unchanged. The
substituted harness retains an isolated SQLite database, disabled model keys, unreachable
Meta endpoint and disabled embeddings. Its audit records 0 notes, 0 relationship analyses,
3 memories (2 active, 1 withdrawn) and 2 lexical connections. No paid inference was used.
No Governor, approval, migration, archive or frozen experimental files were changed.

Hashes prove integrity relative to verified inputs, **not semantic accuracy**. The manifest,
canonical sources, generator and templates remain trusted/reviewed inputs. The narrow
rehashed-qualification-removal test protects the currently selected parts; assessing whether
a newly edited manifest omits a critical qualification elsewhere needs human review. No
semantic claim checker or general omitted-section detection was added.

The R4 research fixture `tests/fixtures/notebook-r4.json` preserves valid source/body hashes
with an unsupported visible title and is exercised by the adversarial tests. Rejecting that
known noncanonical mutation does not solve evidence interpretation for unfamiliar documents.
R3 tests relevance/abstention; R4 tests evidence integrity/interpretation. Both remain open
research problems. R1 is a lexical candidate, not proven supersession. R2 compares different
evaluation conditions, not a universal improvement. All ranks used lexical fallback, not
hybrid embeddings. Retrieval was not tuned.

## Manual shipped-configuration qualification

1. Use a disposable Chrome profile and this branch. Confirm `git diff origin/main --
   extension/config.js extension/manifest.json` is empty. Reserve loopback ports 8000 and
   1313; if occupied, stop and identify the owning process instead of reusing its database.
2. Start `hugo server --source site --bind 127.0.0.1 --port 1313 --disableLiveReload`.
   In a separate terminal start `uv run python scripts/demo_live_01.py --port 8000
   --directory .alive/notebook-r1-manual-UNIQUE` with a new directory name. This helper
   creates an isolated SQLite database and token, disables Meta/research/claim providers
   and embeddings, and uses the mock cognitive provider. Do not add backend test pages;
   the shipped notebook allowlist already contains these URLs. Do not configure keys.
3. Load the unmodified `extension/` through Chrome's Load unpacked control. Pin ALIVE to
   the toolbar. Open `http://127.0.0.1:1313/chapters/alive-12-status/` and physically click
   its toolbar icon (no CDP trigger, host-permission edits or DevTools grant). Connect the
   panel to `http://127.0.0.1:8000` using the isolated token and create a research goal.
4. Click Authorise; confirm the preview is the chapter and includes "Retrieval advantage:
   NOT DEMONSTRATED." Confirm capture completes without a persistent 1313 origin grant.
   Save evidence of the URL, preview/hash and grant; token values must stay out of evidence.
5. Navigate to `http://127.0.0.1:1313/` (a real unlisted page), physically click the toolbar
   icon and attempt Authorise. Confirm refusal and no new grant/snapshot. Also check
   `/chapters/not-a-chapter/` if desired; a 404 must not grant authorization.
6. Return to the listed chapter, physically click the toolbar and re-authorise if necessary.
   Revoke in the panel; confirm its grant is `revoked` in the isolated DB, session capture
   and selection are cleared and Review refuses further capture until new explicit consent.
7. Record Chrome/OS/commit, extension file hashes, screenshots, grant IDs/statuses, snapshot
   counts before/after refusal/revocation and zero note/relationship-analysis counts. Check
   logs contain no model calls. Close the disposable profile and stop only the processes
   started for this procedure. Record PASS only if all these checks pass; otherwise retain
   NOT QUALIFIED with the exact failure. This procedure has **not** been executed for R1.

## Files changed

- `.github/workflows/ci.yml`: full history and required notebook job.
- `site/notebook.py`: canonical metadata and rendered-title verification; history failure.
- `tests/test_notebook_01.py`, `tests/notebook-capture.test.cjs`: adversarial integrity,
  determinism, no missing-tool/history skips.
- `tests/fixtures/notebook-r4.json`: preserved misleading-presentation research fixture.
- `scripts/native_notebook_01.py`: explicit substitution scope and evidence output option.
- `scripts/native_notebook_01_shipped.py`: separate shipped-config native load smoke.
- `site/README.md`, `docs/ALIVE-NOTEBOOK-01-REPORT.md`, this report and validation evidence:
  qualification corrections, reproduction and results.

The historical PR #40 description was corrected in place to state its merged status, all
substitutions, lexical rank conditions and the limits of its evidence. Its actual hosted run
[#231 / 40771211673](https://github.com/ernanhughes/alive/actions/runs/40771211673)
concluded success, but omitted notebook gates and allowed provenance skips. That historical
green run is not evidence that notebook provenance was enforced.
