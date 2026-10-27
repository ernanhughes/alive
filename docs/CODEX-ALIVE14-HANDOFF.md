# Codex ALIVE-14 handoff

## 1. Repository and workflow

- Verified main: `3d81ce9a435d375ff6652bde07582d22a1eafdd6` (ALIVE-13 merge).
- Branch: `codex/alive-14-research-connections`.
- Protocol freeze: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
- Implementation: `843f5b4f2c37d97ff40cd84623e0f8b87c8c1f7f`.
- Race/quote-validation follow-up: `83852b2bdcccdef041c3e440dce3a2b22906ad0c`.
- Archive commit: to be recorded after packaging.
- PR: to be recorded after push. Review-only; no merge or auto-merge.
- CI: to be recorded after push.
- Paid inference: **0**.

The primary checkout and frozen ALIVE-01 through ALIVE-13 archives were not modified.

## 2. Confirmed defects and corrections

| Review finding | Correction |
|---|---|
| Empty memory-type allowlist failed open | `ALL_MEMORY_TYPES` sentinel; empty list/tuple raises `ValueError`; default remains restrictive |
| Long generic excerpts could outrank short specific sources | Goal-term exclusion, BM25 length normalisation, document-frequency weighting, discriminating-IDF guard and score floor |
| Connection evidence could overstate overlap | Exact overlapping sentence-pair selection; goal vocabulary excluded; displayed terms limited to both spans; model quotation separate |
| Freezing could not be verified | Protocol committed before held-out execution; evidence records protocol commit and SHA-256 |
| Outbound consent was undefined | Separate preview, authorise and analyse sequence with exact payload hashes, live-grant checks, active-memory checks, Governor budget and no retries |
| Research vectors not used by retrieval | Explicitly retained as a backlog item; no architecture change |

## 3. Memory scope and outbound permission

| Operation | Permission |
|---|---|
| General cognition retrieval | Restrictive allowlist; research memory excluded |
| Local research retrieval | Same instance and goal, active rows, no external transmission |
| Read retained history after grant expiry | Local owner-scoped history, explicitly documented |
| Create a local lexical connection with the current page | Live reviewed current-page grant |
| Preview outbound payload | Live reviewed current-page grant; no external call |
| Authorise outbound payload | Explicit owner action bound to the displayed payload SHA-256 |
| Send to an external model | Authorised consent + live grant + active memory + exact hashes + Governor approval; Meta disabled by default |
| Withdraw a memory | Exact displayed research ID; outbound consents invalidated; in-flight dispatch blocks withdrawal until settlement |

## 4. Retrieval

The ALIVE-13 ranker remains available as `alive13-scoped-lexical-v1`. The ALIVE-14 default is
`alive14-bm25-v1`.

Held-out frozen result:

| Arm | P@3 | Recall@3 | MRR | Rank-1 | Missing failures |
|---|---:|---:|---:|---:|---:|
| Recency | 0.1667 | 0.3333 | 0.2222 | 0.0000 | 3 |
| ALIVE-13 | 0.4444 | 1.0000 | 0.7500 | 0.5000 | 0 |
| ALIVE-14 | 0.4444 | 1.0000 | 1.0000 | 1.0000 | 0 |
| Full history | n/a | n/a | n/a | n/a | n/a |

The improvement is rank-1/MRR on long-excerpt competition, not recall or precision over ALIVE-13.
The full-history control contained a relevant source for 6/6 positive queries but does not rank.
No semantic-superiority claim is made.

## 5. Withdrawal and races

- Per-result withdrawal remains bound to the displayed `researchId`.
- Withdrawal invalidates pending/authorised outbound consents for that memory.
- Withdrawal during an in-flight outbound call returns 409 and does not remove the memory until the
  dispatch settles; then withdrawal succeeds.
- Revoked grants invalidate pending/authorised consents.
- Consumed consents cannot be reused; repeated analysis of the same source pair reuses the existing
  connection without another dispatch.
- Content changes and payload-hash mismatches are rejected before inference.

## 6. Relationship evidence

New local labels remain `topic_overlap_candidate`, `weak_lexical_overlap` and
`insufficient_evidence`. New model hypotheses use:

- `possible_conceptual_connection`;
- `possible_methodological_difference`;
- `possible_disagreement`;
- `insufficient_evidence`.

Every validated model record has exact current and historical quotations, a separate model quotation
field, limitations, provider/model identity, consent/payload identity, validation results and usage.
Invalid raw output remains in a separately persisted attempt record.

## 7. Index consistency

ALIVE-13's `/research/index/repair` remains intact: it recreates missing projections, refreshes stale
content/version, removes stale vectors and deletes withdrawn leftovers without resurrection. ALIVE-14
does not use the research vector index for retrieval.

## 8. Native synthetic qualification

Chrome `155.0.8059.85`, genuine docked side panel, isolated backend, local synthetic note provider:

- target ranked 1 of 2 competing research results;
- truthful local connection with exact spans;
- exact outbound preview and explicit authorisation;
- local stub relationship analysis with exact quotations;
- scripted feedback saved;
- withdrawal of the displayed target;
- stale authorised consent returned 409 with zero external calls;
- restart preserved the withdrawal and the validated relationship;
- revoked-grant connection returned 403 while local retrieval remained 200;
- wrong-origin grant returned 403;
- 3 synthetic note calls, zero paid calls.

`NATIVE_SYNTHETIC_PASS`. No native Meta inference was run.

## 9. Frozen evaluation and limitations

- Protocol: `archives/ALIVE-14/protocol.json` (commit `bf0af92`, hash in evidence).
- Held-out raw results: `archives/ALIVE-14/evidence/retrieval-comparison-held_out.json`.
- Diagnostics: `archives/ALIVE-14/evidence/ranker-diagnostics.json`.
- Relationship dry-run: included in the held-out evidence; local stub only.
- Native: `archives/ALIVE-14/evidence/native-synthetic.json`.

Limitations: lexical corpus, lexical ranker, source-adequacy labels, no human owner ratings, no
real Meta inference, no semantic paraphrase claim, no evidence of relationship usefulness.

## 10. Archive integrity

`archives/ALIVE-14/` contains the frozen protocol, held-out comparison, diagnostics, native evidence,
screenshot, validation transcripts, README and SHA-256 manifest. ALIVE-01 through ALIVE-13 archives
are unchanged. Verify with:

```powershell
uv run python scripts/verify_archive.py archives/ALIVE-14
uv run python scripts/verify_archive.py archives/ALIVE-13
```

## 11. Meta authorisation gate

No paid calls are authorised by this handoff. A future proposal must specify:

- exact approved model and endpoint;
- exact source material and payload hashes;
- number of tasks and conditions;
- number of calls;
- input/output token caps;
- maximum dollar spend;
- no automatic retries;
- abort conditions;
- data-redaction plan;
- owner assessment procedure.

Suggested starting point, subject to separate approval: up to 12 real Meta calls over the frozen
condition A/B/C tasks, with a small fixed budget. This is a suggestion, not authorisation, and does
not reuse the ALIVE-11 approval.

## 12. Recommended next milestone

ALIVE-14 completion only becomes a usefulness experiment after the approved Meta run and blinded
owner ratings. Until then, the correct claim is: secure, owner-authorised relationship plumbing with
a controlled lexical retrieval improvement and no demonstrated usefulness advantage.
