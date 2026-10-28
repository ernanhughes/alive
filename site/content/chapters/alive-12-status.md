+++
title = "ALIVE-12 - Personal Research Intelligence"
slug = "alive-12-status"
chapter_id = "alive-12-status"
alive_stage = "ALIVE-12"
source_doc = "docs/ALIVE-12.md"
source_parts = ["__preamble__", "Connections and feedback"]
source_commit = "cce792bc87fa8b3c34742d478ce00863dda43b7f"
source_sha256 = "1068575be389fe9f32e0fd540c20a5f355ac671fd9e8c195d7e2d7f490c797a5"
body_sha256 = "3b1f4c76bb5e1ea334a5258354fa01214b12d595cd0efb37c411abba5c29ed2c"
generated_by = "site/notebook.py convert"
+++
Engineering: **PASS**. Native synthetic: **PASS**. Native Meta: **NOT RUN**.
Retrieval advantage: **NOT DEMONSTRATED**.

Baseline: `d58c30748a5ec9273a0be86dc769d8c1b7dc6b23` (ALIVE-11-R1 merge).
Branch: `codex/alive-12-research-intelligence`.
Source commit for the evidence: `cf7022cb168b4cbd65bbc0b98faafbb25b498c85`.
No paid inference was used.

## Connections and feedback

`POST /research/connections` builds a deterministic candidate from lexical overlap between the
current reviewed excerpt and the historical excerpt:

- at least two shared content terms: `same_concept`, status `candidate`;
- one shared term: `complementary`, status `candidate`, weak;
- no shared term or missing exact quotation: `insufficient_evidence`, aborted connection.

Every candidate stores both source URLs and hashes, the current and historical quotations, exact
quote-validation flags, shared terms, relation type and explanation. It is never labelled factual
support. Connection feedback is persisted separately and never used to suppress a topic.
