# ALIVE-EVAL-02 R2 — Trust-Boundary Report

Baseline: `bce7bae` (`origin/main`, PR #51). Implementation branch
`feat/alive-eval-02-r2-trust-boundary` (this workstream).
No paid inference. No model calls. No Docker, Pi, or test-suite
reorganisation. v1 and R1 files preserved.

## 1. The R1 bypass (confirmed before fix)

Using the merged v2 evaluator unchanged, a submitter-authored package with an
invented custodian identity, self-written "adjudicated" gold, and a
caller-supplied `--sealed-root` containing a byte-identical custody record
with a self-asserted human boundary produced, via the real CLI:

`verdict: PROGRESS | custody: QUALIFIED | mode: qualified | sci: ESTABLISHED`
with `is_qualified_progress(receipt) == True`.

Reproduction script (scratch, not committed): `r1_exploit_repro.py`.
Re-running the identical command after the fix fails at argument parsing
(`unrecognized arguments: --sealed-root ...`, exit 2); no receipt is created.

## 2. Corrections (fail-closed only; no new trust invented)

- Trust-root overrides removed from every qualification path: no CLI flags, no
  function parameters, no request fields. Tests reach alternatives only by
  monkeypatching module constants in-process.
- QUALIFIED additionally requires: custodian identity in the active,
  unrevoked registry; canonical (repo-pinned) policy and contract; governed
  execution provenance; verified deterministic controls; sealed record with a
  detached signature binding the exact package identity and custodian; and
  signature math verified by a backend that does not exist yet — so the gate
  fail-closes (`signature_math_unverifiable`) and QUALIFIED stays unreachable.
- `verify_receipt` returns a `VerifiedReceipt` object; `is_qualified_progress`
  accepts only that type. Hand-typed dictionaries, forged fields, legacy v1
  receipts and the demo receipt all return False.
- `verify` reports the real enforcement state (`qualified_reachable: false`
  with explicit blockers) instead of directory occupancy.
- Decision fixes: D counts from the candidate arm (no cross-arm equalization);
  paired comparisons gated on overlapping scored cases; V records reused
  across arms rejected at binding; case-insensitive cross-family duplicate
  detection; legitimate unscored/pending cases fail closed as INCONCLUSIVE
  without count-validation errors.

## 3. R2 regression tests (all must fail closed; none may qualify)

Sealed-override CLI rejection; self-created sealed dir ignored; forged
signature; substituted/unregistered/revoked custodian; caller-modified policy
and swapped contract; handwritten outputs and missing governed-run receipts;
V record reuse across arms; casefold family duplicates; arm-specific
applicability with pending gold; hand-typed qualified receipts; substituted
artifacts; legacy receipts; verify-command enforcement reporting.

## 4. Results

- New R2 battery: 15 passed.
- Combined eval suites (`test_alive_eval01` untouched, `test_alive_eval02`,
  `test_alive_eval02_r2`): all pass.
- Full backend suite: **600 passed, 7 skipped, 1 xfailed**, exit 0
  (585 baseline + 15 new R2 tests; v1 suite untouched and green).
- `ruff check` + `format --check`: pass.
- Docker: NOT RUN — no container, application, dashboard, or dependency files
  changed; the `4b74f3c` container qualification carries over unchanged.

## 5. Remaining scientific-qualification prerequisites (unchanged)

No independent custodian; no sealed artifacts; no human-confirmed boundary;
no signature backend; no governed execution; no adjudicated panel; holdout
still pending. QUALIFIED is unreachable by construction, and that is the
intended secure state — not a defect.

## 6. Confirmations

- Independently authenticated custody exists: **NO**.
- Real model evaluation occurred: **NO** (0 calls, 0 tokens).
- Scientific qualification: **NOT ESTABLISHED**.
- Paid inference: **none**.
- Frozen evidence rewritten: **none**.
- No merge performed; draft PR only.
