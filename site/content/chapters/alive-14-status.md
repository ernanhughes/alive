+++
title = "ALIVE-14 - Evidence-Grounded Research Connections"
slug = "alive-14-status"
chapter_id = "alive-14-status"
alive_stage = "ALIVE-14"
source_doc = "docs/ALIVE-14.md"
source_parts = ["__preamble__", "Limitations"]
source_commit = "f3516d7892fc79c56621a842a8329389997a4c24"
source_sha256 = "d95232e196752119fa1c377ff4f2552fda350fab7eb950422fac4677aaf6f5b4"
body_sha256 = "69cb4216e2973df2a01f7c7bc339c0cb9fbe868906c7e7530a381f7414d05105"
generated_by = "site/notebook.py convert"
+++
Engineering: **ENGINEERING_PASS**. Native synthetic: **NATIVE_SYNTHETIC_PASS**.
Native Meta: **NATIVE_META_NOT_RUN**.
Retrieval: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen held-out lexical corpus.
Relationship usefulness: **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.
Owner ratings: **SCRIPTED_ONLY** (no human ratings collected).

Baseline: `3d81ce9a435d375ff6652bde07582d22a1eafdd6` (ALIVE-13 merge, `origin/main`).
Branch: `codex/alive-14-research-connections`.
Protocol freeze commit: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
Implementation commit for the archived evidence: `83852b2bdcccdef041c3e440dce3a2b22906ad0c`.
PR: https://github.com/ernanhughes/alive/pull/20 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was used. No merge or auto-merge was requested.

## Limitations

- The corpus is lexical and controlled; no semantic paraphrase claim.
- Retrieval labels are source-adequacy labels, not owner usefulness ratings.
- ALIVE-14 improves MRR and rank-1 on the held-out corpus but not recall or precision over ALIVE-13.
- The local stub is not Meta and cannot establish relationship usefulness.
- No owner ratings or paid Meta calls were collected.
- Real Meta requires a separate approval naming the exact model, payloads, call count, token caps,
  spend cap, abort conditions and data-redaction plan.
- Additional relationship feedback revisions are stored as revisions, not independent ratings.
