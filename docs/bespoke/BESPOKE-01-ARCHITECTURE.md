# BESPOKE-01 architecture

Starting point: integrated main `495e4fedaeacedbec33e94b77a485c26dd792a34`.

The selector recommends an existing versioned workflow. It never invokes a capability,
registers a workflow, creates a grant, dispatches Pi, or changes Intelligence rankings.
The only public write is a bounded recommendation record.

## Existing foundations and decisions

| Foundation | Reused behavior | Boundary |
| --- | --- | --- |
| `capabilities/manifest.py` | Restricted YAML reader, strict types, canonical JSON | YAML cannot import implementations |
| `CapabilityRegistry` | Exact identities, deployment limits, implementation fingerprints | Availability is not owner permission |
| `workflows/spec.py`, `store.py` | DAG contracts, registration, immutable versions | No second workflow-definition system |
| `WorkflowCapabilityBinding` | Registration receipt, stage identities and snapshot hash | Historical contracts cannot upgrade |
| `workflows/context.py` | Existing scoped grants, provenance, revocation, source withdrawal | No grant-minting HTTP endpoint |
| `WorkflowRunner` | Admission, budgets, runtime rechecks, execution, retained outputs | Selection does not start it |
| Cognition / Governor | Goal, inquiry, configuration and resource ownership | Intent remains explicit user input |
| Model gateway / Pi | Existing governed model dispatch | Not called by selection |
| Intelligence | Existing independently evaluated feedback and learning | Completion is not a success label |
| Observatory / `WorkflowGraph` | Graph preview and inspection of real linked runs | History performs authenticated reads only |
| Extension | Existing browser observation custody | No URL fetching, extension authority or extension changes |

The PI-03A review records describe a synthetic owner-grant harness, not a qualified production
source-consent interface. PI-03B and PI-03C remain unimplemented. The browser can observe a page;
it cannot establish its truth, choose the user's intent, approve a source, or mint a grant.

## Flow

1. Load the code-owned recipe catalogue at application construction, through PI-03A's reader.
2. Resolve a captured source through an existing live owner grant; verify instance, goal,
   inquiry, source hash, provenance, revocation, and configuration with the existing validator.
3. Derive repository custody from a real approved host capture using `reader_for`, or retain
   controlled-evidence / untrusted-browser custody. Do not classify URLs or page titles.
4. Match explicit intent; an unspecified intent yields abstention and inspectable alternatives.
5. Independently gate each recipe, then score only eligible candidates.
6. Persist the complete bounded result and a compact event receipt in one transaction.
7. Display retained candidate graphs, pins, reasons and uncertainty in Bespoke.
8. A trusted laboratory host can revalidate a recommendation against a separately created
   exact grant. It then calls the existing runner. The dashboard has no execution control.
9. The handoff receipt connects recommendation identity to real scoped Observatory runs.

The implementation uses cohesive `contracts`, `recipes`, `context`, `selector`, `models`,
`store`, `handoff`, and `api` modules. Eligibility and scoring are separate functions/blocks
within one bounded selector; there is no extra service or agent framework.

## Durability and ownership

Migration 0012 adds `bespoke_recommendations`, with instance, trusted grant principal, existing
goal/inquiry/source references, a scoped unique retry key, request hash, selection hash,
timestamp and immutable JSON snapshot. ORM updates/deletes are refused; reads verify the hash.
Database administrators remain trusted, as for existing workflow records; hashes are not signatures.

The deployment has one bearer-authenticated owner per instance, not a multi-user identity service.
Principals originate in trusted grants, never in request fields. Public history is instance-scoped;
handoff additionally checks the original principal and exact goal/inquiry/source context. A future
multi-owner service must map authenticated identities before exposing this API to multiple owners.

Idempotent requests with identical scoped keys and content return the retained record while source
approval is still valid; conflicting content is refused. Historical GET works after expiry,
withdrawal, catalogue retirement or restart. It neither re-ranks nor executes an old selection.

## Deliberate deployment limits

The shipped startup workflow remains the original draft `research-review` v1. This milestone does
not silently activate laboratory procedures in production. The three real recipe examples pin
the already implemented controlled `source-comparison` v1, `research-review` v2 and
`repository-inspection` v1 contracts. They are unavailable until those exact definitions have
been registered by trusted host code. The demonstration registers them through the existing
workflow API in-process, not through a public upload route.

Production selection additionally needs approved captured context. There is no qualified
production approval route; the UI accurately shows empty context and unavailable authorization.
The complete selector and controlled execution path can be exercised now. Broad live browsing,
document extraction, semantic verification, adaptive composition and policy learning cannot.
