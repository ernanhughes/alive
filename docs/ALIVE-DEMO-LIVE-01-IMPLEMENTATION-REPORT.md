# ALIVE-DEMO-LIVE-01 — Implementation report

## Scope and repository identity

- Base: `6713adf8145b915954e6c00bb7541ae2608acb12` on verified current `main`.
- Branch: `feature/alive-demo-live-01`.
- Final implementation and native-tested commit: `d2eeced2843624583760f099b870092d31565840`.
- Documentation/evidence-only commits follow that implementation checkpoint. The
  final delivery SHA is the draft PR head; reviewers should record `git rev-parse HEAD`.
- Delivery is a **draft PR**, not a merge, paid pilot, Think cycle, or general
  evidence-truth engine. Independent review has not been performed by Codex.

PRs #29–#35 and #36 were confirmed merged through GitHub metadata and inspected
against the current code. Earlier draft/unqualified reports were not treated as
proof of qualification. The relevant C1B and Intelligence-01 Claude reviews were
read along with current source and regression tests.

## Baseline and implementation sequence

Before application changes, the existing Windows/SQLite suite returned **368
passed, 6 skipped, 0 failed**; existing Node suites returned **11 passed, 0 failed**.
All six skips are historical R4 cases superseded by R5. Baseline outputs are in
[baseline-python.txt](validation/demo-live-01/baseline-python.txt) and
[baseline-node.txt](validation/demo-live-01/baseline-node.txt).

1. Implemented production capture-v2, acquired attributed canonical documentation,
   pinned focused mirrors, and bound source/entry provenance through the ordinary
   claim path. Qualified the backend before changing presentation.
2. Added selection confirmation, immediate local discovery after explicit page
   authorisation/review, exact comparison preview, authorization, real recorded
   outcomes, evidence cards, dismissal/keeping and withdrawal.
3. Added and exercised the project's real docked-Chrome harness, then preserved
   its evidence, final automated results and independent-review instructions.

Two early native harness attempts failed because they waited for transient status
copy after a completed capture. Their errors and metadata are preserved as
`native/attempt-1*` and `native/attempt-2*`. They did not expose an integrity-stop
condition. The harness now waits for completed actions and actual backend state.
Subsequent runs passed; the final result was produced from a clean implementation
tree at the SHA above. Intermediate lint issues were resolved; the final lint gate
passes. No failed run is presented as a pass.

## Existing infrastructure reused

Existing Goal identities, `WebExperience` rows, source grants, `ResearchMemory`,
lexical retrieval, revisioned anchors, the ordinary `ResearchRelationships.analyze`,
exact consent hashes, durable dispatch markers, Governor reservations, settlement,
feedback, invalidation and restart recovery are reused. No new entity tables,
migrations, provider clients, autonomous schedulers or intelligence cycles exist.

The `_analyze_bounded` AST is unchanged from the base. Campaign approvals/protocols,
research-blind code, frozen archives and existing regression expectations are
unchanged. [Boundary proof](validation/demo-live-01/protected-boundaries.json)
also records archive/protocol verification. New Node gates were added to CI.

## Capture and provenance

`extension/capture.js` is the production capture function loaded before the
observer. It preserves block/paragraph/entry boundaries, concatenates inline text
without trimming each node, excludes private/hidden/non-content elements, records
Sphinx entry spans and emits format version 2. Selection positions and entry spans
use Unicode code-point offsets compatible with Python. Repeated passages retain
the explicitly selected DOM occurrence. Existing 8,000/3,000/2,000 character limits
remain. Stored format-v1 evidence is not reprocessed or upgraded.

The browser test confirms `with <code>tzinfo</code> <code>None</code>.` becomes
`with tzinfo None.`. Tests cover nested blocks without double counting, lists,
code, duplicate text, Unicode and privacy exclusions. Actual Chrome captures,
not BeautifulSoup's text-joining algorithm, generated the pinned capture files.

