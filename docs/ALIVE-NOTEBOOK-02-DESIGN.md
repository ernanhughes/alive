# ALIVE-NOTEBOOK-02 — design and implementation plan

Baseline: `937bdcd` (full SHA in protocol.json), current origin/main at worktree creation.
Notebook-01 (#40) and R1 corrections (#41/#42) are merged. Worktree:
`C:\Projects\alive-notebook-02`; branch `codex/alive-notebook-02-evidence-qualification`.

## Decision and boundary

Choose **A: a small Core service**, composed with the existing ResearchMemory/WebCompanion.
B (declarative skill) would add a registry/manifest layer without helping this experiment;
C (general extension host) is only proposed in ALIVE-EXT-01 and is out of scope. A typed,
read-only service boundary can later be called by a constrained skill without new privileges.

Existing API map (`/api/v1/browser-experience`): grants/snapshots create owner-reviewed
source evidence; `research/memories` explicitly saves it; `research/retrieve` ranks eligible
same-goal active memories; `research/connections` persists lexical candidates;
`research/outbound/preview -> authorize -> analyze` governs optional model use;
`research/memories/{id}/withdraw` retires evidence. Rows remain WebExperience records,
with the existing Memory projection for retrieval. No new persistence or retrieval system.

```text
existing retrieval -> selected snapshot ID + memory ID
  -> authenticated versioned qualification endpoint
  -> Core lock/session, instance/goal/live-current-grant/active-memory checks
  -> resolve authoritative historical snapshot, verify hashes and source bindings
  -> exact quote selection/validation over bounded captured evidence
  -> typed conservative result (no model, no writes, no permission mutation)
```

The operation does not invoke retrieval or change ordering. It accepts IDs, policy version
and optional bounded quote selections; it never accepts raw historical source evidence.
Selections are untrusted and must be exact substrings. Current capture is limited to 2000
characters for comparison parity; historical evidence is the existing 2000-character excerpt.
A source hash covers the full stored snapshot, not merely the displayed quote.

## Contract

Version: `evidence_qualification_v1`; POST `research/qualifications` alongside the legacy
endpoint. Separate dimensions: authorization, source integrity, relevance, claim relationship,
applicability, currency, evidence sufficiency. Unknown semantic dimensions remain unknown.
`candidate_connection` is reserved for a future independently qualified policy; v1 does not
emit it. Authorized but missing/corrupt evidence or invalid selected quotes produce
`qualified_non_use`; intact evidence produces `abstain` because semantics are not established.
No confidence scalar. Responses include authorized source references/exact quotes, reason
codes, limitations, policy/workflow version, explicit semantic/model/call/usage/cost provenance
and a next action. Source quote verification is explicitly distinct from factual truth.

Authorization failure returns the same generic 404 for missing, foreign-instance,
wrong-goal, withdrawn or otherwise ineligible history, without its metadata or existence.
Expired/revoked/missing current permission fails closed. Historical saved evidence requires
retained ownership/goal scope, not a live grant on its former tab (ALIVE-13 contract).
Every request resolves fresh state under the Core lock; no cached qualification survives a
withdrawal, revocation or restart. Missing authoritative historical snapshots are honest
non-use findings for already-authorized memories, not permission errors or semantic claims.

## Model decision

Arm C is **NOT RUN**. No provider option is exposed and no synthetic output is presented as
semantic judgment. Existing ResearchRelationships already has preview, exact-payload consent,
source revalidation, budget/approval and output checking. Its generic relationship/claim
outputs do not implement this new seven-dimension contract. A future semantic adapter must
reuse that governed workflow with a versioned exact-payload preview and validated output;
this milestone adds no dispatch path, approval changes, HTTP shortcut or paid calls.

## Evaluation and gates

Freeze development cases R1–R4 and independent synthetic held-out pairs/labels/protocol
before executing comparisons. Labels live separately, and the runner gives services only
source IDs/quote selections/policy, never labels, case names or expected outcomes. Primary
real cases use source quotes from the existing notebook; perturbations are identified only
in evaluation metadata. Synthetic cases vary names, topics, positive/negative relationship,
scope, temporal order, missing evidence and injection. Hold candidate pairs/evidence budgets
fixed across A (actual legacy connection endpoint), B (new deterministic policy), D (explicit
same-access abstain control); C NOT RUN. Reverse pairs and add a source distractor in
predeclared diagnostics. No tuning against held-out outputs.

Primary metrics: supported substantive-relation precision (undefined if none asserted),
correct non-use/abstention on negative labels, missed useful substantive relationships.
A legacy lexical candidate is not a substantive semantic finding; candidate yield and
label agreement are separate diagnostics. The evaluation must expose all-abstain false
negatives and compare B with D. Integrity/authorization are hard gates, never averaged into
semantic performance. Results are descriptive; labels are author-prepared, not independent
human ground truth. Level 3 is not demonstrated by passing integrity checks or abstaining.

## Implementation sequence

1. Commit this design and frozen cases/labels/protocol with hashes before implementation.
2. Add typed service and thin authenticated API adapter; no UI/extension changes.
3. Test grants, ownership, goal, withdrawal, hashes, quotes, source binding, uniform refusal,
   injection, zero model access, restart and unchanged legacy behavior.
4. Run frozen comparison, including same-access control, source-order/distractor diagnostics.
5. Run focused/full applicable suites, Ruff, Hugo and built provenance, Node capture and
   archive/protocol checks. Native UI is unchanged; no new toolbar qualification is claimed.
6. Record exact results/environment/limitations, commit/push and open a draft PR. Stop for
   independent Claude review. Human merge authority only.

## Risks and limits

- Blanket abstention may discard all useful relationships: count it, do not call it reasoning.
- Snapshot integrity binds captured bytes, not external source authenticity or truth. No web
  fetching or notebook-front-matter validator is used by the qualifier.
- Selected quotes are partial context; full captured evidence may itself be incomplete.
- Mutable local DB and trusted owner/API remain trust boundaries; recomputed malicious hashes
  can defeat cryptographic integrity relative to those inputs. Titles are untrusted presentation.
- Uniform authorization errors avoid metadata/existence disclosure; response timing is not
  claimed to be constant-time. No model output or cached result can override current checks.
- No new UI means researchers must explicitly call the API; companion labels stay unchanged.
