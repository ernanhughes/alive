# PI-02C independent-review handoff

Pin the exact PR head from the draft description. Base is
`b0b3e40ab51e2ea4f482a20767f9bad8b4491765` (merged #71).
Read the architecture inventory, delivery report and Bespoke readiness report.

R3 qualification: Claude's local post-merge audit at
`C:/Projects/alive-pi02b-r3-evidence/ALIVE-PI-02B-R3-INDEPENDENT-REVIEW.md` says GO,
no PI-02C blocker. It records LOW gaps for completed-goal and extra-source-ID test
coverage; neither is a production defect. No R3 execution/security correction is
folded into this branch. Its role-contract and unsupported-worker watch items remain.
The audit also contains a full-suite placeholder; GO is not substituted for CI.

Review these boundaries adversarially:

1. All 12 workflow routes remain GET-only. App wiring supplies the existing pure
   Pi receipt formatter; workflow code imports only Pi record models, not dispatch.
   No migration, dependency, Governor, authorization, runner, recovery or provider
   routing change should exist. Existing route-count test includes three new reads.
2. Trace definition ID/name/version/schema/hash, stage membership/operation/type,
   invocation inquiry/run/attempt and Pi instance/reservation/operation bindings.
   Corrupt/foreign identities refuse. Event correlation alone is not receipt binding.
3. Timeline query filters instance, actual run and validated attached Pi identities,
   allow-lists event kinds and projects fixed fields. It never returns stage output,
   browser context, prompts, secrets or arbitrary event payloads. Test sequence cursor
   bounds, pagination, bad attempts and missing references. Request rows are bounded.
4. Replay must show only event-justified stage state at the cursor. Final snapshots
   remain explicitly separate. No historical abandonment/reservation event is invented.
   Artifact content is withheld during replay and otherwise comes from the existing
   hash-checked artifact endpoint with current parent status.
5. Browser tests use real persisted records from a pinned Pi/scripted HTTP provider.
   Reproduce seed, restart, browser journey and verify unchanged durable counts.
   Inspect the controlled post-dispatch cancellation and post-artifact finalization
   interruption; both are harness-only fault injection, never production switches.
6. Attempt HTML/script-like labels/outputs/URLs, very large strings and invalid dates.
   No raw HTML insertion or diagram directives. SVG and accessible stage buttons
   select the same stable IDs. Inspect desktop/mobile screenshots and contrast.
7. Exercise credential/run/version switches, delayed responses, unmount, tab hiding,
   repeated polling failures and terminal stopping. Abort and generation checks must
   prevent old data replacing the new selection. No concurrent polling cycles.
8. Comparison uses each run's own graph/hash and descriptive facts. Null usage/cost
   stays unknown. Structural validation is not semantic verification or feedback.
9. Extension links contain only validated identifiers on existing allowed loopback
   origins. No new permission, token, context or action parameter. The dashboard
   requires its own authentication and rejects a contradictory run/version link.
10. Confirm exact-head Windows/Linux CI and local Docker/PostgreSQL evidence. Rerun
    targeted tests first; reserve the full backend suite for the release gate.

No independent PI-02C approval is claimed by the implementation agent. No automatic
merge. No paid inference, PI-03, Bespoke selection or workflow execution authority.
