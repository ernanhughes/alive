# ALIVE-DEMO-01 C1A — Claim comparison contract and validation

**Status:** isolated implementation candidate, not integrated into inference/Chrome; review before merging.

## Context
PR #31 (C0) is merged. Claude's independent PR-C review explicitly required C0 before C1 and recommended a claim comparison mode on the **normal** history-assisted `analyze()` path, never the bounded ALIVE-14 experiment path. This first C1 increment isolates the validator and schema so its behaviour can be independently qualified before changing any dispatch code.

## Implemented
- Strict Pydantic `ClaimComparisonOutput` schema with six conservative relationship labels.
- Local deterministic exact-source quote, cross-source ambiguity, sentence-boundary and asymmetric-negation checks.
- Reliance-anchor overlap demotion when a future anchor is provided.
- Same-scope requirement for a `conflicts` label.
- An explicit source-stated basis requirement before `explicit_supersession` is accepted.
- Low-confidence, nonassertive abstention.
- Rejection and demotion do not produce an alert.
- Initial unit tests for acceptance and failure cases.

## Not yet delivered
- Reliance-anchor endpoint and its revision/offset binding.
- Real Python documentation mirror and provenance manifest.
- Full positive/negative matrix for every validator rule, including edge cases.
- `claim_comparison` API mode, owner consent preview/hash, and storage of the validated result.
- Local fixture model stub and adversarial outputs.
- Live Meta call, UI change, or any campaign work.

## Qualification
Run `uv run pytest tests/test_claim_comparison.py`, the full backend suite, and have Claude review limitations of deterministic sentence checks in real document extraction. No paid inference has been run.

## Follow-up C1B design
Only once this contract passes review, wire the new `claim_comparison` mode through the established ordinary relationship route, add an owner-anchored exact passage and fixture provenance, preserve C0 consent-lineage withdrawal and cost protections, and write integration tests proving no post-withdrawal model outputs appear on any read path. Keep a separate draft PR to isolate inference-path safety.

This is not yet a feature users can invoke: it is an independently reviewable **validator foundation**.
