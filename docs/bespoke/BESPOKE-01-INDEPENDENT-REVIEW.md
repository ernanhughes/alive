# Independent review gate — pending

This file is a handoff, not an independent verdict. No independent reviewer has approved this
implementation. The PR must remain draft and must not auto-merge.

Review the PR head and CI links in the PR description. The baseline is integrated main
`495e4fedaeacedbec33e94b77a485c26dd792a34`. Phase commits separate contracts/catalogue,
selector/handoff, dashboard, and evaluation/hardening.

## Required review

1. Audit the restricted-reader extraction for PI-03A regressions. Verify recipe pins cannot import
   code, silently pick latest versions, change grants or register definitions.
2. Trace actual source custody from an existing scoped grant through observation and explicit
   objective. Test a false URL/type claim, malicious prose and source substitution independently.
3. Remove/alter feasibility checks and require relevant behavioral assertions to catch them.
   Add independent mutants for workflow/capability/recipe identity, context ownership, permissions,
   budgets, source approval, availability, ranking, record identity and execution separation.
4. Verify request retry isolation, immutable history, restart/retirement reads and failed handoff
   after revocation or changed deployment state. Review PostgreSQL migration and actual run links.
5. Inspect mobile/desktop UI, credential rejection, request races, empty/unavailable states and
   graph identity. Verify historical replay/inspection emits no writes or model calls.
6. Run the local package, explicit disposable PostgreSQL demonstration, Docker smoke and final-head
   Windows/Linux CI. Check source/image parity and the exact tested head in the PR description.
7. Confirm PI-03B/03C, production owner approval, semantic truth, independent outcome feedback,
   model-assisted selection, adaptive composition and automatic learning are not claimed complete.

## Acceptance evidence

`validation/` retains local demonstration, PostgreSQL demonstration, evaluation, mutation and
desktop/mobile screenshot receipts. `BESPOKE-01-DELIVERY.md` explains measured checks and limits.
These implementation-authored receipts do not replace fresh independent adversarial evidence.

A model cannot approve itself, and a successful workflow does not approve the selector policy.
Return a clear GO / REVISE verdict with concrete findings against the reviewed exact head.
