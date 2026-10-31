# L1-02 — Security decisions awaiting the owner

Three questions decide whether L1-02 may be treated as a qualified production foundation. They are
policy choices, not implementation details, so none is decided here. Each lists what the code does
today, the realistic options and a recommendation. Status of all three: **open**.

## 1. Remote-model egress

**Today.** Source code leaves the host only after: a source approval naming the operation
`repository.analyze`, a review that shows the destination host, model, files and byte count, the
owner's local confirmation of that exact review, and re-checks at start, reservation and dispatch.
There is exactly one destination (the configured Meta endpoint through Pi's loopback egress). The
egress builds the upstream request from the approved request, so Pi cannot change model, schema or
limits. There is no local-inference path, no allowlist of hosts beyond the configured URL, and no
redirect policy beyond the HTTP client's defaults.

**Options.**
* A. Keep per-review disclosure approval (implemented). Accept the single configured endpoint.
* B. A plus a pinned-host check in the egress: refuse any upstream host other than the host named in
  the approved review, and refuse redirects.
* C. Require local inference for sources classified above `owner_internal` (needs a local provider
  that does not exist yet).

**Recommendation.** B before any real source is sent; C when a local provider exists.

## 2. Clear-text retention

**Today.** The prompt (including the files), the response, each stage output and the retained
report are stored unencrypted in the local database. The generic event feed withholds stage results.
Pi's own retained run events were not audited with a real Pi for echoed text.

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

Until these are decided, use L1-02 only on data you are content to hold in clear text locally and to
send to the configured provider, and treat it as unqualified for anything more sensitive.
