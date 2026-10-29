# ALIVE-NOTEBOOK-03A-R1 — engineering and experimental-readiness report

Decision:
**Engineering: READY_FOR_REVIEW. Research protocol: READY_FOR_INDEPENDENT_ANNOTATION. NOT READY FOR 03B.**

Independent held-out labeling, protocol freeze confirmation by reviewers, and
the five Notebook-02 contract issues plus governance qualification remain
prerequisites. No semantic performance advantage is claimed. No model inference
was run.

## Delivery and provenance

- Base: `785e1024a22fca0402741b7a2ebad984af7fc10b` (`origin/main`, PR #45 merged;
  reviewed head `8546536` within).
- Branch: `codex/alive-notebook-03a-r1-protocol-hardening`.
- v1.4 (`evaluations/notebook03a/`, `scripts/notebook03a*.py`,
  `tests/test_notebook03a.py`, v1.4 docs/validation) preserved byte-unchanged;
  `git diff HEAD -- evaluations/notebook03a scripts/notebook03a*.py` is empty
  and v1.4 freeze + 30 tests still pass.
- R1 implementation: `scripts/notebook03a_r1{,_protocol,_surface}.py`,
  `tests/test_notebook03a_r1.py` (18 tests), corpus
  `evaluations/notebook03a_r1/` (protocol v1.5, 66 cases), annotation package +
  adjudication dossier, docs `ALIVE-NOTEBOOK-03A-R1-{DESIGN,PROTOCOL}.md` (this
  report is `...-REPORT.md`), validation under
  `docs/validation/alive-notebook-03a-r1/`.
- Local environment: Windows 11, Python 3.13.3, locked uv dependencies.
  `uv run pytest -q tests/test_notebook03a.py tests/test_notebook03a_r1.py`:
  **48 passed**. `uv run ruff check` + `format --check` (alive/migrations/
  scripts/tests): **pass, 180 files formatted**.
- 03A-R1 execution: **0 model calls, 0 tokens, USD 0.00**. Core replay forbids
  Meta structured calls and embeddings; validation/scoring are local
  Python/Git operations. No production Core, Governor, approval, payment,
  migration, browser-permission, source-document, or archive code changed
  (working tree adds R1 files only).

## What is available

66 public draft cases: 16 development (unchanged v1.4) + 50 public evaluation
(24 v1.4 + 26 R1). 52 pair + 14 claim-support. 45 useful, 10 insufficient, 11
sufficient-non-useful. Origins: 12 authentic-only, 5 controlled-involved, 49
synthetic-only. 39 template families; shared families 83b02e (corroboration
×5), 0b1efb (contradiction ×5), S3+S4 (×2) declared non-independent;
paraphrases are not independent observations.

| Eval relation (n=50) | v1.4 eval | R1 eval |
|---|---:|---:|
| supersession | 0 | 4 (2 authentic + paraphrase + reversed) |
| unsupported_claim | 0 | 4 (2 controlled-long + long + disputed) |
| substantive_connection | 0 | 6 (2 authentic + duplicate + long + 1) |
| scoped_change | 4 | 6 | corroboration_candidate | 4 | 5 |
| contradiction_candidate | 4 | 5 | independent_observations | 4 | 8 |
| unknown | 8 | 12 |

Eval questions: generic 34, conditions 10, replacement 3, headline 3 — R1- and
R4-style represented beyond dev-only. Eval origins: synthetic-only 41,
authentic-only 5, controlled-only 2, controlled-pair 1, authentic+controlled 1.
Authentic gaps reported, not filled: no authentic corroboration/contradiction/
scoped/unsupported artifacts exist in ALIVE history; covered by
controlled/synthetic with explicit labels.

All 66 labels are implementer-authored drafts (`IMPLEMENTER_EXPOSED; NOT
BLIND`). Target 78 (66 + 12 holdout); independent cases available: **0**;
status **PENDING_INDEPENDENT_LABELING**. The custodian package, reviewer
attestations, and actual access-boundary verification are all still missing.
The annotation package (`annotation_package/` with instructions, category
definitions, 66 passage+question items, reviewer/disagreement/adjudication
template, no gold/answers) is ready for independent use; Codex is never the
independent annotator.

## Contracts, gates, and adjudication

Relationship/sufficiency/applicability/decision remain separate; unknowns valid.
Specific categories outrank residual `substantive_connection`. Exact citations,
required-qualification coverage, and directed refs validated separately from
semantic truth. Authentic quotes checked against Git objects; controlled text
retains verbatim quotes with perturbation notes; synthetic never masquerades
as history. Missing Git revisions raise controlled `ValueError`s.

Adjudication dossier (`adjudication_dossier.md`, provisional): duplicates
(93b00a, C3, CR2 → residual, not corroboration); shared limitations (7e0b9f,
C1, C2 → residual continuity); missing-baseline (ff90be → unknown; U4
universal → unsupported, disputed); later-without-replacement (date-only →
unknown; SC3 reaffirm → substantive, provisional); applicability (7b8653a
`applicable` → `not_applicable` standardization, 1 versioned correction;
v1.4 gold untouched). All provisional pending independent adjudication.

Payload `prepare_payload_r1` withholds version/temporal/system context (the
v1.4 cue correlating ALIVE-* vs null) plus all gold/IDs/families/splits/notes.
Goal text is the question verbatim; 4 templates balanced across categories so
it is not a category cue (fixed-candidate comparison, not retrieval ranking).
External submission validates structure/hash/completeness, not OS access or
identity; sibling dirs/worktrees are not automatically private.

