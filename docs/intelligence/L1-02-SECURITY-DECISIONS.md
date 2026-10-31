# L1-02 — Security decisions awaiting the owner

Three questions decide whether L1-02 may be treated as a qualified production foundation. They are
policy choices, not implementation details, so none is decided here. Each lists what the code does
today, the realistic options and a recommendation. Status of all three: **open**.

## 1. Remote-model egress

**Today.** Source code leaves the host only after: a source approval naming the operation
`repository.analyze`, a review that shows the effective HTTPS endpoint, model, files and byte count, the
owner's local confirmation of that exact review, and re-checks at start, reservation and dispatch.
There is exactly one destination (the configured Meta endpoint through Pi's loopback egress). The
egress builds the upstream request from the approved request, so Pi cannot change model, schema or
limits. Stage A binds the effective override URL (including port/path) into the review and
snapshots gateway configuration before Pi starts. R2 also carries a frozen, typed destination
from immutable admission terms through the reserved invocation into the HTTP request. Both
the pinned effective endpoint and constructed HTTP request URL must match that owner-approved
endpoint before any network send; the dispatch fence binds the invocation's admission id and
review digest back to the immutable review. A substituted snapshot is refused even if live
settings were restored before the fence. Redirects are explicitly refused. Admission
rejects HTTP, URL credentials, query strings, fragments and invalid host/port syntax. Existing
reviews without the endpoint field require fresh review and owner approval before starting;
historical completed runs remain readable. There is no local-inference path, network host/IP
allowlist, DNS pinning or provider-side identity attestation. Model HTTP clients use
`trust_env=False`, so ambient proxy/CA settings do not reroute inference or alter TLS trust.
Default TLS certificate verification stays enabled; existing explicit test transports are
preserved. Future explicit deployment proxies or custom CAs require separate governed
configuration and disclosure. This is application
destination binding, not a general network sandbox.

**Options.**
* A. Keep per-review disclosure approval (implemented). Accept the single configured endpoint.
* B. A plus a pinned-host check in the egress: refuse any upstream host other than the host named in
  the approved review, and refuse redirects.
* C. Require local inference for sources classified above `owner_internal` (needs a local provider
  that does not exist yet).

**Implementation for review.** Stage A implements the destination-binding part of B under the
programme's hardening authorization. This does not choose the owner's sensitive-data policy or
authorize live inference. C still needs a local provider. See `L1-QUALIFICATION.md`.

## 2. Clear-text retention

**Today.** The prompt (including the files), the response, each stage output and the retained
report are stored unencrypted in the local database. The generic event feed withholds stage results.
A Stage A canary probe against the real pinned Pi found no source or response text in retained
`pi.rpc.event` payloads. This bounded probe is not a proof about every future Pi event shape.

**Options.** A. Accept for a single-owner development machine and document it. B. Encrypt the
source blob and model records at rest with a key held outside the database. C. Retain digests and
structured findings, drop the prompt text after the call settles.

**Recommendation.** A for demos on owned data only; C as the default for anything else, with B if
prompt text must be kept for audit.

## 3. Deletion

**Today.** Withdrawing a source approval stops any new use. Nothing deletes captured content,
prompts, responses or reports; admission and execution history is deliberately immutable and
undeletable.

**Options.** A. Accept (no deletion). B. A purge command that blanks content fields and keeps
digests, receipts and ids, so history still proves what happened without holding the text. C. Time-
based retention with automatic purge.

**Recommendation.** B, designed as its own reviewed change because it must not break the immutability
guards or receipts that other checks rely on.

## What follows

Until these are decided, demonstration qualification is restricted to synthetic, non-sensitive
or deliberately public sources. Captures, prompts, responses and reports may remain in local
clear-text storage. This temporary deployment restriction is not a retention/deletion policy or
a remote-provider retention guarantee. Independent review of the R2 network boundary remains
required; see `L1-STAGE-A-R2.md`.
