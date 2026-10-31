# Recipe schema: bespoke recipe v1

`alive/bespoke/recipes/*.yaml` is a code-owned catalogue, not an HTTP upload directory.
Unknown keys, implicit executable tags, aliases, anchors, merge/duplicate keys, interpolation,
excessive depth, controls and oversized input are rejected by the PI-03A reader.

Each declaration contains:

| Field | Meaning |
| --- | --- |
| `schema_version` | Exactly 1 |
| `id`, `version`, `name`, `description` | Bounded declarative identity and escaped display data |
| `context_types`, `intents` | Explicit applicability sets; no page-derived instructions |
| `workflow` | Exact name, integer version and canonical definition SHA-256 |
| `capabilities` | One exact stage ID, capability ID, version and manifest hash for every workflow stage |
| `limits` | Model calls, wall seconds, output tokens, outbound request and permission classes |
| `required_evidence` | Approved capture or controlled claims and sources |
| `output_artifact` | Captured files or an existing workflow result |
| `validation` | None, controlled comparison or reference identity; never semantic truth |
| `status` | Active, deprecated or future; only active can pass eligibility |
| `presentation` | Existing strict category/icon/tags contract |

The reader normalizes set ordering and stage pin order. Canonical JSON uses the existing
`json_bytes`/digest functions. The recipe's hash covers all declarative fields. Recipes pin
workflow and manifest identities; each selection additionally retains the binding hash,
implementation fingerprints and effective capability policy hashes from registration.

Changing a recipe creates another canonical identity. Use a new version for published changes.
Duplicate ID/version pairs in one catalogue fail startup. The catalogue is a sealed startup
tuple with no hot reload or arbitrary registry mutation route. Retained records embed the old
recipe snapshot and remain readable even when it disappears from the live catalogue.

## Real examples

| Recipe | Existing execution contract | Honest limitation |
| --- | --- | --- |
| `captured-repository` v1.0.0 | `repository-inspection` v1: one bounded `repository.inspect` | Captured files, not a correctness/security review |
| `controlled-comparison` v1.0.0 | `source-comparison` v1: prepare → compare → record | Controlled source comparison, not truth in the world |
| `bounded-evidence-review` v1.0.0 | `research-review` v2: prepare → model → check references → record | Requires Pi, model authority, outbound permission; semantics unverified |
| `scientific-document` v1.0.0 | Future template with missing `document.extract` | Always unavailable; zero hashes are explicit placeholders |
| `discussion-source` v1.0.0 | Future template with missing `browser.prepare-source` | Always unavailable; no invented browser retrieval |

The corresponding reviewed workflow JSON examples are in `docs/bespoke/workflows/`. Registration
uses existing `register_definition`; recipes cannot register them. Empty/future catalogues are valid.

## Context and rationale contracts

`bespoke-context/v1` distinguishes source custody, explicit objective, constraints and inferred
intent (currently always absent). Source text is never copied into instruction fields. The
request is a strict bounded `RecommendRequest`; the resolved `ObservedContext` is separately
validated against actual approved event/grant state.

`bespoke-rationale/v1` retains context identity, explicit objective, constraints, recipe snapshot,
workflow and binding identities, capability policies, eligibility reasons, suitability factors,
alternatives, graph, uncertainty, policy identities and procedural diversity. Authorization is
`unavailable`; outcome and independent feedback references remain empty until a separate governed
integration supplies them. No model reasoning trace is retained.
