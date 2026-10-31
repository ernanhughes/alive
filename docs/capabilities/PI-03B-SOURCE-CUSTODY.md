# PI-03B source custody

Source custody answers one question at the moment a stage runs: **may this stage read these exact
bytes, for this operation, now?** Implementation: `alive/sources/` and migration `0013`.

## Three facts, kept apart

| Fact | Record | What it means | What it does not mean |
| --- | --- | --- | --- |
| **Capture** | `source_captures` (immutable) | These exact bytes were read by trusted host code. Identified by a SHA-256 over the canonical content. | Not approved. No workflow can read it. Not true. |
| **Approval** | `source_approvals` | The owner decided that *this digest* may be read by *these capability ids*, within *this scope*, until *this time*. | Not a workflow grant. Not a claim the content is correct. |
| **Use** | `custody.resolve`, at each stage start | Every condition below holds *right now*. | A grant minted earlier proves nothing about now. |

A capture and an approval are never edited. The only change to an approval is a one-way
withdrawal. Deletes are refused by the ORM; downgrading migration 0013 discards custody by design
(see the security document).

## Source types and what a capture holds

| Type | Captured by | Content stored | Classification |
| --- | --- | --- | --- |
| `repository` | `prepare repository` | Files (path, content, sha256, bytes) and omissions with a reason. The host path is **not** stored. | `owner_internal` |
| `document` | `prepare document` | Parsed sections (heading, text, sha256, line range), raw digest, parser identity. | `owner_internal` |
| `browser` | `prepare browser` | Sections of an already-captured observation, origin, title, observation event id, raw digest. | `untrusted_browser` (enforced) |
| `collection` | `prepare collection` | Memory ids and content hashes only. **No content is copied.** | `owner_internal` |

Limits: a capture is at most 512 KiB of canonical JSON; a repository capture at most 256 files and
400,000 content bytes; a document at most 256 KiB raw, 512 sections, 32,768 characters per section.
Over a limit is a refusal, never a quiet truncation (a section cut at 32,768 is flagged, and the
capture says so).

## Approval

An approval states: the capture id, the **digest the owner restates** (it must equal the stored
digest, which is recomputed from the stored content first), a list of capability ids (1-8), a scope,
and a time to live (60 seconds to 30 days). The scope is either `{"all": true}` or
`{"items": [...]}` naming captured items (repository paths, section indexes, memory ids). An item
that was never captured is refused.

Approval is idempotent by `request_id`: the same id with the same terms returns the same approval;
the same id with different terms is a conflict and creates nothing. If two processes race on the
same id, the database's unique constraint decides and the loser returns the winner.

## Use: what `resolve` checks, in order

1. `resources` has exactly `source_ref`, `approval_id`, `content_sha256`, `scope_sha256`
   (`source_resources_required`).
2. The approval and capture exist and belong together (`source_approval_missing`).
3. Both belong to this instance (`source_instance_mismatch`).
4. Not withdrawn (`source_withdrawn`) and not expired (`source_approval_expired`).
5. The operation (the capability id being run) is in the approval (`source_operation_not_approved`).
6. Approval digest = capture digest = the grant's digest (`source_digest_mismatch`).
7. Approval scope hash = the grant's = a recomputation (`source_scope_mismatch`).
8. The stored content still hashes to its recorded digest (`source_content_changed`).

Then the content is narrowed to the scope. Items outside it are **absent**, including their
omission records. The runner additionally refuses a source whose type the capability does not list in
`supported_source_types` (`source_type_not_supported`) and a stage input `source_ref` that is not the
source the grant names (`source_ref_not_approved`).

Collections are materialised here: the approved memory ids are read from the live table (this
instance only) and any memory whose current content no longer hashes to the approved digest is
returned as `omitted: changed_since_approval`, never substituted.

**Time of check.** Custody is verified when the stage starts. A withdrawal that arrives while a
stage is already running does not interrupt that read, exactly as revoking a grant does not
interrupt a running stage. Stages are bounded to 30 seconds.

## The owner CLI

`python -m alive.sources` is a local operator command. It adds no network route, never starts the
runtime (it does not call `Kernel.initialize`, which takes the database ownership lock), refuses a
database ALIVE has never started against, and records the operating-system user as `owner-cli:<user>`.

```
prepare repository --root R --label L (--all | --path P ...)   capture a candidate
prepare document   --file F --label L                          text, Markdown, HTML (not PDF)
prepare browser    --event-id E --label L                      an observation already captured
prepare collection --label L [--limit N] [--query Q]           freeze memory ids and hashes
list | inspect ID | approvals [--capture ID]
approve ID --confirm-sha256 D --operation OP ... (--all | --item I ...) [--ttl-hours H] [--request-id R]
withdraw APPROVAL_ID --reason TEXT
```

`prepare` prints the digest and a content-free inventory and says plainly that the result is a
**candidate**. `approve` requires restating the digest, so an approval cannot attach to content
that changed after it was inspected.

## What custody does not do

It does **not** mint a workflow grant. A grant also needs an authorised investigation and context
provenance, which today exist only for the controlled laboratory and for untrusted browser events.
Wiring "owner approves a source, then runs a workflow" for live use is a separate admission gate
that needs its own security review (see the security document). `approval["resources"]` is exactly
what an owner grant carries for a stage that reads the source.
