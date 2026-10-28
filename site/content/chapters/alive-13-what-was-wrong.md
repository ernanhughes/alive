+++
title = "ALIVE-13 - Reliable Research Retrieval and Evidence-Grounded Connections"
slug = "alive-13-what-was-wrong"
chapter_id = "alive-13-what-was-wrong"
alive_stage = "ALIVE-13"
source_doc = "docs/ALIVE-13.md"
source_parts = ["What was wrong"]
source_commit = "1f399f8760a74c92deb853f2209dee80fbcd5951"
source_sha256 = "211bbb782685bf82f4a00258fe5a8b3c41f26c86b336c2cb20d93f88f229e8c3"
body_sha256 = "1248bf7df7f06a2a70bd18deadd42c6521a7129da80d17a3efc899fad0076aba"
generated_by = "site/notebook.py convert"
+++
## What was wrong

ALIVE-12 established the research-memory lifecycle, but its retrieval path was:

`goal + current text -> unscoped MemoryService top-k -> post-filter by research metadata`

The rank and limit were therefore decided before goal and record-type eligibility. Sixty
older ordinary memories could fill the candidate window before the relevant research row was
considered. The same shared `MemoryService` path was also used by general cognition, so a saved
research excerpt could enter an ordinary investigation prompt. The panel's withdrawal command used
the last saved research ID rather than the displayed result. Lexical overlap was labelled
`same_concept` or `complementary`, which overstated what shared words establish.

The frozen pre-fix evidence is in `archives/ALIVE-13/evidence/pre-fix-defects.json`:

- With 60 ordinary memories, the old path returned 15 ordinary candidates and **zero** research
  candidates; the relevant research memory was absent.
- The old general retrieval path returned the research sentinel; the corrected default returned
  the ordinary experience memory and excluded the sentinel.
- The old background worker withdrew `research-B-last-saved` when the displayed item was
  `research-A-displayed`; the corrected worker withdrew the displayed ID and rejected a request
  with no explicit ID.
- Contradictory, unrelated and weakly related fixtures were labelled `same_concept`,
  `complementary` or `no_supported_connection`; the corrected labels are
  `topic_overlap_candidate`, `weak_lexical_overlap` and `insufficient_evidence`.

These controlled reproductions reconstruct the pre-fix algorithm against a fresh database: the
old query, top-k and post-filter are copied from `af12bc8`, and the ALIVE-13 type allowlist is
explicitly disabled. They are faithful reproductions of the defect, not a literal execution from a
checkout made before the edits.
