# ALIVE-DEMO-LIVE-01 — Claude independent review packet

## Identity and scope

Base: `6713adf8145b915954e6c00bb7541ae2608acb12`.
Final runtime implementation/native-tested code: `d2eeced2843624583760f099b870092d31565840`.
Branch: `feature/alive-demo-live-01`; final delivery ref is the draft PR head.
Documentation and evidence commits follow code qualification. Verify this yourself:

```powershell
git rev-parse HEAD
git diff --exit-code d2eeced2843624583760f099b870092d31565840 HEAD -- alive extension scripts tests fixtures .github
```

Read the [implementation report](ALIVE-DEMO-LIVE-01-IMPLEMENTATION-REPORT.md), but do
not accept its verdict without rerunning the code. Nothing was merged and no
independent review or paid provider qualification is claimed by the implementer.

The change is one anchored-passage, explicitly authorised comparison flow in the
existing Chrome companion. It adds production capture-v2, focused attributed
Python mirrors and a synthetic abstention page, direct source saving without a
model note, source/entry-bound validation, exact local previews and evidence cards.
It does not add autonomous cycles, a new research engine, migrations or paid calls.

## Critical entry points

| Area | Entry point / question |
|---|---|
| Extraction | `extension/capture.js`: block/inline fidelity, exclusions, selected range and Unicode offsets |
| Production observer | `extension/observer.js`: capture version and retained limits |
| Capability bridge | `extension/background.js`: live-selection/remember/context/preview, active Goal and stale-capture gates |
| UI trust boundary | `extension/live-companion.js`: text-only rendering, exact disclosure, Goal checks, stale response suppression, local provider labels |
| Source identity | `alive/demo_live_01.py`: only known paths/bytes/entry maps inherit manifest metadata |
| API provenance | `alive/web_experience.py`: SnapshotRequest capture contract, snapshot metadata and direct-source save request |
| Saved evidence | `alive/research_memory.py`: save_snapshot, anchor CAS, retrieval anchor metadata and existing withdrawal |
| Authorization | `alive/research_relationships.py`: claim-only payload metadata, ordinary guard, real-fixture identity gate, settlement and candidate storage |
| Validation | `alive/claim_comparison.py`: exact spans, pinned v2 entry binding and conservative named-subject refusal |
| Fixture output | `alive/claim_fixtures.py`: exact SHA-pair demo registry; no text-based label inference |
| Real browser evidence | `scripts/native_demo_live_01.py`: actual docked Chrome, actual APIs, backend restart and database scan |
| Isolated startup | `scripts/demo_live_01.py`: separate database, no migration, empty Meta keys and disabled Meta flags |

The bounded experiment AST and all protected files/old tests must remain unchanged.
Use [protected-boundaries.json](validation/demo-live-01/protected-boundaries.json)
and independently compare the base. Archive/protocol verification must still pass.

## Reproduce independently

1. Check out the PR branch. Record its SHA and working-tree status.
2. `uv sync --locked`; `npm ci --prefix dashboard`.
3. Run all Python tests: `uv run pytest -q --tb=short -rs`.
4. Run all five Node suites:

```powershell
node --test tests/extension-background.test.cjs tests/extension-panel.test.cjs tests/extension-capture.test.cjs tests/extension-live-background.test.cjs tests/extension-live-companion.test.cjs
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
uv run python -m scripts.native_demo_live_01
```

5. Run the PostgreSQL-configured domain subset against your **isolated** test
   server, whose admin role may create/drop disposable test databases:

```powershell
$env:ALIVE_CLAIM_TEST_PG_URL = 'postgresql://YOUR_TEST_ROLE@127.0.0.1:YOUR_TEST_PORT/postgres'
uv run pytest -q tests/test_demo_live_01.py tests/test_claim_runtime.py tests/test_demo01_foundation_probes.py --tb=short
```

6. Re-enact the manual Demo A/B routes in the implementation report using
   `uv run python scripts/demo_live_01.py --port 8000`, the unpacked extension and
   its separate token file. Browser bootstrapping/restart is outside the user
   research interaction. No terminal work is needed to anchor, discover, check,
   dismiss, retain or withdraw once connected.
7. Do not regenerate fixtures silently: the acquisition script performs network
   retrieval and intentionally changes provenance. Compare current pins first.

All model implementations must stay disabled. Native runs use the production
local fixture branch, not a patched MetaProvider or scripted fake frontend state.
Do not use a real API key to test this PR.

## Expected versus observed

| Scenario | Expected | Implementer observation |
|---|---|---|
| Python 3.11 anchor | Exact selected behavior span, source SHA and revision | Actual Chrome selection + API anchor |
| Python 3.12 comparison | Source-stated standing change; retained behavior sentence | Entry-bound candidate, retained=true, `datetime.datetime.utcnow` |
| Neighbor's deprecation | Refuse as basis for utcnow | Permanent validator assertion demotes it |
| Unknown/forged identity | No validated alert | Identity/entry/downgrade regressions pass |
| Synthetic newer page | Recorded abstention, no candidate | Native Demo B validated ledger/no finding |
| Repeated exact comparison | Reuse exact candidate without another dispatch | Native cached re-review; two total dispatches for A+B |
| Dismiss interpretation | Preserve historical source | Native/Node assertions pass |
| Withdraw + restart | No ordinary active finding and no derived text copies | Native/API/all-table scan + real backend restart pass |
| Goal switch/stale capture | Refuse stale preview/dispatch and suppress old UI response | Node/backend tests pass |
| General deletion/privacy | Not promised by this milestone | Authoritative originals retained; legacy note endpoint concern remains |

