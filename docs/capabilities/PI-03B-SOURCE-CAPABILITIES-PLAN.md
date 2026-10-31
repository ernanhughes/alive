# PI-03B plan: source and retrieval capabilities

Not started. Requires PI-03A review authorization. Each item is a manifest plus one reviewed
trusted implementation; no runner, router or dashboard edits.

## Prerequisite: host snapshot custody (carry-over from PI-03A)

PI-03A can only receive repository content through `create_app(capability_registry=...)`.
Before any new source capability, design how an operator approves a source: an authenticated
owner step that records the captured content digest, scope and consent as an owner event, then
mints the run grant. Without this, source capabilities stay test-only. Decision needed from the
owner: whether approval is an API route, a CLI step, or part of the existing owner-grant harness.

## Capabilities

| Capability | Source | Key bounds | Provenance in output |
| --- | --- | --- | --- |
| `repository.inspect` v1.1 | Extend the PI-03A capture: directory listing of approved paths, Git object ids when available | Listing size, depth, no new filesystem authority | Capture digest, per-file hash, omissions with reasons |
| `retrieval.approved-collection` | Existing approved memory/evidence collections via the established reader | Item count, bytes, collection id from the grant | Source event ids, retrieval timestamp |
| `browser.prepare-source` | A page already captured by the browser extension, by observation id | Bytes, text only, consent classification | Observation id, origin, content hash, consent class |
| `document.extract` | A host-captured document with a page-bounded parser | Pages, bytes, parser version in fingerprint | Document hash, page/section locator, parser identity |

## Rules inherited from PI-03A

- Content is captured and approved by trusted host code; stages receive immutable readers.
- Retrieved is not extracted is not cited is not verified; keep those statuses distinct and never
  write retrieval results into independently observed evidence or learning records.
- Outputs are closed contracts with explicit truncation (never silent).
- A parser dependency is part of the implementation fingerprint and needs its own review.
- No network, shell or arbitrary filesystem authority.

## Tests to add

Per capability: contract and bound tests, hostile-input tests (oversize, malformed, encoding),
a real `WorkflowRunner` execution, refusal without an exact grant, tampered-manifest refusal,
cancellation between bounded reads, catalogue visibility, and a mutation set for the new guards.
POSIX coverage for the repository reader must be added (CI runs on Linux).

## Exit criteria

Draft PR with focused tests, mutation receipts, and an independent review of every new
implementation's fingerprinted source.
