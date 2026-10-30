# ALIVE-EVAL-02 — Phase 1 Reconciliation (old review vs `main @ 4b74f3c`)

Sources reviewed at 4b74f3c: `scripts/alive_eval01_custodian.py` (689 lines),
`scripts/alive_eval01.py`, `tests/test_alive_eval01.py` (~700+ lines),
`docs/ALIVE-EVAL-01-{DESIGN,TRUST-MODEL,REPORT}.md`,
`evaluations/alive-eval-01/{custodian_policy,controls_registry,holdout_status}.json`,
`docs/validation/alive-eval-01/{custodian-verify,demo-receipt}.json`.

## Reconciliation table

| Historical finding | Status on current main | Evidence |
| --- | --- | --- |
| Metrics recomputed from per-case records | Retain (working) | `score_r2` + `gated_flags` recompute; caller summary echoed with `summary_authoritative: False`; `test_honest_receipt...` asserts recompute |
| Exact citation + output-set binding | Retain (working) | `verify_binding`: exact offsets, source-hash match, claim-ref match, no missing/duplicate/substituted outputs; battery covers swaps |
| Self-attested custody can produce PROGRESS | **STILL_PRESENT** (blocker) | Reproduced 2026-10-29: invented distinct custodian string + self-written `adjudicated external_attested` gold → `PROGRESS` + `blind` + `custody_valid: True`. Control (custodian == submitter) → INCONCLUSIVE. Repo tests `test_honest_receipt...:300` and `test_every_policy_param...:642` enshrine the defect as expected behavior |
| Receipt lacks full input fingerprints | **STILL_PRESENT** | Receipt binds only protocol + scorer fingerprints; no task-package, gold, outputs, contract, or policy hashes recorded (`evaluate()` lines 482–497) |
| Scorer/protocol/contract trust not independently pinned | **STILL_PRESENT** | Policy file, protocol dir, and all claimed hashes are submitter-supplied and only checked for self-consistency; only the executing scorer module hash is locally anchored. `verify_fingerprints` compares claim vs supplied protocol, not vs an independent pin |
| Model outputs accepted without governed execution | **STILL_PRESENT** | `score_r2(..., allow_offline_fixtures=True)`; outputs are files with no execution provenance, authorization, usage, or identity binding |
| Comparator V required but not meaningfully evaluated | **STILL_PRESENT** | `pair_diffs` computes only D–S and D–C; no D–V comparison gates the verdict despite V being a required arm |
| Incorrect C-dependence for D progress | **STILL_PRESENT** | Absolute/citation gates loop over `("C", "D")` (lines 576–586): C failing its gates forces NO_PROGRESS even if D demonstrates improvement |
| Wide uncertainty → NO_PROGRESS instead of INCONCLUSIVE | **STILL_PRESENT** (by code reading) | Any failure containing "gate"/"margin"/"interval"/"tolerance" → NO_PROGRESS (lines 606–613); underpowered short-circuit exists but powered-wide intervals read as failure rather than inconclusive |
| Misleading family diversity from arbitrary labels | **STILL_PRESENT** | Families come from submitter `task.family`; no independence validation of family assignment |
| Incorrect count aggregation across arms | **STILL_PRESENT** | `useful = max(...)`, `scored = max(...)` over arms (lines 523–524) inflates eligibility |
| Caller-controlled bootstrap seed | **STILL_PRESENT** | Seed comes from submitter contract file; `validate_decision_contract_strict` only checks type, no independence |
| Unenforced uncertainty settings | **STILL_PRESENT** | `uncertainty_policy` loaded (line 88) but never consumed in verdict logic |
| Annotation holdout not independently established | Retain as unqualified (no code defect) | `holdout_status.json`: HOLDOUT_PENDING, 0 cases; trust model + report correctly state unqualified posture. Preserve; do not reframe |
| Windows timeout/budget test intermittent | **NOT_TESTED** | No timeout test in `test_alive_eval01.py`; referenced test lives elsewhere — locate during Phase 8 |
| Legacy `decide` command producing misleading progress | **NOT_TESTED** | CLI has only `verify`/`evaluate`; R2 `decide_progress` usage needs audit in Phase 7 |

## What the old review got right (retain)

Strict loaders, NaN/Infinity rejection, zero-disabler rejection, unknown-key
rejection, recomputed metrics, citation/binding gates, family bootstrap
mechanics, V-registry labeling, `entailment: requires_human_adjudication`.

## Reproduction artifact

`eval02_repro.py` (scratch, not committed): distinct-string custodian forgery
→ PROGRESS/blind/valid; same-string control → INCONCLUSIVE. Run from a
checkout with `python eval02_repro.py`.
