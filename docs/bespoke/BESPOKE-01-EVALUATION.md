# Evaluation protocol v1

Run the local versioned package with no paid inference:

```
uv run python -m scripts.bespoke_evaluate --output evaluation.json
uv run python -m scripts.bespoke_check --output demonstration.json
uv run python -m scripts.bespoke_mutations --output mutations.json
```

The explicit expectations in `evaluation/cases-v1.json` are maintained separately from selector/scoring code.
They were authored during implementation; they are not an independent-review verdict. It includes
development and held-out cases: clear captured evidence, ambiguous intent, incompatible context,
missing discussion ingestion, permission/wall conflicts, unrecorded/changed source references,
unknown model proposals, explicit objective preservation and captured-repository procedures.
Held-out outcomes were specified before running the harness; no ranking tuning used their results.

Each case shares source evidence and ceilings across A and B:

- A: fixed `controlled-comparison` default, subject to the **same mandatory feasibility gate**.
- B: deterministic context-aware selection among the actual catalogue.
- C: model-assisted selection is not implemented, authorized or measured.

The harness compares selected IDs with independent expected IDs/refusals, checks typed missing
requirements, tests deterministic replay with another retry key, verifies score explanations,
source provenance, resource ceilings and procedural diversity, and records elapsed selection time.
Unauthorized selection means selecting a procedure where expected ground truth requires abstention;
this metric is distinct from execution authority, which the selector never creates.

The recorded result is 14/14 correct deterministic selections/refusals versus 13/14 for the gated
fixed default, with zero unauthorized selections. The difference is the supported repository
inspection case, where the fixed procedure correctly abstains rather than changing procedure.
This tiny fixture package demonstrates suitability behavior, not a task-quality improvement.
It does not measure downstream correctness, semantic truth or generalization to real scientific
documents or discussions.

Security/lifecycle cases requiring database or registry changes live in the behavioral suite:
changed recipes and workflows, disabled/changed capabilities, missing definitions, equal-score
ties, aliases sharing one execution contract, source/grant revocation, cross-instance reuse,
source injection, policy changes, immutable history and actual runner execution. These are not
silently counted as extra held-out dataset successes.

## Controlled scenarios

The demonstration uses disposable databases, controlled sources, a captured repository snapshot,
the existing independent fixture owner, and the real runner/Observatory:

1. Repository: capture a bounded README, select its installed inspection procedure and execute it.
   It produces captured files with hashes, not a security/correctness review.
2. Scientific objective: compare already structured controlled claims when compatible; document
   extraction and semantic verification remain unavailable. Repository context abstains for this intent.
3. Discussion objective: abstain and retain missing `browser.prepare-source` requirements. No URL
   is fetched or represented as approved discussion evidence.

Every receipt records the actual installed capability catalogue. SQLite and PostgreSQL evidence
includes real completed runs. No model is used and no workflow completion is written as learning.

## Mutations

`bespoke_mutations.py` reuses the existing PI-03A isolated temporary-copy runner. It first requires
the target behavioral baseline to pass, applies only the named guard mutation, and counts a kill
only for a relevant pytest failure. Syntax, setup and collection failures do not count. The checked
campaign has 12 killed, zero survived and zero invalid mutants: goal binding, permission gate,
wall ceiling, workflow pins, both capability pin checks, future availability, score ordering,
record digest, stale recipe handoff, handoff wall budget policy identity and configured model-provider readiness.

An initial B9 campaign definition had a nonmatching formatted-code pattern; it stopped before
running the mutant and was corrected. B9–B11 were then run with merged receipts. That harness
pattern error was never counted as a kill. These mutations are implementation-authored;
independent review remains a separate gate and must extend the campaign.
