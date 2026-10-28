# I1-A2 local qualification — STOP / NOT READY

28 October 2026. Local repair branch: `codex/i1-a2-qualification`.

## Repository identity and boundaries

Started at `767596cde22bdc6d5c896415fb83e0e9604a61c8` (PR #35 already merged).
During this session an external operation added merge commit
`fc56df422057ada63e38076efbd8b0b45df9e6f3`; its tree is identical to the starting
commit. This session did not perform that merge. Repairs below are uncommitted
working-tree changes, not a qualified commit or PR. No push or merge was performed
by this agent.

The complete `_analyze_bounded` method was restored byte-for-byte to pre-I1-A2
commit `5a750c4`. No ALIVE-14 test, campaign, experiment, blind-test file, migration,
browser permission, or intelligence-cycle implementation was edited.

## Repairs and new coverage

- Repaired the literal backslash-n and malformed fixture dispatch syntax.
- Removed the undefined `analysis_mode` edits from the bounded method by restoring
  that method to its pre-I1-A2 implementation.
- Routed `local_fixture_claim` to a pinned synthetic SHA-pair map; unregistered
  sources fail closed. Explicit non-Meta identities cannot reach external dispatch.
- Added claim source/anchor, consent-expiry and default-off paid-mode checks at
  the ordinary dispatch guard. Claim expiry is persisted before returning an error.
- Added claim version metadata, zero local-provider liability, cancellation
  settlement/propagation, and local-provider restart accounting.
- Refused duplicate settlement or candidate storage following recovery of an
  already interrupted ordinary-path attempt.
- Removed copied reliance and claim text from invalidated derived records.
- Added owner-revoked current-grant invalidation and correct settlement reasons.
- Distinguished invalid anchor spans (422) from stale source/revision conflicts
  (409).
- Added 25 synthetic claim-runtime tests, 16 permanent cases from the newer Claude
  attack corpus, five foundation tests, and a reusable all-table evidence scanner.
  The fixture prerequisite note is seeded locally; save and subsequent lifecycle
  steps use real APIs. These are not real capture-v2 fixtures.

## Files authored or edited by this session

Product: `alive/research_relationships.py`, `alive/research_memory.py`,
`alive/web_experience.py`, `alive/claim_fixtures.py`.

Tests: `tests/test_claim_runtime.py`, `tests/test_claim_review_attacks.py`,
`tests/test_demo01_foundation_probes.py`, `tests/evidence_leaks.py`.

Documentation: this report, a follow-up note in `ALIVE-INTEL-I1A2-DRAFT.md`,
and the four execution transcripts under `docs/validation/i1-a2/`.
Owner-added Claude reviews and scratch scripts were read and left unchanged.
The pre-existing untracked `models.txt` was left unchanged.

## Qualification stopped on a real derived-record leak

The newly supplied [review contract](ALIVE-INTELLIGENCE-01-CLAUDE-REVIEW.md), section
12, says: **"Stop and report without working around"** upon **"a leak-scanner hit
in a derived kind"**. Product changes stopped when the permanent F probe hit it.

After paired analysis and withdrawal, both invalidated rows retain historical
source text at:

- `research_relationship_analysis.data.validation.evidence[1].quote`
- `research_paired_analysis.data.validation.evidence[1].quote`

The existing list endpoint hides those rows, but storage still contains the copy.
This is distinct from the deliberately retained authoritative snapshot, note and
withdrawn memory. The scanner and failing assertion are preserved. No expected
failure marker or weakened assertion was used to conceal the defect.

Reproduce:

```powershell
uv run pytest -q tests/test_demo01_foundation_probes.py::test_F_paired_lineage_is_scrubbed_and_hidden --tb=short
```

The first I-E2 scanner assertion incorrectly scanned an active historical memory
and its projection after revoking only the *current* grant. That test was corrected
to scan the affected claim dependents. The separate withdrawal scanner still scans
all tables and fails on the two real copies above.

## Evidence and limits

| Checkpoint | Result | Evidence |
|---|---|---|
| Full Windows/SQLite suite before foundation tests and last dispatch/recovery hardening | 304 passed, 6 skipped | [full output](validation/i1-a2/python-before-foundation.txt) |
| Claim runtime on Windows/SQLite, before last dispatch/recovery hardening | 25 passed | Captured local command output |
| Claim runtime on isolated PostgreSQL 18, before last dispatch/recovery hardening | 25 passed | [full output](validation/i1-a2/postgres-claim-checkpoint.txt) |
| Final targeted newer attacks + foundation probes | **20 passed, 1 failed** | [full output](validation/i1-a2/foundation-stop.txt) |
| Existing extension suites | 11 passed | [full output](validation/i1-a2/extension.txt) |
| Ruff on newly authored Python files; diff whitespace check | passed | Local execution |

The full suite was **not** rerun after adding the failing foundation probe and
last dispatch/recovery hardening. Do not present the 304-pass checkpoint as a green
result for this final working tree. Six pre-existing R4 cases are skipped because
their real/synthetic paths are superseded by R5 (one parametrized group of three,
plus three individual tests). No skips were added.

The final foundation assertions cover C-real liability and no double settlement,
D retention/read behavior, E/I-E1 committed pre-marker revocation with no dispatch,
and I-E2 post-marker revocation with no candidate. F remains red.

The raw `docs/i1a_attacks.py` was executed. Its truncated `3.` case prints DEFECT
because its old expected decision was `demoted`; the written review corrects this
to `rejected`, and the permanent assertion uses that correction. The older
`docs/validator_attacks.py` was also executed: it reports unresolved heading and
wrong-method cases, an obsolete duplicate-span expectation, and aborts on the
now-correct rejection of empty schema fields. It is not a passing qualification
harness. The newer permanent attack assertions do not establish real entity binding.

PostgreSQL used temporary per-test databases on a separate loopback-only server;
no existing service or database was modified. No pgvector/capture-v2/Chrome behavior
was qualified. No application schema migration was added or applied; the existing
full-suite migration test operates only on its temporary SQLite database.

External model calls: **0**. All model-shaped responses in the new foundation tests
come from in-process fakes. Runtime tests forbid real provider invocation. Owner
consent and grants existed only inside synthetic test databases. Paid spend: **0**.

## Remaining gates

1. Resolve the derived validation-evidence leak under a follow-up scope that honors
   the review's stop condition, then rerun the all-table scanner and full suite.
2. Review the local changes independently; Claude's supplied review covers the
   starting commit, not these uncommitted repairs.
3. Complete pass/fail coverage of all B/R rules and resolve/report the older
   attack corpus against the intended contract. Current entity binding remains
   heuristic, including the utcnow/utcfromtimestamp distinction.
4. Qualify actual pinned capture-v2 source fixtures, rendered quote identity and
   native Chrome later. The four map entries here are explicitly synthetic.
5. Run the added foundation probes on PostgreSQL after the stop condition is
   resolved; only the 25-test claim-runtime suite was run there.

**I1-A ready for I1-B: NO. I1-A2 ready for I1-B: NO. Keep any follow-up PR draft.**
