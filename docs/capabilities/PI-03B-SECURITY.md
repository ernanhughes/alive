# PI-03B security model and honest limits

Builds on `PI-03A-SECURITY.md`. Capability implementations are still trusted, reviewed, in-process
Python and are not sandboxed. PI-03B adds a custody layer between *the owner's intent* and *what a
stage may read*.

## Threats and controls

| Threat | Control | Test |
| --- | --- | --- |
| Source changes after the owner looked at it | Approval is bound to the digest the owner restates; the stored content is re-hashed at approval and at every use | `test_content_changed_underneath_the_application_is_detected`, PostgreSQL tamper check |
| An old grant outlives the owner's decision | Withdrawal, expiry, operation, scope and digest are re-checked when each stage starts, not when the grant is minted | `test_custody_is_rechecked_at_dispatch_not_when_the_grant_was_minted` |
| A model, page or extension approves its own source | There is no route, tool or event that approves a source. Approval is a local operator command that needs the digest restated | `test_the_owner_flow_prepare_inspect_approve_withdraw` |
| A bearer token widens authority | Nothing in the API writes custody. The token reads the catalogue and run history only | catalogue API write-surface tests |
| Substitution between sources | The stage input `source_ref` must equal the granted source; the digest and scope hash must match the grant | `test_a_stage_cannot_name_a_different_source_than_the_one_approved` |
| Read outside the approved scope | Items outside the scope are absent from the content the adapter receives; a requested path outside it is refused, not skipped | `test_repository_refuses_every_out_of_scope_read` |
| Another instance's source | Every custody read is instance-scoped, including an internally consistent foreign approval | `test_custody_is_instance_scoped` |
| Path traversal, links, hardlinks, FIFOs, devices | Capture uses the PI-03A hardened reader (no-follow opens, non-blocking, regular-file check, hardlink refusal, Windows device names refused). At run time no filesystem is touched | `test_source_capture.py`; Linux container run |
| Secrets in the tree | `.env`, key and credential names, `.git`, `node_modules` and `.gitignore`d paths are never opened and appear only as omissions with a reason. The host path is never stored | `test_repository_capture_omits_secrets_...`, CLI test |
| Prompt injection in page text | Page text is returned as data. `trust.content_is_instructions` is the constant `false`; adapters interpret nothing; the capability cannot change authority, permissions or selection | `test_browser_text_is_returned_as_inert_untrusted_data` |
| Malicious documents | Parsed once at capture, on the host, with size, section and nesting bounds; NUL/bad UTF-8/oversize/deep nesting each get a named refusal; scripts, styles, comments and hidden text are dropped; control and bidi characters removed | `test_hostile_documents_are_refused_...` |
| A parser upgrade silently changes what was approved | The capture records the parser identity; the adapter refuses a different build until re-captured and re-approved | `test_a_changed_parser_build_requires_recapture` |
| Content leaks on the generic feed | Stage output is withheld from the REST/WebSocket feed (PI-03A); custody events carry digests and decisions, never content | `test_source_content_never_reaches_the_generic_feed...` |
| Retrieval presented as truth | Outputs are `semantic_status: unverified` (a one-value enum) and validation status `not_run`; ordering says it is a term count, not relevance or truth | contract + mutation S21 |

## Why a local command is the approval mechanism

The alternatives were a network route or a local owner UI. A route would add a write surface to
the API that anything holding the bearer token could use, which is exactly the authority creep the
design avoids. A local command acts with the rights of the person at the machine, which is the trust
ALIVE already places in its owner, adds no remote surface, and cannot be driven by a page, model or
extension. The cost is that an approver needs shell access. If a graphical owner flow is wanted, it
should be designed as its own reviewed surface; this change deliberately does not do so.

## Limits you should know about

1. **No workflow-admission path for live use (the main open item).** Custody records the owner's
   decision; it does not turn it into a runnable workflow. A grant still needs an investigation and
   context provenance, which exist today only for the controlled laboratory and untrusted browser
   events. The end-to-end tests therefore use the same trusted fixture owner PI-03A used. Do not read
   "the source capabilities work" as "a user can approve a file and run a workflow on it today".
2. **Owner identity is the local operating-system user plus database access.** Approvals are not
   cryptographically signed. A process with write access to the database can forge an approval, as it
   can already forge a grant. The recorded principal is `owner-cli:<user>`.
3. **Time of check.** Custody is verified when a stage starts; a withdrawal during a running stage
   does not interrupt it (stages are bounded to 30 seconds).
4. **Captures are not atomic filesystem snapshots.** A file can change while being read; the
   mtime/size/inode recheck narrows this. Outputs state `atomic_repository_snapshot: false`.
5. **Content is stored unencrypted in the database, with no retention period and no deletion path.**
   Captures are immutable evidence; withdrawal blocks use, it does not erase. Treat the database as
   holding the approved source content. Run history also retains stage output (PI-03A retention note).
6. **PDF is unsupported.** There is no reviewed PDF parser dependency. Adding one is a supply-chain
   decision for the image and lockfile, not something to guess at inside a capability.
7. **HTML is parsed with the lenient `html.parser`.** It does not load resources or run scripts, but
   it is not a conforming browser parser. The parser identity covers `documents.py` and the
   `beautifulsoup4` version, not every transitive dependency.
8. **Collection ordering is a term count.** It is deterministic and honest about being a count; it is
   not semantic search and not a relevance score.
9. **Browser capture trusts the stored event.** Anyone holding the API token can already post an
   observation. The owner chooses which event to capture and inspects its inventory, the capture is
   forced to `untrusted_browser`, and approval is still the owner's. Authority does not widen.
10. **Fingerprints are not transitive** (PI-03A F18); the new implementations list the files that
    define their behavior, including `custody.py`.
11. **Platform coverage.** Windows 11 host plus a Linux container for the POSIX behavior. Not run:
    macOS, Windows CI, Docker image build and the Docker smoke test (see the delivery record).
12. **Downgrading migration 0013 deletes custody records** (approvals and captures). Older tables
    are untouched. Do it only knowingly.

## Decisions that need the owner

1. **The live admission gate.** How does an approved source become a runnable workflow for a real
   user? This needs its own design and independent review before any live use.
2. **A PDF parser dependency.** Which library, and is adding it to the image acceptable?
3. **Retention and encryption for captured content.** A retention period, deletion path or
   encryption at rest.
4. **A graphical owner flow**, if the CLI is not acceptable as the approval surface.
