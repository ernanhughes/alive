# PI-03A-R2: corrections after independent review

Review verdict being answered: **REVISE** (`ALIVE-PI-03A-R1-INDEPENDENT-REVIEW.md`, reviewed head
`e0db4ae`). This round repairs the confirmed findings and changes no architecture. PR #76 stays
a draft and unmerged; PI-03B, PI-03C and any selector are not started.

The completion criterion was: the engine invokes precisely the implementation pinned by its
authorized binding, capability identity is stable across history, declared boundaries are enforced,
and the regression gates support the result. Read "Not verified" before relying on any of it.

## Disposition of every finding

| Finding | Disposition | Where |
| --- | --- | --- |
| F1 runner used a global adapter | **Fixed.** `ADAPTERS` is removed. `invoke()` has no callback parameter; the only resolver is `registry.adapter_for(identity)`, which re-verifies the retained id, version, manifest hash and fingerprint. | `execution.py`, `registry.py`, `runner.py` |
| F2 fingerprint missed the mapping | **Fixed.** The adapter is an explicit `module:function` reference; the fingerprint covers kind, effects, adapter, legacy binding, interface, ceiling, traits, source list and bytes. Legacy implementations also list `workflows/context.py`. Non-transitive limit documented. | `trusted.py` |
| F3 POSIX FIFO hang | **Fixed.** `O_NONBLOCK`/`O_NOCTTY` on file opens; oversize or non-regular `.gitignore` fails closed with a named reason; Windows device names refused. | `repository.py` |
| F4 legacy adoption too broad | **Fixed by provenance.** DAG-only contract only for a row that exists without a binding, or a shipped definition by exact hash (two). New definitions meet the full contract, atomically. | `store.py`, `bindings.py`, `trusted.py` |
| F5 migration head assertions | **Fixed** earlier (`df85640`). Full CI green on every job at that head. | tests |
| F6 registry not authoritative | **Fixed.** Graph route, seeding, Intelligence linkage and the catalogue API use the application registry or none; an AST test guards production call sites. | `api.py`, `store.py`, `intelligence/store.py` |
| F7 pre-PI-03 history depended on the catalogue | **Fixed.** Read from the stored, hash-verified definition; never attributed an identity. | `bindings.py`, `spec.py` |
| F8 reuse not YAML-only | **Fixed with traits** (below). All five reusable implementations run end to end under new ids. | `trusted.py`, `runner.py`, `adapters.py`, `store.py`, `observatory.py`, `intelligence/receipts.py` |
| F9 retention / exposure | **Decided and enforced** (below). | `kernel.py`, `app.py` |
| F10 references ignored the fingerprint | **Fixed**, API and dashboard link. | `api.py`, dashboard |
| F11 DEL/C1 controls | **Fixed.** | `manifest.py` |
| F12 duplicate enum | **Fixed** (refused). | `contracts.py` |
| F13 large `.gitignore` | **Fixed** (named refusal). | `repository.py` |
| F14 stale disable entry | **Accepted as designed**, clearer message. A silently ignored typo would leave a capability enabled. | `registry.py` |
| F15 activation used the newest version | **Fixed.** Pinned stages are judged by their pinned version. | `registry.py`, `spec.py` |
| F16 internal paths in the operations listing | **Fixed.** | `operations.py` |
| F17 narrower context | **Accepted** (least privilege); PI-03B must define `repository-context/v1` if inputs are needed. | docs |
| F18 non-transitive fingerprint | **Documented**, concrete uncovered helpers listed. | security doc |
| F19 no production snapshot approval | **Unchanged**, PI-03B prerequisite. | security doc |
| F20 surviving mutants | **Addressed**: tests added, campaign extended. | below |

## Decisions that need the owner's eye

1. **Retention (F9).** `persistence: none` now documents exactly one thing: the capability may not
   create a `workflow_result` artifact. Stage output is always kept in run history. The generic
   event feed no longer carries it and is instance-scoped. Still open: other event types remain on
   the feed, any API-token holder can read it, and there is no retention period or deletion path.
