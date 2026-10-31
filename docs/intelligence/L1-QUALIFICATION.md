# Level 1 qualification — Stage A

Status: **NOT QUALIFIED; focused hardening for independent review.**

## Starting state and scope

Remote `refs/heads/main`, local `origin/main`, and the clean primary checkout all resolved to
`4e990bfadb886eba933a88f1c07e1b2543ab8f02` at audit. The primary checkout was on
`codex/l1-01-live-admission`; it was not switched or modified. Work uses the separate
`C:/Projects/alive-l1-qualification` worktree, branch `codex/l1-qualification`.
Eight pre-existing worktrees were enumerated and left intact. No open GitHub PRs were returned;
the Codex chat inventory showed no other active ALIVE Codex chat. Other tools/processes are
not exhaustively observable, so isolation is retained regardless.

PR #82 is merged. Its head `98938c9443e598e340fb9ea41ef1643498617f9a` passed
[CI run 41236492418](https://github.com/ernanhughes/alive/actions/runs/41236492418), including
Windows/Linux backend, dashboard/extensions, PostgreSQL first-contact and notebook jobs.
This is previous-head evidence, not qualification of this branch. The GitHub PR discussion
returned no comments; there is no independent security acceptance in that evidence.

## Implementation-gap assessment

| Layer | Code inspected / reused | Assessment |
| --- | --- | --- |
| PI-01 / PI-02 | Pi runner/gateway/egress; WorkflowRunner; scoped context/grants | Existing executor, reservation, dispatch fence, accounting and cancellation retained |
| PI-03A / PI-03B | capability bindings/trusted registry; source custody and source adapters | Existing exact captures, operations and immutable capability identities retained |
| BESPOKE-01 | recipe catalogue, selector eligibility/ranking, handoff | Deterministic selection exists; no governed semantic interpretation or generated compositions |
| INT-02 | intelligence receipts and independent-feedback custody | Existing role receipts are not a complete live repository outcome/evaluation/promotion contract |
| L1-01 | admission prepare/approve/start/current_terms | Real local owner confirmation exists; bearer access cannot approve |
| L1-02 | analysis context/contracts/adapters/validation/report, disclosure and dashboard | Real bounded model analysis exists; findings remain semantically unverified |
| PI-03C | repository citation validator plus existing reference/controlled-comparison implementations | Reuse these; general file/page locator and composed validation milestone still unqualified |
| L2 / L3 | programme contracts in architecture document | Remain subsequent milestones; no superiority or adaptive-improvement claim |

Read alongside L1-01, all L1-02 documents, PI-03C plan, Bespoke architecture/delivery/security,
PI-03B security and INT-02 review. Some older documents describe historical pre-integration gaps;
code and this audit take precedence over those delivery snapshots.

## Defects reproduced and hardening

1. Disclosure used the base URL's hostname while dispatch preferred `ALIVE_META_URL`. An
   after-approval override to another host still completed. Same-host port/path changes were
   also absent from the immutable terms. New regression failed on the integrated implementation.
2. A settings change immediately after the dispatch fence substituted the actual destination.
   A second regression observed the unapproved URL before the snapshot fix.

One credential-free endpoint resolver now supplies both disclosure and dispatch. The exact
HTTPS endpoint joins the existing immutable review; existing approve/start/reservation/fence
rechecks compare the full disclosure. The dashboard displays the endpoint with a historical
host fallback. The upstream gateway deep-copies configuration before Pi starts, preventing
post-fence substitution. Subsequent workflow checks still refuse changed live configuration;
the dispatched request remains at its approved destination and the workflow reports UNKNOWN.
HTTP redirects are explicitly refused without retry, and classified as a fatal provider error.
Admission rejects unsafe URL shapes before showing or persisting disclosure terms.

No new executor, model client, provider, capability, permission, security allowlist or schema
migration was introduced. The model, role, input digest, invocation ceiling and source controls
are reused unchanged. Old pending approvals without exact endpoint terms require a fresh review;
completed history is not rewritten. No live or paid inference was used.

## Qualification evidence

| Check | Observed result |
| --- | --- |
| Analysis end-to-end/adversarial, units, provider destination and gateway tests | 129 passed before the additional reservation/post-fence probes |
| New reservation integration probes | 3 passed |
| Direct reservation guard probes with successful controls | 3 passed |
| Real pinned Pi, scripted upstream: owner journey, retained-event confidentiality, override disclosure and post-fence substitution | 4 passed after the gateway snapshot |
| Owner admission and Pi egress regressions | 55 passed; final gateway/parity/egress/post-fence recheck: 64 passed |
| Dashboard Admission component tests / production build | 7 passed / built |
| Docker image / disposable PostgreSQL application | Built with pinned Pi 1.4.0; migrations applied and application started |
| Docker smoke / existing HTTP journey groups | Rebuilt after gateway snapshot: 8 smoke checks / 6 groups passed |
| Full backend, PostgreSQL migration suites, dashboard/extensions on final head | Delegated to CI; do not infer green from previous-head CI |
| Model-backed Admission browser E2E | Not implemented/run; component tests and HTTP journeys do not close this gap |
| Independent security review | Pending; author probes are not independent approval |

Windows tests emit the existing Proactor/ZeroMQ selector warning. Scripted responses qualify
authority and classification, not a live model's semantic accuracy. Token/cost/latency/storage
benchmarking remains unqualified; existing unknown usage/cost semantics are preserved.

## Mutation method and receipts

The original merged campaign already covered 25 single and 3 compound mutants, contrary to the
outdated handoff. Its harness mutated its own checkout and counted arbitrary test failures as
kills. Stage A replaces that with one `git archive` copy of an immutable commit per mutant,
offline scripted-provider tests, exact-pattern validation, persistent stdout/stderr and JSON
receipts. A kill needs an assertion failure, not collection/setup/runtime failure alone.
Unknown IDs fail rather than silently running nothing. Run receipts outside the checkout:

```powershell
python scripts/l102_mutations.py --baseline <commit> --output C:/disposable-evidence/mutations.json
```

The first replay uses `9a27056`; direct authority probes use `c15bff5`; the stronger redirect
probe uses `fb19c27`. Each receipt carries its full immutable baseline and exact test command.
Final dispatch-snapshot mutation and aggregate results are recorded with the delivery evidence.
All deliberate edits occur in temporary copies. The primary checkout remains clean.

Receipts and losslessly gzip-compressed test logs live in [validation/l1-stage-a](validation/l1-stage-a/).
Across 33 unique mutants, using the stronger follow-up probes where available: **30 killed,
2 invalid, 1 equivalent survivor**. M01/M02/M03 now have direct reservation kills, each with
a passing control before changing one authority term. M25–M29 cover exact endpoint terms,
effective URL resolution, redirects, unsafe URL shapes and configuration snapshot respectively.
The first four superseded logs (M01/M02/M03/M27) were overwritten by follow-ups; their original
JSON outcomes remain, explicitly marked without available original logs. Follow-up logs are
retained. The harness now uses a distinct log directory per output receipt to prevent that loss.

Production source and dashboard code were last changed at
`0c268eea2390faa9b945d3ca3c116896987f9030`; subsequent delivery changes concern documentation,
receipts and mutation-log output naming. Final delivered SHA and CI are recorded on the draft PR.
The final smoke image is
`sha256:ef8d3a5fa7987bbe59bf2f894d0646aae94445aeefe3acedd35e2dd75b0de8f4`.

M10b's survivor is equivalent under immutable source approvals: the preparation layer already
requires disclosure approval; withdrawal/expiry are also checked by the inspect operation.
M16 and M21 currently produce runtime exceptions instead of the expected refusal/classification
when mutated, so this stricter campaign records them as invalid, not killed. They need stronger
isolated behavioral probes before claiming complete mutation qualification. M01's first attempt
also hit a shared real-Pi setup timeout (no runtime in that copy); the subsequent direct guard
probe kills it without subprocess dependencies. Original attempts remain in the receipts.

## Security boundary and review gate

Exact endpoint binding is an application control. It does not provide network host/IP allowlists,
DNS pinning, proxy isolation, local inference, provider-side attestation or guarantees about a
remote provider's retention. Explicit source disclosure and execution authorization remain
separate. Citation validity still proves neither semantic support nor task success.

The real-Pi canary probe inspects persisted `pi.rpc.event` payloads for source and response
canaries. It passes, but source captures, invocation prompts/responses, stage outputs and reports
remain clear text in the local database. Withdrawal stops future use; it does not delete data.
Encryption, purge/retention policy and acceptable sensitivity remain open owner decisions;
this PR does not invent consent or change immutable history.

Stop at the draft hardening PR and independent review gate. Do not advance dependent PI-03C/L2/L3
implementation until the necessary security contracts are qualified. Next work is independent
review of destination binding, stronger M16/M21 probes, the full model-backed browser journey,
final-head CI and an explicit retention/sensitivity policy decision.
