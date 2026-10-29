# ALIVE-NOTEBOOK-03A-R2 — Sealed-Holdout Handoff Contract

A sealed holdout is an **access boundary**, not a directory name. Until a
custodian supplies a package through this contract, the state is
`HOLDOUT_PENDING` and no final scientific verdict is possible.

## Custodian duties

1. Author genuinely unseen tasks (new source texts and families, not
   paraphrases of public cases) with `split: independent_heldout`.
2. Obtain two independent reviews plus adjudication per
   `adjudication_spec.md`; labels carry `external_attested` status.
3. Retain `tasks.json`, `annotations.json`, and `independent_submission.json`
   on an independently controlled account or machine the 03B implementer
   cannot access.
4. Run validation and scoring on that machine; share only package hashes,
   case counts, and aggregate reports.
5. Record access attestations and any exposure events. Any implementer
   exposure of answers invalidates blind use of that set for later tuning.

## Package layout (machine-readable part in `holdout_contract.json`)

- `tasks.json`: schema `task`, all splits `independent_heldout`.
- `annotations.json`: schema `annotation`, all `adjudicated` +
  `external_attested`, author distinct from at least two reviewers.
- `independent_submission.json`: schema `exposure`, `blind_eligible` true.
- No public task IDs, family IDs, or source hashes may be reused.

## Structural validation (what the CLI checks)

Family/split/gold completeness, attestation shapes, hash consistency, and
exposure flags. These checks validate **structure only**: they do not prove
operating-system access restrictions or human identity. A human reviewer
must verify the separate-account boundary before treating results as blind.

## Status values

- `HOLDOUT_PENDING`: no custodian package supplied (current state).
- `SEALED`: a package validated structurally on the custodian machine.
- Exposure or reuse events return the state to pending-equivalent
  (that set must never be used as a blind test afterwards).