2. **Two shipped definitions keep the PI-02 contract by exact hash** (`research-review` v1 and the
   `intelligence-fixture` v1 harness). Re-issuing them as new versions is the retirement path.
3. **Traits** are a new concept: code-owned, fingerprinted, never declared in YAML. Please review
   the four defined (`model.role`, `result.writer`, `validation.independent`,
   `validation.reference-identity`) and which implementations carry them.

## Evidence

All commands are from the repository root.

| Check | Result |
| --- | --- |
| Full CI at `df85640` (F5 fix) | All jobs pass: backend Ubuntu and Windows, dashboard, PostgreSQL first-contact, notebook |
| Pi-backed suites (fence, r3 guards, transactions, history) with the pinned Pi installed | 88 passed |
| Suites reading the events API | 131 passed, 6 skipped |
| Registration, API, spec, store | 149 passed |
| Linux (reviewer's image): `tests/test_capability_repository.py` incl. real FIFOs | 37 passed; with `O_NONBLOCK` removed, the two discriminating FIFO tests fail by timeout |
| PostgreSQL 16, disposable database: real run, downgrade to 0010, re-upgrade | Passed: row counts preserved, snapshots `{}`/NULL (not invented), runs inspectable and unlabelled, one head `0011`, genuine-history adoption of the re-registered definition |
| Dashboard: `src/capabilities` and `src/workflows` tests, production build | 59 passed, build clean |
| Final broad focused regression for this round | see "Final head" |

### Mutation campaign

`scripts/capability_mutations.py`: **44 single-guard mutants, 44 killed, 0 survived, 0 invalid**, each
with a passing baseline in a temporary copy. Receipts: `validation/mutations.json`.

- C1-C19: the author's original campaign, re-run after the changes.
- R1-R6b: the reviewer's independent survivors (runtime resolving "latest", skipped identity
  recheck, legacy gates, fingerprint ignoring source bytes, ignored version pin, references
  ignoring the manifest hash and the implementation fingerprint). All killed.
- F-series: one mutant per correction.

How the final count was reached, because the first full run was not clean: it killed 41, left F8a
and F8c alive, and counted F3b invalid (the mutation left a syntax error, which the harness
correctly refuses to count). Causes, all in my tests or table, none in the product: the artifact
route maps every failure to one 404, so F8a's test could not tell the trait guard from an
accidental crash (now asserts the explicit refusal at the point it is raised); F8c needed a stage
that *passed* validation without the reference trait; F3b's pattern was malformed. After fixing
those, only those three mutants were re-run and merged. A separate first attempt aborted on a
failing baseline (C19) because the F15 change made activation refuse earlier than the runner's own
check; the test now proves both layers independently.

Redundancy disclosed: a changed manifest is refused by three checks (identity compare at recheck,
identity compare at the grant check, and the policy hash). C1 therefore removes all three together.

Not mutated, deliberately or for lack of a hook: the observatory and Intelligence-receipt
`model.role` guards (defence in depth; `model_claim` already enforces the exact implementation at
dispatch, and no test fabricates a Pi run on a non-model stage); `O_NONBLOCK` (needs a POSIX
host; proven by hand in Linux as above); parser rejection rules (own adversarial tests).

## Not verified

- **CI at the new head.** Nothing in this round has run on GitHub yet. Do not treat the evidence
  above as CI. The result is recorded under "Final head" once it exists.
- Browser E2E (Playwright), extension, Docker build and Docker smoke were not run in this round.
- PostgreSQL was exercised for migration and history only, not the full suite.
- Pi evidence is against a scripted provider; no paid inference was used.
- Fingerprints remain non-transitive.

## Final head

The exact head SHA and its CI result are recorded in the PR #76 description, not here: recording
them in a commit would itself create a new head and restart the full CI run. If the PR description
shows no passing run for the current head, the round is not qualified.

Local focused regression for this round (capability, workflow, Intelligence and migration suites,
Pi architecture boundaries): 532 passed, 4 skipped, 1 failed. The one failure was a hand-built
dependency in `test_record_requires_actual_validation_dependency` that lacked the new
`implementation` field; it was corrected and passes (11 passed in that file). This is a local
result on a Windows host with the pinned Pi installed, not CI.
