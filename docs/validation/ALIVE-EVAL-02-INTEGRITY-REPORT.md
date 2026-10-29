# ALIVE-EVAL-02 — Integrity Report

Baseline: `4b74f3c6337c5be839a3ef9e6044b409e3ce08f9` (`origin/main`, Docker-qualified).
Implementation: HEAD of `feat/alive-eval-02-integrity` at push time.
No paid inference. No model calls (offline only). No Docker, Pi, or test-suite
reorganisation changes.

## 1. Historical reconciliation (summary)

Full record: `ALIVE-EVAL-02-PHASE-1-RECONCILIATION.md`.
Revalidated against current `main`: 9 findings retained as working or correctly
unqualified; 10 confirmed STILL_PRESENT (incl. the central custody forgery,
reproduced on `4b74f3c`); 2 NOT_TESTED at Phase 1 (now resolved below).

## 2. Attack reproduction matrix (all run against v2)

| # | Attack | Result |
| --- | --- | --- |
| 1 | Self-created custody record (distinct invented custodian) | INCONCLUSIVE, IMPLEMENTED_UNQUALIFIED, no PROGRESS |
| 2 | Public cases relabelled as sealed holdout | public_diagnostic, INCONCLUSIVE |
| 3 | Self-declared independent adjudicator | INCONCLUSIVE, never QUALIFIED |
| 4 | Changed protocol + recomputed hash + permissive policy | INCONCLUSIVE (self-consistent but unqualified) |
| 5 | Arbitrary scorer substitution | Rejected (claimed hash must match executing scorer); self-consistent variant stays unqualified |
| 6 | Synthetic model outputs without governed execution | INCONCLUSIVE + IMPROVEMENT_OBSERVED, provenance marked `offline_fixture_unprovenanced` |
| 7 | Replayed outputs from another package | Binding error; package-identity mismatch on verify |
| 8 | Rewritten gold labels after evaluation | `verify_receipt` fingerprint mismatch |
| 9 | Fabricated independent controls (all arms perfect) | NO_PROGRESS + NO_IMPROVEMENT_OBSERVED (identical controls demonstrate no advantage) |
| 10 | Multiple artificial family IDs on near-duplicates | INCONCLUSIVE, cross-family duplicate reason |
| 11 | Unpinned bootstrap seed | Rejected (must equal evaluator-pinned); identical intervals across runs |
| 12 | Incomplete/substituted receipt inputs | Rejected (missing field / fingerprint mismatch) |

## 3. Corrections made

- Machine-enforced custody states (`CUSTODY_NOT_ESTABLISHED` /
  `IMPLEMENTED_UNQUALIFIED` / `QUALIFIED`) derived by verification, never from
  manifest strings. `QUALIFIED` requires a sealed artifact in the
  repo-pinned sealed root plus a human-confirmed boundary; the sealed root is
  empty, so `QUALIFIED` is unreachable by construction.
- `evaluation_mode`: `qualified` only under `QUALIFIED` custody, else
  `diagnostic`. Verdict `PROGRESS` only when qualified; diagnostic outcomes use
  `IMPROVEMENT_OBSERVED` / `NO_IMPROVEMENT_OBSERVED` / `INDETERMINATE`.
- Receipts bind SHA-256 of task package, gold, outputs, contract, policy,
  protocol, scorer, package identity, source commit, evaluator version, trust
  roots and pinned bootstrap. `verify_receipt` recomputes and rejects
  tampering, substitution and cross-package replay.
- `is_qualified_progress` consumer gate: exactly one acceptance shape; v1
  receipts, the demo receipt and all self-attested v2 receipts return False.
- V comparator: D must show non-inferiority vs the evaluation-informed
  shortcut (paired D−V retention lower bound ≥ 0, misleading upper bound ≤ 0;
  zero boundary, no invented margin). Missing V outputs → INDETERMINATE.
- C gates no longer veto D; C absolute performance recorded diagnostically.
- Wide-but-straddling intervals → INDETERMINATE; demonstrated failure only on
  fully-cleared-against evidence → NO_PROGRESS.
- Counts computed per arm with equality enforced across compared arms;
  mismatch rejects the package.
- Operative bootstrap fixed to the repo-pinned seed/resamples/level; caller
  contract values must match exactly or evaluation is rejected.
- The two v1 tests enshrining self-attested PROGRESS are superseded by v2
  fail-closed assertions (same scenarios); v1 code and its suite are
  byte-unchanged as the historical implementation, and v1 receipts can never
  satisfy `is_qualified_progress`.

## 4. Receipt and custody contract

Every v2 receipt carries `custody_state`, `evaluation_mode`, `verdict`,
`diagnostic_result`, `scientific_qualification`, `scope_determined`, custody
facts, sealed-match detail, full fingerprints (incl. `package_identity`,
`source_commit`, trust-root and bootstrap hashes), metrics, uncertainty,
decision diagnostics, reasons and an authoritative-summary flag pinned False.
`scientific_qualification` is ESTABLISHED only for qualified PROGRESS;
all current outputs read NOT_ESTABLISHED.

## 5. Test results

- New `tests/test_alive_eval02.py`: **23 passed**.
- Full suite `pytest -q`: **585 passed, 7 skipped, 1 xfailed**, exit 0.
- `ruff check` + `format --check` on all touched files: pass.
- Windows provider timeout/budget tests (3 runs each): pass; historical
  intermittency NOT_REPRODUCED on current main; left unmodified, noted for
  continued observation.
- Docker container tests: NOT RUN — this branch touches no container,
  application, or dashboard files (scripts/tests/docs/evaluations only), so
  the Docker qualification from `4b74f3c` carries over unchanged.

## 6. New acceptance tests

The 23-test battery (§2 plus positives): valid diagnostic reports improvement
without qualifying; qualified-unreachable assertion; v1/demo receipts rejected;
structural-invalid custody fail-closed; count-equality unit test; determinism;
V-regression and C-no-veto behavior; straddle calibration; missing-arm
indeterminacy; CLI verify/evaluate/verify-receipt round trip.

## 7. Remaining limitations

- No independent custodian exists: `QUALIFIED` unreachable, scientific
  qualification NOT_ESTABLISHED by construction. A real qualification requires
  a reviewed commit adding a custodian identity, sealed artifacts and a
  human-confirmed boundary — explicitly out of scope here.
- Governed execution provenance is recorded but unavailable: all model outputs
  remain `offline_fixture_unprovenanced`; qualified mode additionally requires
  authorization, identity and usage evidence that does not yet exist.
- Annotation holdout remains `HOLDOUT_PENDING` (0 cases); preserved as
  diagnostic-only, never reframed.
- No frozen evidence rewritten; v1 implementation and its suite untouched.

## 8. Required confirmations

- Independently authenticated custody exists: **NO**.
- Real model evaluation occurred: **NO** (0 calls, 0 tokens).
- Scientific qualification: **NOT_ESTABLISHED**.
- Paid inference: **none**.
