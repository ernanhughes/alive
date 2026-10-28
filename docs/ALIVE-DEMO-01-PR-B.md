# ALIVE-DEMO-01 PR-B — Minimal Browser Evidence Card

**Status:** draft browser UI implementation, not native-Chrome qualified.

## Scope delivered

This patch adds a deliberately small, owner-triggered evidence-validity panel inside the existing Chrome side panel:

1. `Check saved findings` fetches the pre-existing authenticated `GET /api/v1/browser-experience/research/relationships` through the extension background worker.
2. Shows at most ten active **candidate** connections with exact quoted current and historical source excerpts, URLs, source hashes, relation labels and caveats. Uses `textContent`, not executable markup.
3. Clearly labels that these are candidate relationships, **not** verified contradiction/supersession verdicts. It does not call Meta, make any new inference, request browser permissions or schedule background work.
4. An explicit `Withdraw historical evidence` control confirms with the owner, invokes ALIVE-12's existing withdrawal endpoint, clears displayed cards and reloads the authoritative list. Previously invalidated rows are filtered out.
5. The existing withdrawal control also clears previously rendered outbound and relationship views rather than preserving misleading stale quotes.

## Why the scope is narrow

PR-A was merged, but the merge itself does not establish the regression gates in its report have been passed. The browser layer therefore only presents **existing** findings and the existing source withdrawal primitive. It does not claim the new inferential check works or simulate a real correction. There is no new permanent data store or ALIVE-14 campaign dependency.

## Known gaps / explicit limitations

- Candidate connections are not necessarily contested claims. A true supersession classifier and a real public correction fixture belong in the next carefully reviewed slice.
- This is a side-panel section, **not a toolbar badge**, notification or global Digital Lens.
- It does not auto-refresh when another device withdraws a source; clicking Check refreshes it. Views may remain stale between refreshes. Source withdrawal within this section clears before re-fetch.
- Only research connections with both source quotes and a historical memory ID appear; an invalidated finding is not displayed.
- A stale individual card in the original connection workflow might persist after a server-side withdrawal elsewhere until that flow is refreshed. Existing interaction surfaces need a full revocation UI audit.
- No native Chrome execution or extension smoke test was performed by this GitHub-only implementation session.

## Acceptance and independent review

1. Run the existing backend suite and `node --check extension/panel.js`, `node --check extension/background.js`.
2. Load unpacked Chrome extension and connect to an isolated backend with synthetic evidence.
3. Generate a real existing-API candidate, click Check, inspect exact excerpts and source identities.
4. Withdraw its historical memory; card immediately disappears; API list returns the same invalidated row only with scrubbed data, never as active.
5. Restart backend, refresh panel, confirm withdrawn candidate does not reappear.
6. Retry with unauthorized token; no content should appear and refresh must fail closed.
7. Confirm HTML / script strings inside evidence quotes remain inert text.
8. Check narrow panel width, keyboard use, no content shift on refresh, proper text wrapping.
9. Replay Claude's PR-A three failure probes; **do not claim hackathon readiness from this UI PR**.
10. No paid calls, changed Chrome host permissions, Meta inference, or ALIVE-14 pilot actions.

## Next stage after review

**PR-C design:** one independently qualified Meta claim comparison (exact-passage checks and explicit abstention) and an evidence fixture reflecting a genuine permitted source correction or clearly labelled synthetic case. Then evaluate whether a toolbar indicator adds real value. Only after PR-C should conversational Skill Forge be connected to the Evidence Watch story.
