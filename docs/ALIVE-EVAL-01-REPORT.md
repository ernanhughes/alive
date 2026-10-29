# ALIVE-EVAL-01 — engineering report

Decisions:
**Engineering: READY_FOR_REVIEW.**
**Evaluation custody: IMPLEMENTED_UNQUALIFIED.**
**Semantic experiment: NOT_RUN.**

Nothing here claims independent custody, independent gold, or semantic
progress. The mechanism is built and forgery-tested; the trust anchors it
needs do not exist yet.

## Delivery and provenance

- Base: `0375fb4b56658aa3e6e5dbfe2abb54ccab9be858` (`origin/main`, PR #47 merged).
- Branch: `codex/alive-eval-01-trusted-custody`.
- v1.4, v1.5, v1.6 frozen files preserved byte-unchanged; their freezes
  and 69 tests still pass.
- New: `scripts/alive_eval01{,_custodian}.py`, `tests/test_alive_eval01.py`
  (24 tests), `evaluations/alive-eval-01/` (custodian policy, v1.7
  amendment record, controls registry, citation study, annotation
  handoff, holdout status), R2 annotation package v1.7 revision,
  docs `ALIVE-EVAL-01-{DESIGN,TRUST-MODEL,REPORT}.md`,
  `ALIVE-EVAL-01-NOTEBOOK02-DEPS.md`, validation under
  `docs/validation/alive-eval-01/`, CI additions.
- Local: Windows 11, Python 3.13.3, locked uv dependencies.
  `pytest`: **93 passed** (30 v1.4 + 18 v1.5 + 21 v1.6 + 24 eval-01).
  `ruff check` + `format --check`: **pass**. Hosted CI runs the same
  custodian paths after push (logs pending).
- Execution: **0 model calls, 0 tokens, USD 0.00**. No production Core,
  Governor, approval, payment, migration, browser-permission,
  source-document, or archive code changed.

## What was built and verified

- Custodian evaluator: recomputes metrics from per-case records against
  custodian tasks/gold; verifies claim binding, exact citations, source
  hashes, protocol/scorer fingerprints against custodian pins; derives
  family counts from the actual package; runs the operative family
  bootstrap; applies eligibility then the decision rule; emits a receipt
  binding verdict to input hashes. Caller aggregates echoed only.
- Forgery battery (14 attacks, real code path): one-case holdout,
  forged ADJUDICATED flag, modified gold/protocol/scorer hashes,
  public-scope flag on public tasks, fabricated metrics, changed task
  set, replayed outputs, same-ID content swap, missing hash/schema,
  invalid freeze, tampered scorer, missing comparators, self-issued
  custody, scope confusion. All fail closed or `INCONCLUSIVE`; none
  yields `PROGRESS`.
- Review's heuristic numbers reproduce R1 `PROGRESS` under the old
  function and yield `INCONCLUSIVE` under custody (public scope; no
  holdout; provisional gold).
- Operative uncertainty: interval bounds gate the verdict; identical
  systems fail margins ([0,0] clears nothing); imbalance warned;
  underpowered samples forced `INCONCLUSIVE`; gated flags match scorer
  exactly.
- Threshold integrity: NaN/Infinity rejected at read; exclusive
  confidence bounds; zero-disabler rejection (precision, recall flag,
  retention floor, misleading cap); unknown/missing/contradictory keys
  rejected; every policy parameter shown to change a decisive outcome.
- Shortcuts: S template-informed, V evaluation-informed (registry with
  code hashes); V not rewritten; final gate does not rely on S alone.
- Annotation v1.7: hashes/access cues removed, disputes framed as open
  questions, handles/salts out of annotator hands; audit passes R2,
  fails R1 (68 findings) and tampered variants.
- Citation: 0.2 floor justified as a dump filter from the measured
  length distribution (required 20–286, median 72; dumps ~0.08–0.11);
  entailment explicitly requires human adjudication on every receipt.

## What is NOT established

- Independent custody: `CUSTODY_NOT_ESTABLISHED` for all real evaluations.
- Independent gold: `PENDING_INDEPENDENT_LABELING`; no panel convened.
- Sealed holdout: `HOLDOUT_PENDING`; no package supplied.
- Semantic capability: `NOT_RUN`; C/D have never executed.
- Custody verdict: `IMPLEMENTED_UNQUALIFIED` — mechanism only.
  `QUALIFIED` requires an independent custodian, adjudicated gold, and a
  human-confirmed boundary, none of which exist.

## Prerequisites before 03B (all incomplete)

Independent annotation panel; 12-case sealed holdout under real
custody; Notebook-02 contract migration; reviewed governance adapter;
frozen model/settings/pricing; owner approval of exact payloads/caps;
cancellation/restart and output-adjudication qualification. No external
inference. EVAL-01 must not be read as permission to run it.

## Reproduction

```powershell
uv sync --locked
uv run python -m scripts.alive_eval01 verify
uv run pytest -q tests/test_alive_eval01.py
uv run pytest -q tests/test_notebook03a.py tests/test_notebook03a_r1.py tests/test_notebook03a_r2.py
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
```

The synthetic demo receipt (`docs/validation/alive-eval-01/demo-receipt.json`,
explicitly labeled) exercises the full CLI path on generated fixtures;
it is a mechanism demonstration, never a blinded result.
Stop after the draft PR; human merge authority only. Do not begin 03B.