### Real source fixtures

Canonical sources were retrieved over HTTPS:

- [Python 3.11 datetime](https://docs.python.org/3.11/library/datetime.html), whose
  acquired title identifies **Python 3.11.18** documentation.
- [Python 3.12 datetime](https://docs.python.org/3.12/library/datetime.html), whose
  acquired title identifies **Python 3.12.16** documentation.

The focused mirrors prominently say **LOCAL MIRROR — PYTHON DOCUMENTATION**, link
the canonical source/version and PSF license, and retain both `utcnow()` and
`utcfromtimestamp()` entries, including the neighboring deprecation notice. They
explicitly disclose omission of other entries. Header permalink glyphs are omitted
by the same capture exclusion used in production. The complete acquired HTML and
license pages are retained for provenance. The mirrors are focused derivatives,
not byte-identical copies of the complete canonical page or its visual styling.

[manifest.json](../fixtures/demo_live_01/manifest.json) records retrieval UTC,
exact acquired build title, upstream HTML SHA-256, mirror SHA-256, captured-text
SHA-256, entry offsets, capture browser, format version, licensing and attribution.
**Upstream git revision was not independently established and remains null.** No
commit identity was inferred from a version URL. Identity means a match to pinned
local bytes/entry structure; it is not independent factual verification.

| Capture | Characters | Captured-text SHA-256 |
|---|---:|---|
| Python 3.11 mirror | 1841 | `2c47a1179d4a97b5b7c13c1d60e20dcd4ed340ba3343a95d0363817884538494` |
| Python 3.12 mirror | 1987 | `8a549c9616d48bc9660259afcdc43adaa864d52cf363127e24cb3fbf9352a6bf` |
| Clearly labelled synthetic newer page | 153 | `c726319fe3c1c1e48f5609bb52081a3aa8bf164c9d607e8afbad727031274233` |

## Source, anchor and comparison behavior

A reviewed snapshot can now be saved directly as `owner_selected_source`, without
creating a fictional validated model note. Existing note-based saving remains.
The source and retrieval projection use existing kinds/tables. Same-Goal duplicate
captures reuse the same saved source; withdrawn sources are not resurrected.

The panel reads an actual DOM selection, displays its exact captured span,
investigation, title/URL, provenance, chosen occurrence and existing revision,
then requires **Confirm passage**. The existing anchor CAS contract handles stale
SHA/revision, malformed/nonmatching selections, unknown memories and in-flight
conflicts. Re-anchoring invalidates dependents bound to the prior revision.

**Authorise and review page** grants only the existing page capability, captures
locally, saves the reviewed snapshot and invokes local Goal-scoped retrieval.
Suggestions explain lexical matches and do not assert a change. **Check against
new evidence** requests `analysis_mode=claim_comparison` and
`provider=local_fixture_claim` explicitly. Neither fallback nor Meta selection is
available through the new action. A stale page/capture or switched Goal is refused.

Preview shows the exact instructions/input/schema, source identities/hashes,
anchor offsets/revision, provider, expiry, reservation, maximum spend and
payload/request hashes. The request hash binds the actual instructions and schema.
**Authorise exact comparison** is separate from discovery. Cancellation before
analysis revokes that consent. Progress text describes an actual outstanding
request, not simulated model thinking.

All eight claim seams were inspected and exercised. Capture provenance is bound
into exact hashes and rechecked before dispatch and settlement. Only accepted
conflicts/qualifications/source-stated supersessions can create candidates. The
real Python pair requires pinned capture-v2 identity, including at fixture
provider dispatch; simply relabelling its bytes as v1 fails closed. Unknown pairs
cannot invoke a model. A named, unbound method in a legacy supersession basis is
also conservatively demoted, without weakening prior tests.

For v2, the historical quote and current/basis quote must belong to the same
pinned Sphinx subject entry. The `utcfromtimestamp()` deprecation cannot stand in
for `utcnow()`. Missing/forged identity or entry provenance abstains. The accepted
example reports a status/recommendation change with the behavior sentence retained;
it does not say the historical behavior was false.

The companion displays only entry-bound local-fixture candidates. It does not
relabel old v1 or Meta candidates as qualified local results; legacy views remain
available under advanced tools. Source text is rendered with `textContent`, and
demo links use the configured backend allowlist. Dismissal records interpretation
feedback while retaining evidence; keeping records an owner review preference.
Withdrawal clears live and legacy finding cards before refreshing authoritative
state. Delayed responses cannot restore those cards.

## Qualification results and exact commands

```powershell
uv run pytest -q --tb=short -rs
# 380 passed, 6 skipped, 541 warnings in 374.67s

$env:ALIVE_CLAIM_TEST_PG_URL = 'postgresql://postgres@127.0.0.1:61587/postgres'
uv run pytest -q tests/test_demo_live_01.py tests/test_claim_runtime.py tests/test_demo01_foundation_probes.py --tb=short
# 42 passed, 44 warnings in 48.14s; isolated PostgreSQL 18 test server/databases

node --test tests/extension-background.test.cjs tests/extension-panel.test.cjs tests/extension-capture.test.cjs tests/extension-live-background.test.cjs tests/extension-live-companion.test.cjs
# 29 passed, 0 failed

uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
# passed; 165 files already formatted

uv run python -m scripts.native_demo_live_01
# PASS, real docked Chrome target, both demonstrations, real backend restart
```

[Full Python output](validation/demo-live-01/python-final.txt),
[PostgreSQL output](validation/demo-live-01/postgres-final.txt),
[Node output](validation/demo-live-01/node-final.txt),
[native result](validation/demo-live-01/native/result.json), and
[native command output](validation/demo-live-01/native-final.txt) are included.
The ZeroMQ/Windows Proactor warnings remain visible; they are not suppressed.

A supplementary repository-wide `uv run ruff check .` reports **84 existing
errors**, and `uv run ruff format --check .` reports **7 existing unformatted
files** outside the CI lint scope (archived evidence, reviewer attachments and
`skill_forge`). All affected paths were verified unchanged from the base. Those
files were left intact. These broader commands do not pass; the scoped CI commands
above pass. See [repository-wide lint](validation/demo-live-01/repository-wide-lint.txt)
and [format output](validation/demo-live-01/repository-wide-format.txt).

Windows 11 and SQLite: **RUN, PASS**. PostgreSQL 18: **RUN, PASS** for the 42-test
claim/foundation subset, not the entire campaign suite. Native Chrome
156.0.8078.73: **RUN, PASS** through the supported CDP/Playwright harness, with a real
docked side-panel target, not an ordinary extension tab. The panel was emulated
at a 360 px viewport and checked for horizontal overflow. This is browser-harness
qualification, not a human usability or measured 90-second performance study.
Linux, PostgreSQL/pgvector first-contact UI and native paid Meta: **NOT RUN**.
The temporary PostgreSQL server and native backends were stopped after testing;
their isolated test data remains outside the owner database.

## Native observed outcomes

- **Demo A:** selected the real DOM sentence; saved source and anchor through UI;
  newer page produced a retrieval hint; exact local comparison was separately
  authorised; a candidate identified `datetime.datetime.utcnow`; retained text and
  source-stated deprecation were displayed distinctly.
- Dismissed interpretation did not remove its source. Explicit re-review reused
  the exact cached candidate without a second provider dispatch. Keeping the
  interpretation persisted owner feedback.
- UI withdrawal removed the finding; API and all-table scans found no derived
  quote copies. Remaining matching rows were audit-original snapshots and the
  withdrawn source. A real backend process restart plus panel reload left the
  finding absent, including when the original Goal was re-queried.
- **Demo B:** a separate Goal anchored the source, then the clearly synthetic newer
  page produced a validated abstention ledger row and no candidate.
- **Final native run:** two recorded local fixture provider dispatches, both with
  zero model token usage; no note rows; zero recorded external provider dispatches;
  zero paid spend. The cached re-review did not add a third dispatch. Automated
  fixture invocations across all test suites were not globally aggregated.

Screenshots: [anchor](validation/demo-live-01/native/01-anchored-source.png),
[meaningful change](validation/demo-live-01/native/02-meaningful-change.png),
[retired](validation/demo-live-01/native/03-evidence-retired.png),
[after restart](validation/demo-live-01/native/04-retired-after-restart.png),
[abstention](validation/demo-live-01/native/05-credible-abstention.png).

## Reproduction: setup, then a roughly 90-second interaction

From a checked-out branch, install existing dependencies (`uv sync --locked`,
`npm ci --prefix dashboard`) and run:

```powershell
uv run python scripts/demo_live_01.py --port 8000
```

This prepares a separate `.alive/demo-live-01/demo.db` with existing table metadata;
it applies no migration. Meta keys are empty, Meta flags false, the provider base
is an unreachable loopback address, and only the test fixture provider is enabled.
Load the existing `extension/` folder as an unpacked extension in Chrome. No shipped
manifest permission changed. Connect to `http://127.0.0.1:8000` with the token in
`.alive/demo-live-01/token`; the token is not included in this package.

**Demo A:** save an investigation about `datetime.utcnow`; open the historical
mirror from Demonstration sources; click **Authorise and review page**; select the
behavior sentence on the page; click **Remember this passage**, inspect the
selection and **Confirm passage**. Open the 3.12 mirror; authorise/review it; follow
the related-passage hint; **Check against new evidence**; inspect/expand the exact
preview; **Authorise exact comparison**. Review the unchanged sentence, deprecation
and provenance. Use **Withdraw saved source → Confirm withdrawal**. Reload the
panel: no active candidate remains. Backend restart is exercised by the harness;
it is an operator/service operation, not a new browser administration endpoint.
The normal capture/anchor/check/withdraw interaction requires no terminal use.

**Demo B:** use a separate investigation, remember the historical passage again,
then open the labelled synthetic page and authorise/review it. Authorise the
comparison. Expect **Evidence checked · No validated change detected**, a real
ledger entry and no alert. The 90-second duration is a presentation target, not a
measured human-completion claim.

Refresh the upstream fixtures only intentionally with
`uv run python scripts/prepare_demo_live_01.py`. That performs real HTTPS retrieval
and updates pins/provenance; it is not a test dependency. Review and requalify the
changed pins before use. Ordinary tests/demos use committed offline fixtures.

## Deviations, remaining risks and explicit unresolved blocker

- This milestone qualifies the pinned local-mirror path. Capture-v2 sources without
  a registered identity/pair cannot produce this demo's validated alert. Existing
  v1 contracts remain available as legacy test-provider behavior; they are not
  retroactively reprocessed or claimed to have general entity-binding quality.
- **Unresolved legacy withdrawal-privacy blocker:** `/notes/{id}` still serves a
  retained authoritative model note after its research memory is withdrawn, under
  the established retention policy. Existing tests explicitly document that
  policy, and were not changed to conceal it. The new selection flow creates no
  model note, and ordinary active research-finding endpoints suppress retired
  findings. **Complete withdrawal privacy/deletion is not claimed.** An approved
  legacy-note suppression policy remains a separate review decision.
- Original snapshots and withdrawn source records remain intentionally. The
  evidence-validity lifecycle retires findings; it is not an erasure mechanism.
- A request that has passed its durable marker may already have been sent;
  revocation discards the result but cannot recall bytes. Pre-marker revocation
  prevents dispatch. Existing C-real/D/E/F and newer I-E1/I-E2 tests remain intact.
- Shipped Chrome permissions are unchanged. The harness uses a fresh profile and
  a copied extension whose host list is restricted to its isolated loopback
  backend. It does not change the owner's installed extension/profile.
- No human-usefulness study, external provider readiness, actual owner paid consent,
  cryptographic source authenticity, or independent semantic truth is asserted.
- Demo links and the local card deliberately identify deterministic output. A
  future paid/live provider demo needs separate owner authorization, exact preview,
  spending cap and independent qualification.

## Complete file-change inventory

- `.github/workflows/ci.yml`
- `alive/app.py`
- `alive/claim_comparison.py`
- `alive/claim_fixtures.py`
- `alive/demo_live_01.py`
- `alive/research_memory.py`
- `alive/research_relationships.py`
- `alive/web_experience.py`
- `docs/ALIVE-DEMO-LIVE-01-CLAUDE-REVIEW-PACKET.md`
- `docs/ALIVE-DEMO-LIVE-01-IMPLEMENTATION-REPORT.md`
- `docs/validation/demo-live-01/baseline-node.txt`
- `docs/validation/demo-live-01/baseline-python.txt`
- `docs/validation/demo-live-01/capture-node.txt`
- `docs/validation/demo-live-01/core.txt`
- `docs/validation/demo-live-01/native-final.txt`
- `docs/validation/demo-live-01/native/01-anchored-source.png`
- `docs/validation/demo-live-01/native/02-meaningful-change.png`
- `docs/validation/demo-live-01/native/03-evidence-retired.png`
- `docs/validation/demo-live-01/native/04-retired-after-restart.png`
- `docs/validation/demo-live-01/native/05-credible-abstention.png`
- `docs/validation/demo-live-01/native/attempt-1-result.json`
- `docs/validation/demo-live-01/native/attempt-1.txt`
- `docs/validation/demo-live-01/native/attempt-2-result.json`
- `docs/validation/demo-live-01/native/attempt-2.txt`
- `docs/validation/demo-live-01/native/attempt-3-result.json`
- `docs/validation/demo-live-01/native/attempt-4-result.json`
- `docs/validation/demo-live-01/native/result.json`
- `docs/validation/demo-live-01/node-final.txt`
- `docs/validation/demo-live-01/postgres-final.txt`
- `docs/validation/demo-live-01/protected-boundaries.json`
- `docs/validation/demo-live-01/python-final.txt`
- `docs/validation/demo-live-01/repository-wide-format.txt`
- `docs/validation/demo-live-01/repository-wide-lint.txt`
- `extension/background.js`
- `extension/capture.js`
- `extension/config.js`
- `extension/live-companion.js`
- `extension/observer.js`
- `extension/panel.html`
- `fixtures/demo_live_01/.gitattributes`
- `fixtures/demo_live_01/license-3.11.html`
- `fixtures/demo_live_01/license-3.12.html`
- `fixtures/demo_live_01/manifest.json`
- `fixtures/demo_live_01/python-3.11.capture.json`
- `fixtures/demo_live_01/python-3.11.html`
- `fixtures/demo_live_01/python-3.12.capture.json`
- `fixtures/demo_live_01/python-3.12.html`
- `fixtures/demo_live_01/synthetic-no-change.capture.json`
- `fixtures/demo_live_01/synthetic-no-change.html`
- `fixtures/demo_live_01/upstream-3.11.html`
- `fixtures/demo_live_01/upstream-3.12.html`
- `scripts/demo_live_01.py`
- `scripts/native_demo_live_01.py`
- `scripts/prepare_demo_live_01.py`
- `tests/extension-capture.test.cjs`
- `tests/extension-live-background.test.cjs`
- `tests/extension-live-companion.test.cjs`
- `tests/test_demo_live_01.py`

Qualification verdicts below apply to the delivered deterministic local-mirror
workflow, with the legacy-note privacy blocker explicitly excluded from any claim
of complete withdrawal privacy. The PR must remain draft for independent review.

**Engineering integrity: PASS**

**Demo A readiness: READY**

**Demo B readiness: READY**

**Ready for independent Claude review: YES**
