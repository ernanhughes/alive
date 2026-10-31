# PI-03B delivery record (draft for independent review)

Stops at the PI-03B review gate. PI-03C and the Bespoke selector are not started and nothing here
depends on them. Not merged. No paid inference was used.

## Identity

| | |
| --- | --- |
| Repository | `ernanhughes/alive` |
| Branch | `pi-03b-source-capabilities` |
| Base | `origin/main` `495e4fedaeacedbec33e94b77a485c26dd792a34` (verified before branching) |
| Head | the PR head. Capability and implementation identities at that code state are recorded in `validation/pi03b-identities.json` (its `generated_at_commit` names the commit) |
| Size | about 35 files, 4,800 lines added, 11 removed |

## What is delivered

1. Source custody: durable immutable captures and separately recorded, withdrawable owner approvals
   (migration `0013`, two additive tables), and `custody.resolve`, which re-checks every fact when a
   stage starts. See `PI-03B-SOURCE-CUSTODY.md`.
2. The owner's approval path: `python -m alive.sources` (prepare, inspect, approve, withdraw). Local,
   no network route, no runtime start, no workflow grant.
3. A `source.read` permission class (`permissions.sources: approved_capture`) that leaves every
   earlier manifest hash unchanged (pinned by a test).
4. Four capabilities, each a YAML manifest plus a reviewed trusted adapter:
   `repository.inspect@1.1.0`, `document.extract@1.0.0`, `browser.prepare-source@1.0.0`,
   `retrieval.approved-collection@1.0.0`. They appear in the existing Capabilities pane unchanged.
5. 83 new tests (including one opt-in PostgreSQL test), 23 new mutants, and the PI-03B documents in
   this directory (architecture, custody, security, this record).

## Explicitly not delivered (stated, not hidden)

| Item | Status |
| --- | --- |
| Live use: an owner approving a source and then running a workflow on it | **Not implemented.** Needs its own admission design and security review. Tests use the same trusted fixture owner PI-03A used. |
| PDF extraction | **Unavailable.** No reviewed PDF parser dependency exists. |
| OCR, fetching, crawling | Not implemented, by design. |
| Validation, locators, claim comparison, reports | PI-03C. |
| Retention period, deletion path or encryption at rest for captured content | Not implemented; decision requested. |

## Evidence

All commands are from the repository root of the worktree. Local, on a Windows 11 host unless noted.

| Check | Result |
| --- | --- |
| New source tests on Windows (custody 25, CLI 4, capture 28, capabilities 22, seam 3) | 81 passed, 1 skipped (the POSIX-only FIFO test); the FIFO test passes in the Linux run below |
| PostgreSQL 16, disposable empty database: JSONB, database-side expiry, tamper detection, two-kernel approval race, 0013 downgrade/re-upgrade | pass |
| Linux container (the reviewer's image), filesystem-sensitive suites including real FIFOs | 90 passed |
| Broad focused regression (capability, source, workflow, Intelligence, migration, Pi gateway, architecture-boundary suites; pinned Pi installed) | 614 passed, 7 skipped, 1 failed. The failure was a legacy invariant test (`test_the_operation_set_is_closed`) that the new implementations violated; fixed in the next commit, then 95 passed across the four affected files |
| `ruff check` and `ruff format --check` on changed files | clean |
| Mutation campaign (`scripts/capability_mutations.py`, S-series, receipts in `validation/pi03b-mutations.json`) | 23 killed, 0 survived, 0 invalid (see "Mutation campaign") |

### Mutation campaign

23 single-guard mutants over the custody, scope, provenance and hash-stability guards. A kill needs
a behavioral test failure with no collection, setup or teardown error.

The first pass killed 12, left 1 and counted 10 invalid. The 10 were not escapes: the intended
assertion failed, but a failed `pytest.raises` *inside* the test client's portal raises a
`BaseException` that crashes the portal and adds a teardown error, which the harness correctly
refuses to count. The tests now return refusals as data. The survivor, S15 (source type), is checked
twice with the same category (the runner seam and the adapter), so each alone is an equivalent
mutant; S15 removes both together. The cross-instance test was also strengthened: it previously
tripped the earlier "approval missing" check and never reached the instance check.

**Final result, one full run on the final code (code state `a938daf`, no merged or repeated receipts):
23 killed, 0 survived, 0 invalid.** An earlier pass produced the 12/1/10 split described above; its
receipts were replaced, not merged, by this run. CI results for the exact PR head are kept in the PR
description, not in a commit.

Not mutated: the PostgreSQL race handler (`IntegrityError` retry; needs PostgreSQL, proven by the
two-kernel test instead); the HTML nesting bound and parser sanitization (own adversarial tests);
`O_NONBLOCK` (needs POSIX; PI-03A proof); symlink refusal in document capture (the test skips where
symlinks need privilege, as on this host); the collection materialisation instance filter (its
input ids come from a capture already scoped to the instance, so removing it is an equivalent mutant).

## Compatibility notes a reviewer should check

1. **`repository-inspector-v1`'s fingerprint changed** (`3ca0a2fe1aa4…` to `bdeb62767746…`) because
   `repository.py`, which it fingerprints, gained capture ceilings. Its behavior for existing callers
   is unchanged (defaults are identical). The effect is that a non-terminal run or unspent grant
   pinned to `repository.inspect@1.0.0` would fail closed and need re-approval. Completed history is
   unaffected. PI-03A had no production grant path, so no such grant is expected to exist. The other
   legacy implementations are byte-identical in identity.
2. `repository.inspect` now has two versions. An unpinned stage resolves to `1.1.0` at registration;
   the PI-03A test fixture pins `1.0.0`.
3. `ReadCapabilityContext` gained `inputs` and `limits` (defaults empty), so v1 is unaffected.
4. `capture_repository` accepts larger explicit ceilings; defaults are unchanged.

## Not verified

Windows and Linux CI at the final head, the Docker image build and smoke test, Playwright browser
tests, the extension tests, and the full backend suite. macOS. The independent review itself.

## Instructions for the independent reviewer

1. Read `PI-03B-SOURCE-CUSTODY.md`, then `PI-03B-SECURITY.md` ("Limits" and "Decisions").
2. Try to use a source without approval, after withdrawal, after expiry, with another instance's
   approval, with a changed digest, with an out-of-scope path, and by naming a different source in
   the stage input. Each should be a named refusal before any content is returned.
3. Try to make `python -m alive.sources approve` succeed without the exact digest, or to reach custody
   from a model, page, extension event or HTTP route.
4. Re-run the mutation campaign with independent mutants. Candidates not in this table: the
   `apply_scope` omission filtering, `materialize_collection` ordering, and the event payloads.
5. Check the compatibility notes above, particularly the fingerprint change.
6. Decide the four owner decisions in the security document.