## Replayed baselines and scoring (R1 v1.5)

Core A/B replayed via existing allowlisted fixture URLs in isolated SQLite
(actual B output recorded: outcome/semantic/inference calls; unexpected
semantics raise instead of faking abstain); S is the frozen offline
surface-cue-v1.0 control; C/D NOT RUN.

| Arm | Scored | Useful ret. | Misleading | Correct non-use | False abst. | Cat acc |
|---|---:|---:|---:|---:|---:|---:|
| A lexical | 50 | 0.000 | 0.240 (12) | 0.143 | 0.028 | 0.100 |
| B integrity | 50 | 0.000 | 0.000 | 1.000 | 1.000 | 0.100 |
| B0 abstain | 64 | 0.000 | 0.000 | 1.000 | 1.000 | 0.156 |
| S surface | 64 | 0.489 (22/45) | 0.219 (14) | 0.737 | 0.289 | 0.609 |

Citation: A precision 0.940/recall 0.814; S precision 0.973/recall 0.741
(exact-span only; broad cites penalized, e.g., C4 recall 1.0/precision ~0.12).
Wilson 95% illustrative only (non-independent families).

Surface diagnostic reproduces the review finding: synthetic retention ~0.71 vs
authentic retention **0.0**; authentic misleading 0.417 vs overall 0.219;
authentic category accuracy 0.25 vs overall 0.609. S itself fails the
pre-registered bar (retention ≥ 0.5 AND misleading ≤ 0.10, plus beating S by
margin) — so a future model beating B0 while matching S is NO_PROGRESS, not
success. C/D evaluate to INCONCLUSIVE (unrun). Thresholds frozen before any
model result, justified against these controls and n=66/45 useful (authentic
n=12 underpowered; report INCONCLUSIVE when underpowered).

## Freeze history and fingerprints

Final protocol: **notebook03a-v1.5**. v1.4 `protocol.json`
(`ffba53c7…`) untouched. R1 `protocol.json` pins LF-normalized SHA-256 for 10
files + 3 tools + 2 documents; `amendments.json` appends v1.5 to the v1.1–v1.4
history. Baseline expectations (`expected-baselines.json`, normalized
metrics+strata+per-case decisions) stored separately in validation and
compared deterministically (`--check-against` passes); never rewritten to hide
behavior. One replay determinism fix during R1 (tuple→list in normalized
comparison) was a contract bug fix, not a label/result change.

## Validation

Evidence: `docs/validation/alive-notebook-03a-r1/` (validate/submission/
prepare summaries, full `baseline.json`, `expected-baselines.json`,
`python-notebook.txt` 48 passed, lint pass, working-tree/changed-paths).

| Check | Result |
|---|---|
| R1 validate (66, PUBLIC_COMPLETE) | pass |
| R1 submission (PENDING, attested_eligibility false) | pass |
| R1 prepare (R1 whitelist, 2 refusals gated) | pass |
| R1 baseline + `--check-against` (metrics/strata/decisions) | pass |
| pytest `test_notebook03a` + `test_notebook03a_r1` | 48 passed |
| v1.4 freeze + tests (byte-unchanged) | 30 passed, fingerprints match |
| ruff check + format (repo scope) | pass, 180 formatted |
| Template similarity (Jaccard ≥ 0.55 cross-split) | 0 hits, limits documented |
| Full backend suite / hosted CI / native flows | **pending** (see below) |

Skipped/deferred: full `pytest -q` backend suite, Node suites, Hugo build, and
existing hosted CI are not yet run/recorded for this branch; R1 changes no
production code paths they cover, but the draft PR must record hosted CI
before merge. No native browser flow added or claimed.

## Prerequisites before 03B (all incomplete)

1. Independent review of this R1 protocol/taxonomy/evidence/scoring.
2. Independent adjudication of the 66 draft labels via the annotation package.
3. 12-case restricted holdout collected, boundary-verified, exposure-attested,
   gold withheld from implementer.
4. Five Notebook-02 contract issues via explicit narrow migration (new R1
   expectation checks do not claim the old gate).
5. Reviewed single-/dual-source governance adapter (resolve owned IDs
   server-side; bind exact evidence/prompts/schema/model/settings; no fixture
   access-bit trust); preserve caps, cancellation/restart, revalidation.
6. Frozen model/settings/tokenizer/pricing with verified worst-case under the
   USD 1 proposal; authorized spend remains 0.
7. Owner approval of exact payloads/calls/caps; output adjudication of prose/
   scope/forbidden conclusions; C-vs-D matched comparison with strata.
8. Existing outbound approval/payload/Governor/cancellation semantics unchanged
   and unqualified for dispatch by R1.

## Reproduction

```powershell
uv sync --locked
uv run python -m scripts.notebook03a_r1 validate
uv run python -m scripts.notebook03a_r1 submission
uv run pytest -q tests/test_notebook03a.py tests/test_notebook03a_r1.py
uv run python -m scripts.notebook03a_r1 prepare --output .alive/03a-r1-inputs-review-01.json
uv run python -m scripts.notebook03a_r1 baseline --check-against docs/validation/alive-notebook-03a-r1/expected-baselines.json --output .alive/03a-r1-replay-review-01.json
uv run python -m scripts.notebook03a_r1 score --records .alive/03a-r1-replay-review-01.json --arm S --output .alive/03a-r1-score-review-01.json
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
```

Sealed-package command is custodian-only on a separately controlled machine.
Use unused output names; never overwrite frozen inputs/evidence. Stop after the
draft PR; human merge authority only. Do not begin 03B.
