# ALIVE-EVAL-01 — amendment record (v1.7 scope)

v1.4 (`evaluations/notebook03a/`) and v1.5 (`evaluations/notebook03a_r1/`)
remain byte-unchanged. v1.6 (`evaluations/notebook03a_r2/`) files are
unchanged except the annotation package (not part of the frozen
inventory), which is revised here as package v1.7.

## v1.7 changes (no frozen-input changes)

1. **Annotation package v1.7** (new location
   `evaluations/alive-eval-01/annotation_package/`, derived from the R2
   package; R2 files untouched):
   - Removed per-source `sha256` and `access` fields from
     `tasks_for_annotation.json` (66 entries). Source text remains; hashes
     enabled trivial matching against public task records.
   - Rewrote `labeling_instructions.md` disputed-pattern guidance as open
     adjudication questions; no case references, no endorsed rulings.
   - Added `Open adjudication questions` section; template already supports
     multiple readings, ambiguity flags, and predeclared exclusions.
   - Leakage audit extended (in the custodian, R2 frozen): missing
     hash/access cues are now failures; the v1.7 package passes, the
     frozen R2 package fails the stricter audit (content hash present).
2. **Threshold validation strictness (code-level, values unchanged)**:
   - v1.6 contract values are frozen and unchanged. EVAL-01 enforces
     additional admission rules at read time: reject NaN/Infinity,
     require `0 < ci_level < 1`, require `min_citation_precision > 0`,
     require `require_full_citation_recall is True`, require
     `min_useful_retention > 0` and `max_misleading_advance_rate < 1`.
   - Rationale: zero/false values would silently disable mandatory
     integrity requirements; the v1.6 loader accepts them.
3. **New custodian policy** (`evaluations/alive-eval-01/custodian_policy.json`,
   version `alive-eval-01-policy-v1`): eligibility gates (holdout size,
   required arms, family/useful/scored minima), allowlisted protocols and
   scorers, custody record requirements. Strictly validated, no defaults.
4. **Controls registry** (`controls_registry.json`): S marked
   `template-informed`, V marked `evaluation-informed` with code hashes.
   V is not rewritten to score poorly; its failures stand as measured.
5. **Uncertainty made operative**: family bootstrap intervals and paired
   differences now gate the verdict (bounds must clear floors, margins,
   and tolerances), with imbalance warnings.

## Preserved history

- v1.4 protocol `notebook03a-v1.4`, 40 cases, original baselines: untouched.
- v1.5 protocol `notebook03a-v1.5`, 66 cases, surface-cue-v1.0, R1 baselines: untouched.
- v1.6 protocol `notebook03a-v1.6`, 66 neutral-question cases, shortcut-v2,
  R2 baselines: frozen files untouched (package revision is outside the
  frozen inventory by design).
