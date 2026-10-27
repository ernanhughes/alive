# ALIVE-14-R2 - Paired experiment plan

Status: **FROZEN, NOT RUN**. No real Meta calls are authorised.

Protocol: `archives/ALIVE-14-R2/protocol/relationship-experiment-v2.json`
Protocol commit: `2463da5`
Canonical LF SHA-256: `bd08e2e6b9e7f4804af16daaca5b5a12a2d07d83eb19ae082527ef1da2add5dc`
Seed: `20261101`

## Research question

Does owner-authorised historical research improve the factual support and owner-perceived usefulness
of an AI research assessment compared with the same model using the current page alone?

The three conditions separate model knowledge, current-page evidence and additional historical
evidence:

- **A_current_only** - current excerpt and research question; no historical material.
- **B_current_plus_history** - current excerpt and question plus the exact authorised historical
  excerpt.
- **C_history_without_synthesis** - direct display of the same historical excerpt, no model
  synthesis.

A and B are paired on the same task and pinned model. C is a no-inference control.

## Strata and tasks

The protocol defines:

- **Novel controlled facts** T01-T04: Aster-17, Helio-9, Novara-4 and Ether-2 fixtures. These are
  experimental fixtures, not claims about real technology. The historical excerpt contains a
  specific mechanism that the current-only model cannot derive from the current page.
- **Current-only-solvable control** T05: the current Cache API excerpt is sufficient; history is
  irrelevant.
- **Misleading controls** T06-T08: outdated appcache recommendation, unrelated CPU cache, and an
  adversarial historical instruction/false claim.
- **Recent owner-approved stratum**: not populated in this preflight; no approved real sources were
  available. It must remain empty rather than substituting unapproved material.

## Conditions and prompts

Treatment prompts are frozen as:

- A: `CURRENT_ONLY_INSTRUCTIONS`
- B: `RELATIONSHIP_INSTRUCTIONS`

Both use the same model pin, research question, output-token ceiling and no-retry policy. The
current-only schema has no historical quotation field. History-assisted validation is unchanged and
is not weakened for A.

## Blind rating

The owner uses the side-panel blind evaluation view or the equivalent authenticated owner API. The
server hides condition/provider/model/token/cost during rating. Each task's three outputs are
shuffled with the frozen seed; assignment is stored separately and hashed. Ratings are append-only
revisions using the seven-dimension rubric. Reveal is a POST action that requires all owner ratings
and records `revealed_at` and the assignment hash. Post-reveal ratings are rejected.

The rating endpoint uses an issued capability bound to the run; a client-supplied `rater=owner`
string is not accepted. Scripted preflight ratings use an internal path and are labelled separately.

## Scale and budget

- 8 paired tasks.
- 2 inference conditions per task = **16 calls**.
- 1 direct-history condition per task = no inference.
- No automatic retries.
- Input cap 18,000 tokens; output cap 1,536 tokens.
- Planning estimate: **$0.035 expected**, **$0.34 worst-case reservation**, **$0.40 ceiling**.
- Verify current provider pricing and the exact reservation formula before requesting approval.

The earlier $0.30 proposal is not reused; the revised 16-call count requires a new approval.

## Metrics

Primary:

- factual support rate;
- owner usefulness rate;
- new-insight rate;
- misleading/incorrect rate.

Secondary:

- already-obvious rate;
- willingness to act;
- uncertainty/insufficient-evidence rate;
- abstention appropriateness;
- dispatch success;
- invalid-output rate;
- cost and latency.

Report per-condition and paired differences. This is a small pilot; do not claim population-level
significance. Do not use model judgments as a substitute for owner ratings.

## Freeze and analysis rules

- Protocol commit and canonical hash are recorded in preflight evidence.
- Any material change creates a new protocol version.
- The final evaluator must refuse a mismatched protocol.
- Use the latest owner revision per output and retain revision history.
- Exclude no mandatory owner ratings; reveal requires all.
- Rejected/invalid outputs are reported as failures and never counted as validated answers.
- Preserve negative and null results.

## Approval gate

Before real calls, the owner must independently receive and approve:

- exact endpoint and pinned model;
- exact 8 task payloads and hashes;
- 16-call count;
- input/output caps;
- expected and worst-case spend;
- hard USD/call/token limits;
- no retry and abort conditions;
- payload redaction policy;
- blinded rating procedure.

No paid inference is authorised by this document.
