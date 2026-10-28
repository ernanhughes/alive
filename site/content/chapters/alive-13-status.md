+++
title = "ALIVE-13 - Reliable Research Retrieval and Evidence-Grounded Connections"
slug = "alive-13-status"
chapter_id = "alive-13-status"
alive_stage = "ALIVE-13"
source_doc = "docs/ALIVE-13.md"
source_parts = ["__preamble__", "Connection evidence semantics"]
source_commit = "1f399f8760a74c92deb853f2209dee80fbcd5951"
source_sha256 = "211bbb782685bf82f4a00258fe5a8b3c41f26c86b336c2cb20d93f88f229e8c3"
body_sha256 = "3b960dcf05e224f4a7c5216db041179c62cb585918927e674fd8215c17df2424"
generated_by = "site/notebook.py convert"
+++
Engineering: **ENGINEERING_PASS**. Native synthetic: **NATIVE_SYNTHETIC_PASS**.
Native Meta: **NATIVE_META_NOT_RUN**.
Controlled lexical retrieval: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen corpus.
General semantic or owner-usefulness superiority: **NOT DEMONSTRATED**.

Baseline: `af12bc88c91a85558873d01579dba93fdd6b1bbf` (ALIVE-12 merge, `origin/main`).
Branch: `codex/alive-13-reliable-research`.
Product and harness commit for the archived evidence: `d963d267c219d49e4dfab23cf838946b64c4b190`.
Archive commit: `04adadb`.
PR: https://github.com/ernanhughes/alive/pull/19 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was used. No merge or auto-merge was requested.

## Connection evidence semantics

New connection records use only lexical claim labels:

- `topic_overlap_candidate` - at least two shared content terms and exact sentence spans in both
  sources.
- `weak_lexical_overlap` - exactly one shared content term and exact sentence spans.
- `insufficient_evidence` - no inspectable shared span; the connection abstains.

The record carries the current URL/SHA-256, historical URL/SHA-256, exact current and historical
source sentences, separately labelled model evidence quotation, shared terms, an explicit
`evidence_policy`, and quote-validation booleans. The explanation states that lexical overlap does
not establish agreement, support, contradiction or corroboration. The panel labels source spans and
the historical model quotation separately. Legacy persisted rows are not rewritten.
