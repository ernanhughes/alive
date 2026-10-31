# PI-03B architecture: governed source capabilities

PI-03B only. It stops at independent review. PI-03C (validation and composition) and the Bespoke
selector are not started here, and nothing in this change depends on either.

Principle, unchanged from PI-03A: a manifest defines a contract; reviewed code implements it; the
registry decides availability; the existing `WorkflowRunner` executes it; an exact owner grant
decides authority. PI-03B adds no agent framework, plugin runner, model gateway, evidence store
or orchestration engine.

## Baseline matrix (audited before any code)

| Capability | Existing implementation | Governed adapter | Manifest | PI-03B work |
| --- | --- | --- | --- | --- |
| Repository inspection | `capture_repository`, `RepositoryReader` (PI-03A) | `inspect_repository` (v1) | `repository.inspect@1.0.0` | `@1.1.0`: database-backed custody, list and read, item scope. `1.0.0` stays for pinned definitions. |
| Memory retrieval | `MemoryService.retrieve` (searches all memories) | none | `memory.retrieve@1.0.0` (unavailable) | New `retrieval.approved-collection` over an owner-approved id/hash set. `memory.retrieve` is untouched. |
| Browser observations | `Browsers.observe` and the extension write `browser.page_opened` / `browser.dom_changed` events | none | none | `browser.prepare-source` over an observation already captured. No fetching or navigation. |
| Document parsing | none (`beautifulsoup4` present, no PDF library) | none | none | `document.extract` for text, Markdown, HTML. **PDF is unavailable** (no reviewed parser dependency). |
| Evidence qualification | `EvidenceQualifier` | none | `evidence.qualify@1.0.0` (unavailable) | Not PI-03B. |
| Reference validation | `alive.society.validate_references` | `validate-references-v1` | `evidence.validate_references@1.0.0` | Not PI-03B (PI-03C). |

Nothing existing was rebuilt. The only shared-core changes are listed under "Integration surfaces".

## Flow

```
owner machine                       database                         workflow runtime
-------------                       --------                         ----------------
prepare ──capture builder──────────► source_captures (immutable)
inspect (digest, inventory, no content)
approve --confirm-sha256 ──────────► source_approvals (digest, ops, scope, expiry)
                                     source.* events (decisions, no content)
owner grant (existing, trusted) carries approval["resources"] for the stage
                                                                      stage starts
                                                                      custody.resolve ──► re-check all facts now
                                                                      adapter(ApprovedSource) ──► typed output
                                                                      existing output contract + persistence
```

Untrusted bytes are parsed once, at capture time, by the trusted host, so the owner approves what
was actually extracted. No stage parses untrusted input, holds a database handle, a path or a
credential. Adapters are pure functions of an already-verified, already-scoped `ApprovedSource`.

## The capabilities

| Id | Implementation | Reads | Notable guarantees |
| --- | --- | --- | --- |
| `repository.inspect@1.1.0` | `repository-inspector-v2` | `repository` | List or read; a path outside the approval is **refused**, not skipped; per-call byte limit from the grant. |
| `document.extract@1.0.0` | `document-extractor-v1` | `document` | Windowed sections with locators; `complete` is true only if everything in scope was returned untruncated; refuses a different parser build. |
| `browser.prepare-source@1.0.0` | `browser-source-v1` | `browser` | Text is inert data; `trust.content_is_instructions` is the constant `false`. |
| `retrieval.approved-collection@1.0.0` | `collection-retriever-v1` | `collection` | Live read; changed memories omitted; ordering is a term count and says it is not a relevance or truth score. |

All four: deterministic, side effects `read`, `persistence: none`, `network: none`, `process: none`,
`filesystem: none`, and a new permission class (below). Outputs are `semantic_status: unverified`
(a one-value enum in the contract) and validation status `not_run`: retrieval is not verification.

## Integration surfaces (shared core, narrowly changed)

1. **`permissions.sources: approved_capture`** (bit `source.read`). A manifest field with a default,
   omitted from the canonical form while unset, so **every earlier manifest keeps its exact hash**.
   A test pins all ten earlier hashes. Declaring it requires an implementation whose compiled ceiling
   includes `source.read`.
2. **`execution.invoke`**: for `source.read` it calls `custody.resolve` at the moment the stage runs,
   checks the source type against `supported_source_types` and that the stage input names the
   approved source, and passes the grant's limits to the adapter. `ReadCapabilityContext` gained
   `inputs` and `limits` (PI-03A review item F17).
3. **`registry.check_grant`**: a grant may carry resources for `repository.read` or `source.read`.
4. **`capture_repository`** accepts larger explicit ceilings (256 files, 400,000 bytes); defaults
   are unchanged for PI-03A callers.
5. **Migration 0013** (two additive tables). Migration-head assertions moved to `0013`.

The runner, the router, the dashboard and `app.py` are unchanged. The new capabilities appear in
the existing Capabilities pane through the registry.

## Upgrade behavior

`repository.inspect@1.0.0` and `@1.1.0` coexist with different manifest hashes and implementations.
An **unpinned** stage resolves to the newest version when the definition is registered, so the
PI-03A fixture pins `capability_version: "1.0.0"`. Pinned definitions keep their identity.

## Not in PI-03B

PDF extraction; OCR; fetching or crawling; a way for the owner to mint a workflow grant for a live
source (see the security document); validation, locators, claim comparison and reports (PI-03C);
any selection logic (BESPOKE-01).
