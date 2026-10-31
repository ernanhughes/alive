# PI-03C — validation architecture and implementation audit

Baseline: `4e990bfadb886eba933a88f1c07e1b2543ab8f02`, verified against remote main.
Branch/worktree: `codex/pi-03c-validation`, `C:/Projects/alive-pi03c`.
PR #83 is a separate unmerged security dependency. Its authorized CI correction is on
`b2f39251ca6915e847133214179be799ec068f58`; no security fixes are copied here.
Only deterministic PI-03C is authorized for this milestone. No L2 implementation.

## Verified implementation matrix

| Existing feature | Verified behavior | Missing behavior | Reused API / change | Security and qualification |
| --- | --- | --- | --- | --- |
| PI-03A registry | Versioned YAML, immutable bindings, trusted fingerprints and exact grants | General validation operations | New reviewed implementations/manifests; retain existing versions | Registry, version, hash and permission regression tests |
| PI-03B custody | Instance, approval, capture digest, scope, expiry and withdrawal checks | General reference/locator consumers | `custody.resolve`, `ApprovedSource`, narrow read context | Never read filesystem/network; actual approved captures in runner tests |
| Source adapters | Stable source ids, repository files, document/browser sections, memory items | Validation classifications | Reuse `source_id`; consume exact captured content | No invented PDF/page identity; unsupported page outcome |
| L1-02 citation checks | Repository line bounds and normalized quotation checks | General source types and explicit exact quotation policy | Reuse line-bound checker; new versioned quote policy, leave old code unchanged | Matching locator is not semantic verification |
| WorkflowSpec / WorkflowRunner | DAG type checks, trusted registration, scoped grants, cancellation, retained stage outputs | New deterministic compositions | Existing runner and per-stage approved source resources | No generated code, no new executor or registration API |
| Result recording | Requires exact output of a real validation dependency | Composed validation reports | New composer checks actual dependency output; existing `result.record` persists | Caller-provided status cannot impersonate a validator |
| Observatory / dashboard | Existing graph, stage outputs, artifacts and validation status | PI-03C record vocabulary | Existing views expose structured reports | No separate reporting store or dashboard |
| Bespoke | Deterministic eligibility and immutable recipes | LLM interpretation/composition | Unchanged; later L2 roles use qualified model boundary | No keyword substitute for semantic reasoning |
| Pi / ModelGateway / Governor / owner admission | Existing bounded analyst and exact owner/source reviews | Security acceptance and generalized research role | No new model client or invocation in this branch | Model-backed research qualification blocked on PR #83 review |
| Intelligence | Independent feedback and retained execution receipts | Live outcome evaluation | No changes | Completion/citation validity never becomes task success |

## Planned deterministic contracts

Upgrade the existing `evidence.validate_references` identifier to a separately pinned 1.1.0;
the programme's hyphenated spelling is descriptive, not a duplicate operation. Add
`evidence.verify-locators`, `evidence.compare-claims`, and `report.compose` through the existing
trusted table. No manifest can install its own implementation or acquire extra permissions.

Reference/locator stages receive a custody-checked captured source, verify the exact source and
scope digests, and classify each citation. Comparison and composition consume only records
equal to actual trusted dependency outputs; arbitrary findings cannot certify themselves.
Comparison may join two independently approved captured sources through two validator stages.
Reports preserve findings and provenance, omissions, unsupported references and uncertainty.

All records separate schema, structure, reference identity, locator validity, semantic support,
independent verification and task outcome. Semantic support stays unverified, independent
verification is false, and task outcome is unknown. Deterministic equality proves only the
declared controlled comparison. No model assessments are fabricated in this branch.

Repository and captured-document deterministic paths, plus two-source comparison, can be
qualified now. The required authorized-Pi research path remains a named incomplete exit gate
until the final transport and its owner-admission contracts qualify. A deterministic document
path is not reported as a completed model-backed research workflow.
