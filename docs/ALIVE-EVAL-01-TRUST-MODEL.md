# ALIVE-EVAL-01 — trust model

## What is trusted, and why

| Claim | Trust anchor | Status |
|---|---|---|
| Tasks/gold used for a verdict are the custodian's | Package and gold hashes pinned in a custody record held outside the submission directory; evaluator re-hashes both | Mechanism implemented; organizational separation NOT established |
| Metrics reflect per-case records | Custodian recomputes from submitted outputs; caller aggregates echoed only | Implemented, forgery-tested |
| Scope is blind | Derived from package splits + custody validity + adjudicated gold, never from a caller flag | Implemented |
| Thresholds/contract are the frozen ones | Strict loader; unknown/missing/contradictory/disabling values rejected | Implemented |
| Scorer is the reviewed one | Executing module hash + version checked against custodian pins | Implemented |
| Custody is independent | Custodian identity distinct from submitter + human-confirmed access boundary | NOT established (no independent custodian exists) |
| Gold is independent | Two reviewers + adjudicator, external attestation, no answer exposure | NOT established (no panel convened) |
| Semantic progress shown | Governed experiment under this custody | NOT_RUN |

## What the mechanism cannot do

- It cannot prove organizational independence. Structural checks (hash
  binding, identity inequality, directory separation) raise the cost of
  forgery and make it auditable, but a submitter who controls both
  directories can still manufacture a passing package. That is why the
  maximum achievable verdict today is `IMPLEMENTED_UNQUALIFIED`, and why
  `QUALIFIED` additionally requires a human-confirmed boundary plus real
  adjudicated gold.
- It cannot blind annotators who already hold repository access. Renaming,
  opaque handles, and field hygiene do not erase recognizable text.
- It cannot detect a leak it cannot see. Answer exposure that happens
  outside logged channels is undetectable by construction; the mitigation
  is procedural (need-to-know handling, exposure logging, invalidation on
  any reported exposure).

## Verdict semantics

- `PROGRESS`: only on a blind, custodied, fully compared evaluation whose
  intervals clear every gate — currently unreachable, by design, until
  03B runs under custody.
- `NO_PROGRESS`: gates evaluated and failed (a negative result is acceptable).
- `INCONCLUSIVE`: missing comparators, holdout, gold, or underpowered
  evidence. An invalid positive result is not acceptable, so uncertainty
  defaults to `INCONCLUSIVE`, never to success.

## Custody states

- `CUSTODY_NOT_ESTABLISHED`: no validated custody record (current state
  for all real evaluations).
- `IMPLEMENTED_UNQUALIFIED`: mechanism built, forgery-tested, but no
  independent custodian or gold (current EVAL-01 state).
- `QUALIFIED`: independent custodian holds sealed tasks and adjudicated
  gold, boundary human-confirmed. Requires evidence that does not exist yet.
