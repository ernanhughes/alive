# Codex ALIVE-14-R2 handoff

## 1. Repository

- Verified main: `a4dbf25e6c4611ef4248297426b1cd6c267e0c72`.
- Branch: `codex/alive-14-r2-memory-experiment`.
- R2 protocol commit: `2463da5`.
- Product/evidence source commit: `c31f4f57d2a6a8ca48ad1d0ec37be263ed8f484d`.
- No paid inference, merge or auto-merge.
- Original ALIVE-14 and ALIVE-14-R1 archives preserved.

PR/CI to be recorded after push.

## 2. REVIEW-08 blockers

| Blocker | Correction |
|---|---|
| Current-only cannot execute | Current-only mode with dedicated payload, instructions, schema and storage; no historical fields or hidden retrieval |
| Seed `20261101` rejected | Seed range expanded; frozen seed regression test passes |
| Ratings after reveal | Explicit `collecting -> revealed -> archived`; POST reveal; post-reveal ratings 409 |
| Experiment ID reuse | Duplicate IDs refused |
| No native blind UI | Side-panel evaluation selector, anonymous outputs, rubric, progress, reveal and archive |
| Textbook-heavy tasks | Successor protocol with novel controlled facts and misleading controls |
| Task requires absent evidence | Current-only-solvable and explicit misleading controls added |
| Grant revoked between reservation and dispatch | Final guard revalidates grant, snapshot, memory, hashes, provider, model, reservation and cap under the kernel lock |
| Condition metadata leak | Separate assignment record; rating view hides condition/provider/model/tokens/cost |
| Meta preview not native-qualified | Exact instructions, input, schema, request hash, reservation and remaining allowance |

## 3. Current-only and history-assisted

- Current-only: current excerpt, research question, goal, provenance; no historical excerpt, ID,
  title, hint, prior explanation or hidden retrieval.
- History-assisted: same current context plus the explicitly selected historical excerpt.
- Direct history: no inference.
- Current-only abstains when the current source is insufficient; its schema has no historical quote.
- Both modes share model pin, output ceiling, no-retry policy and Governor path.

## 4. Consent and dispatch

The final dispatch guard rechecks:

- live page grant;
- current snapshot hash/excerpt;
- active historical memory and hash for B;
- payload and request hashes;
- provider enablement/identity and model pin;
- Governor reservation;
- cumulative USD liability including interrupted attempts.

The revocation-after-reservation regression revokes the grant after reservation but before guard
source validation and asserts zero provider calls. Once a request has left the process, revocation
cannot recall it; this is documented.

## 5. Blind lifecycle and provenance

- `collecting` assignment is committed before ratings.
- Outputs are immutable and hash-bound.
- Rating capability is issued by the authenticated owner view; owner ratings require it.
- Scripted ratings use the internal path and are separate.
- Conditions/provider/model/token/cost hidden before reveal.
- Seeded per-task order; assignment hash stored.
- Ratings append revisions; reveal POST requires all owner ratings and records `revealed_at` and
  assignment hash.
- Post-reveal ratings and repeated reveal rejected; archive explicit.
- A plain GET does not change state.

## 6. Frozen R2 protocol

- 8 paired tasks: 4 novel controlled facts, 1 current-only-solvable control, 3 misleading controls.
- Optional recent-owner-approved stratum is explicitly not populated.
- Seed `20261101`; 16 inference calls; no retries.
- Budget proposal: $0.035 expected, $0.34 worst case, $0.40 ceiling. Not authorised.
- Protocol hash and commit recorded in preflight evidence.

## 7. Zero-cost preflight

`archives/ALIVE-14-R2/evidence/preflight.json` records 8 tasks, A/B local-stub execution, C direct
text, 24 anonymous outputs, 24 synthetic owner-endpoint ratings, reveal and archive. No paid calls.
The owner-endpoint exercise is explicitly not human feedback.

## 8. Native Chrome

Chrome `155.0.8059.85`, genuine docked side panel:

- current-only and history-assisted analysis;
- exact payload/request preview;
- malformed-output rejection;
- cache reuse and scripted feedback;
- blind evaluation selector, anonymous outputs, rating completion, reveal and archive;
- withdrawal invalidating consent; restart; zero external calls.
- 3 synthetic note calls, 0 paid calls.

## 9. Tests

- Full backend: 192 passed.
- Focused research-memory: 46 passed (before final revocation test; final rerun recorded in archive).
- Extension: 11 passed.
- Frontend: 7 passed.
- Production build: passed.
- Ruff in CI scope: passed.
- Native: `NATIVE_SYNTHETIC_PASS`.

## 10. Status

- **ENGINEERING_PASS**
- **NATIVE_SYNTHETIC_PASS**
- **NATIVE_META_NOT_RUN**
- **META_READY_FOR_APPROVAL** subject to independent recheck
- **OWNER_USEFULNESS_NOT_MEASURED**
- **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**

## 11. Remaining decisions

No real Meta experiment is authorised. Before paid execution, independently recheck provider and
blind-boundary behaviour, verify current pricing/reservation, and approve the exact 8-task/16-call
payload set, token caps, spend ceiling, no-retry rule, redaction policy and owner-rating procedure.
