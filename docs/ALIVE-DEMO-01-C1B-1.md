# ALIVE-DEMO-01 C1B-1 — Owner-selected reliance anchors

**Status: draft engineering candidate; no tests executed in this session.**

## Implemented
- Strict `POST /api/v1/browser-experience/research/memories/{memory_id}/anchor` request.
- Compare-and-swap via expected source SHA-256 and expected anchor revision.
- Exact excerpt quote (16–300 characters), rejects Unicode control and formatting characters, refuses withdrawn and in-flight sources.
- Detects ambiguous duplicate occurrences and permits explicitly selected code-point offsets.
- Saves `reliance_anchor` in the authoritative existing research-memory row, with offsets, hash, revision, and timestamp.
- Re-anchor invalidates consent-lineage dependents already bound to an earlier anchor revision, in the same database transaction.
- Withdrawal scrubs anchor quote but preserves non-content provenance.
- Adds initial API-level regression tests.

## Qualification required
- Run `uv run pytest tests/test_demo01_c1b_anchor.py -q` and full suite. Confirm fixtures use sentence-bounded quotes; revise tests only for fixture mistakes, never weaken the source/auth checks.
- Add tests for every Gate 1 case in the owner-supplied Claude C1B review: duplicates, explicit offset, malformed Unicode, normalization, concurrent revision updates, in-flight refusal, and restart.
- Review error mapping: current service raises `ValueError` for stale/ambiguous/withdrawn cases, and generic API exception mapping may differ from the proposed 409/422 contract. Align response codes before merging.
- Check that every old-revision dependent kind is invalidated, and that attempts already in flight settle without hiding liability.
- Check that no readable retained anchor quotation survives withdrawal.
- Independently verify behavior on SQLite/PostgreSQL and Windows; currently not run.

## Not yet implemented
This is **C1B-1 only**, not the complete three-slice C1B requested by Claude. Validator v2, eight claim-mode inference seams, code-gated Meta disablement for claim mode, capture-v2 observer and fixture corpus are **not** part of this PR. Do not claim claim-comparison runtime readiness.

## Safety boundary
No Meta calls, spend, permission changes, new tables, schema migrations, or ALIVE-14 modifications. Keep draft; obtain independent review and test qualification before merging.
