# L2-01 — Interpretation contract and role

## `alive-intent-interpretation/v1` (strict; unknown fields are refused)

| Field | Bound | Meaning |
| --- | --- | --- |
| `explicit_goal` | 1–1000 chars | the owner's words, copied unchanged; compared by code |
| `primary_objective` | ≤300 | the higher-level outcome the goal serves (model inference) |
| `intent_kind` | enum | `inspect_implementation`, `compare_claims`, `assess_claims`, `explore_arguments`, `unclear` |
| `subordinate_objectives` | ≤6 | `{objective ≤120, rationale ≤300}` |
| `evidence_requirements` | ≤8 | `{requirement, importance: required/recommended/optional, status: observed/not_observed/unknown}` |
| `assumptions`, `alternative_interpretations`, `ambiguities`, `missing_information`, `limits_of_available_procedures` | ≤5 / ≤4 / ≤5 / ≤5 / ≤4 items of ≤300 | uncertainty and honest gaps |
| `candidates` | ≤5 | `{recipe_id ≤64, recipe_version ≤32, addresses: fully/partly/tangential, relevance ≤300}` |
| `needs_clarification`, `clarification_question` | bool, ≤300 | only when no useful read-only recommendation is possible |

There is no field that can carry a command, path, permission, credential or approval. The role
contract digest the owner approves covers the instructions, this schema and the context policy
`alive-intent-context/v1`.

## What the model receives

The instructions (goal preservation, untrusted data, no tools, catalogue-only names, abstention is
valid), then JSON data: `user_goal` verbatim; `source` (type, label, classification, file names and
sizes, `content_included: false`); the catalogue projection (id, version, name, description,
context types, task intents, evidence needed, what it produces, whether it needs a model or sends
data to the provider, permissions); the catalogue digest. The projection comes from the trusted
YAML recipes, never from the source.

## Stored recommendation `alive-intent-recommendation/v1`

`status` is one of `recommended`, `no_executable_recommendation`, `clarification_needed`,
`rejected_interpretation`. The record carries `original_goal`, `goal_preservation`, the source
reference and digest (`content_sent: false`), `catalogue_sha256`, the interpreter identity
(role, contract digest, model, endpoint, admission, review digest, run, invocation, usage),
the interpretation labelled `model_inference`, the resolution labelled `trusted_system`
(per proposal: `eligible`, `ineligible`, `unknown_recipe` or `wrong_version`, with reasons),
`recommendation`, `alternatives`, `unavailable`, `also_eligible_not_proposed`, `uncertainty` and
`authorization` (`execution: not_authorized`, the profile a separate review would use).