Reported totals: baseline Python **368 passed / 6 skipped** and Node **11 passed**;
final Python **380 passed / 6 skipped**, Node **29 passed**, PostgreSQL domain subset
**42 passed**. Full transcripts are in `docs/validation/demo-live-01/`.
Native result: `native/result.json`, Chrome 156.0.8078.73 on Windows 11, genuine
docked side-panel target, 360 px emulation with no horizontal overflow. Linux and
native paid Meta were not run. Screenshots document both outcomes and retirement.
The first two native harness timing failures are retained, not counted as passes.

## Fixtures and authenticity challenge

Read `fixtures/demo_live_01/manifest.json`, the full acquired upstream HTML and
license pages, focused mirror HTML and browser capture JSON. Recompute byte and
text hashes; confirm title/version and retrieval timestamps. Independently fetch
canonical sources if desired, but current network bytes may have changed since
retrieval. Upstream git revision is explicitly **not established**, not guessed.

The mirrors declare their local/derivative status, focus on two method entries,
and preserve the confusing neighbor. They are not presented as a byte-identical
full canonical page or as a live Meta result. The synthetic page is separately
labelled and makes no claim to be Python documentation. Evaluate whether the scope
of that transformation and the identity language are sufficiently clear.

## Authorization/revocation invariants to attack

- Discovery/ranking is local; no standing inference permission is created.
- The exact request binds excerpts, source IDs/hashes, v2 entry maps/identities,
  anchor quote/offsets/revision, instructions, schema and provider/model identity.
- Only the ordinary claim path runs. No silent history-assisted fallback.
- Pre-marker committed revocation prevents provider entry (I-E1).
- Post-marker revocation discards settlement/candidates; bytes cannot be recalled
  (I-E2). In-flight withdrawal/re-anchoring are rejected by the existing gate.
- Consent expiry, provider enablement, source changes and anchor changes are
  revalidated. Real fixture bytes downgraded to v1 cannot bypass identity checks.
- Local failed checks cost zero; ambiguous external dispatch recovery remains
  conservative. Replay/cancellation cannot settle twice or resurrect a finding.
- Dismissal changes interpretation feedback, not source status. Withdrawal uses
  authoritative retirement and projection removal, not a UI-only hide.

## Required adversarial challenges

1. Reassign exact quotes to the wrong source or forge snapshot identity metadata.
2. Use the real `utcfromtimestamp()` deprecation as utcnow's basis; swap/corrupt
   entry spans or subject IDs; remove the correct method's marker.
3. Select the second of two identical passages; place emoji/non-Latin text before
   it; alter the selected range, quote, SHA or expected revision before confirm.
4. Revise an anchor between preview and authorisation/dispatch; withdraw before,
   during and after settlement, after caching and after backend/panel restart.
5. Deterministically commit revocation on both sides of the durable marker. A
   network-side request already sent must not be falsely described as recalled.
6. Inject HTML/event handlers in quotes, titles, reasons and provenance; change
   the Goal while preview or inference promises are pending; return stale UI data.
7. Modify a mirror, upstream HTML, capture JSON or manifest; alias an unknown URL
   with the same bytes; downgrade the real fixture capture to v1.
8. Repeat/cancel a consumed consent; interrupt process recovery around the marker;
   ensure liability, Governor reservations and candidate reuse remain correct.
9. Put identical source captures in multiple Goals and verify scope/dedup behavior.
10. Challenge every phrase implying understanding, standing, validity or unchanged
    text. Deterministic provenance acceptance must not be presented as semantic truth.

Stop and report any essential integrity violation. Do not mask it with changed
expectations, omitted probes, an invented live result or optimistic PR language.

## Known unresolved limitations — do not overlook

**Legacy-note withdrawal privacy is unresolved:** `/notes/{id}` can still serve an
authoritative model note after its associated saved memory is withdrawn. Existing
retention-policy tests deliberately remain unchanged. The new direct-source flow
creates no note; the live active-finding and projection lifecycle is qualified,
not complete data erasure. Decide separately whether to approve legacy-note
suppression. Do not accept any claim of complete withdrawal privacy while that
path remains.

Capture-v1 behavior is retained as legacy, not silently upgraded or generally
qualified for entity binding. Unregistered v2 sources/pairs do not produce this
local demo's validated alert. No live provider readiness, human usefulness,
manual 90-second usability timing, cryptographic source authenticity or general
claim-truth verification is established. Review the scope of readiness labels.

The proposed local-demo engineering verdict is PASS; Demo A/B are READY within
that declared scope. **Independent Claude review is requested, not presumed.**
Do not merge or authorize a paid/live inference demonstration on this packet alone.

Supplementary repository-wide Ruff commands expose existing out-of-CI-scope issues
(84 lint errors; 7 unformatted files), all on paths unchanged from the base. The
implementation report includes the outputs; the scoped CI lint gates pass.
