# ALIVE-INTEL I1-A — Claim foundation repair (partial implementation)

**Status: DRAFT / NOT READY FOR MERGE.** This PR implements the first validator-and-anchor portion of I1-A, not the complete claim-mode runtime.

## Based on
Claude's independent `ALIVE-INTELLIGENCE-01-CLAUDE-REVIEW.md` at main `88cd0be`. It calls for a conservative validator v2 before any Think-cycle work. This branch was created from current main; do not assume the baseline is unchanged without checking.

## Changed here
1. Versioned v2 output model and local validation logic in `alive/claim_comparison.py`. Exact spans, chosen offsets, source-presence annotation, conservative negation and qualifier checks, explicit-supersession basis and anchor shape are implemented as a draft.
2. `ResearchMemory.anchor` now passes the selected occurrence offset to the boundary validator, rather than silently validating the first instance.
3. Initial pure deterministic tests for historical passages unchanged in a newer source, negation, duplicate occurrences, and abstention.

## Critical gaps — remain blocking
- Eight integration seams through `ResearchRelationships` are **not yet connected**: mode whitelist, payload / exact consent hash, instructions+schema, ordinary dispatch parse/validation, source and settlement rechecks, storage, reuse, listing.
- No `local_fixture_claim` provider or code-level paid-model lockout for claim mode yet.
- Anchor HTTP error mappings remain unchanged, and capture-v2 has not landed.
- The nearest-marker heuristic in the draft validator is **not a sufficient entity-binding check**. The `utcfromtimestamp` wrong-method attack remains a blocker; reject/demote until the actual subject-heading section can be bound.
- No durable foundation probe suite or full E2E flow yet. Existing C1A tests may require intentional revision with stronger assertions, not weakened expectations.
- No test suite or Python syntax execution was available through this GitHub-only editing session. All tests, including the new ones, are **UNRUN**.

## Reviewer / implementer gates
Use Claude's `ALIVE-INTELLIGENCE-01-CLAUDE-REVIEW.md` §12 as the I1-A contract. Resolve every gap above before merging. Run `uv run pytest -q`, `node --test`, adversarial cases, C-real/D/E/F, anchor status/occurrence tests, and claim-mode end-to-end tests. Report exact counts, skips, baseline/head SHAs and provider-call count (zero).

**No** real Meta calls, consent grants, changes to ALIVE-14, migrations, new Chrome permissions, or intelligence-cycle implementation were performed here.

**I1-A ready for I1-B: NO.**
