# ALIVE-11 handoff

Baseline: `be47e18e329a1f1d932dbce253f703048c5fd3e3`.
Branch: `codex/alive-11-live-native-intelligence`.
PR: [#15](https://github.com/ernanhughes/alive/pull/15), review-only; initial head `2420fbf`.
Qualified source: `cb29c336760cb62e709da73a32553663ddde7e38` (v1);
second campaign `eb4c273a7922a558126e927d7951a7409ca1b444` (v2, identical
`alive/` and `extension/` code).
Worktree: `C:\Projects\alive-worktrees\alive-11`.
Later evidence/tooling commits retain identical alive/ and extension/ content.

The primary checkout remains on older `0809f37` with 25 preserved local files.
Its services/stores were left alone. Inventory is local at
`.alive/transition-primary-inventory.json` in that checkout.

Engineering PASS_WITH_LIMITATIONS. Docked Chrome synthetic and Meta journeys,
policy v11 restart and exact-note cold recall passed. Eight paid calls, 4,486
charged tokens, estimated $0.0123425. The explicit allowance is exhausted by call
count: no more paid inference under this campaign. Local checks: 142 backend,
seven frontend, eight extension; build and Ruff passed. Review final-head CI
separately; SQLite native qualification does not replace PostgreSQL CI coverage.

A second, separately approved campaign is frozen in
`archives/ALIVE-11/qualification-v2/`: eight validated calls, 4,246 charged
tokens, estimated $0.0113225, genuine docked side-panel target, policy v11
restart and all guards. Across both campaigns: 16 calls, 8,732 tokens and
$0.023665 estimated. Both allowances are consumed; do not rerun either paid
campaign without a new explicit approval.

Changes: authenticated runtime provenance, panel source display, optional persisted
cumulative spending ceiling, bounded raw-output/error evidence, service-worker/DOM
readiness and fresh-grant waits. Existing provider, Governor, permissions and
feedback policy remain authoritative. No new learner was added.
The native harness cleanup assumes the experience table exists: an early migration
failure could obscure its original exception. Qualified runs migrated successfully.

Research BEHAVIOUR_CHANGE_DEMONSTRATED; utility superiority unestablished. Scripted
feedback exercises branches. Adaptive synthetic comparison saves calls but misses
two opportunities. Paid baseline arms share three responses; they are not independent
trials. Lexical relevance can misread negation. Exact quotes do not prove whole-note
truth. Historical negative results remain intact.

See ALIVE-11.md, ALIVE-11-DEMO.md and the qualification archive README. The archive
retains diagnostic failures, preparation, approval, screenshots and usage; no
profiles, keys, env files or private history. The executed recall runner is archived
byte-for-byte; maintained script differs by a line-length formatting correction.
Recall uses a read-only original-store backup and disabled inference.

Publication is review-only: no merge, auto-merge or force-push. Obtain independent
review and inspect regression checks before integration. ALIVE-12 remains deferred.
