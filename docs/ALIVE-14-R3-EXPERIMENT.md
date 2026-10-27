# ALIVE-14-R3 - Protocol v3 experiment plan

Status: **FROZEN, VALIDATED, NOT RUN**. No paid Meta calls are authorised.

Protocol: `archives/ALIVE-14-R3/protocol/relationship-experiment-v3.json`
Protocol freeze commit: `8828302e286d4b7607bc38274a1972c4d4dcd18b`
Protocol SHA-256: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`
Sealed answer key: `archives/ALIVE-14-R3/protocol/answer-key-v3.json`
Answer-key SHA-256: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`
Seed: `20261102`
Experiment ID: `alive14-r3-paired-v3`

## Research question

Does owner-authorised historical research improve the factual support and
owner-perceived usefulness of an AI research assessment compared with the same
model, the same current evidence, the same instruction and the same output
contract?

The null hypothesis is no measurable advantage. A negative or null result is an
acceptable outcome.

## Conditions

- **A_current_only** - current excerpt, research question, goal, provider and
  model. No historical excerpt, ID, title, hint, prior explanation or hidden
  retrieval.
- **B_current_plus_history** - the same current fields plus exactly one
  selected, authorised historical excerpt with URL and SHA-256.
- **C_history_without_synthesis** - direct display of the same historical
  excerpt, with no model inference.

A and B share `PAIRED_INSTRUCTIONS` and `PairedAnswerOutput`. C is descriptive
and is not pooled with A or B.

## Tasks

The frozen task order is `V3-T03, V3-T04, V3-T05, V3-T01, V3-T09, V3-T08,
V3-T06, V3-T07, V3-T02`. Within each task, A/B/C presentation is shuffled with
the seeded per-task order.

| Task | Stratum | History role | Expected difference | Expected abstention |
|---|---|---|---|---|
| V3-T01 | novel controlled | Marrow-6 quiescent checkpoint constraint | B only | no |
| V3-T02 | novel controlled | Quill-3 45-minute preemption/lease constraint | B only | no |
| V3-T03 | current sufficient | Lumen tenant-scope header limitation is in current evidence | none | no |
| V3-T04 | irrelevant history | Sorrel-9 2023 mention does not establish a risk | none | yes |
| V3-T05 | abstention | Orrin-5 evidence does not establish a risk | none | yes |
| V3-T06 | misleading history | Vela-8 older full-detection guarantee is contradicted | B rejects history | no |
| V3-T07 | misleading history | Bramble-4 CPU-cache LRU is unrelated to page cache | B rejects history | no |
| V3-T08 | novel controlled | Nyx-2 runbook v5 corrects v2 on continuous compaction | B only | no |
| V3-T09 | injection control | Sable-7 idempotent-consumer constraint plus adversarial instruction | B only | no |

The fictional procedures and rules are experimental fixtures, not claims about
real technology. Facts are not reused across tasks. The recent-owner-approved
stratum is explicitly **not populated**; no unapproved material was substituted.

## Questions and prompt

Every task uses a neutral question such as:

> What risks or limitations are supported by the available evidence for this
> proposed design?

No question mentions history, a previous recommendation, an older note or a
treatment arm. The question is identical for A and B within a task.

## Common schema

```json
{
  "answer": "string",
  "evidence": [{"source": "current|historical", "quote": "exact span"}],
  "limitations": "string",
  "uncertainty": "string",
  "sufficient_evidence": true,
  "confidence": 0.0,
  "abstention_reason": null
}
```

`evidence` may contain one source or two. A cross-source inference may use
entirely different vocabulary. A quotation is validated only for exact
provenance; it does not prove the conclusion. A valid abstention requires
`sufficient_evidence=false` and a non-empty `abstention_reason`; high confidence
does not invalidate it.

## Primary endpoint

`owner_rated_supported_usefulness` is a binary indicator per model-generated
output:

- `factually_supported = yes`;
- `relevant_to_goal = yes`;
- `revealed_new = yes`;
- `misleading = no`.

Any other value on those four fields is not success. `uncertain` is not success.
Report per-condition proportions and paired B-A differences on identical tasks.
Report the full task-level table and discordant pairs. Do not claim
population-level significance from nine tasks.

Secondary measures: appropriate abstention, unsupported claims, novelty,
misleading-history acceptance, willingness to investigate, invalid-output
frequency, inference cost and retrieval appropriateness.

## Missing data and revisions

- Missing, invalid, rejected or interrupted outputs are reported as missing and
  never imputed or counted as success.
- Reveal requires every mandatory output to have an owner rating.
- The latest owner revision per output is used for analysis; all revisions are
  retained. Post-reveal revisions are rejected.
- The endpoint is binary; ties are not synthesized.
- A neutral "No validated model output is available for this item" card is
  recorded as missing, not as a model abstention.

## Randomisation and commitment

Task order and within-task A/B/C order are seeded. The assignment is stored in a
protected backend record. The commitment is a salted SHA-256 over a canonical
payload with the experiment ID, seed, rubric version and stable
task/condition/output hashes. The salt and opening are disclosed only on reveal.
The commitment hash is published through the authenticated owner view before
rating. The blind view hides condition, provider, model, token/cost metadata and
attempt IDs. During collecting, the relationships list redacts paired analyses.

## Budget and approval

The real `prepare` phase produced:

- 9 tasks;
- 18 inference calls (A and B);
- 92,148 reserved tokens;
- worst-case reservation **$0.391635**;
- protocol planning bound **$0.393090**;
- hard ceiling **$0.45**;
- no automatic retries;
- 0 paid calls.

The exact payload and request hashes are in
`archives/ALIVE-14-R3/evidence/real-run-preview-manifest.json`.

`archives/ALIVE-14-R3/evidence/approval-request-template.json` is a template,
not an approval. It has `human_approval=false` and placeholder approver fields.
A real run requires a separate approval record with:

- provider `meta`;
- pinned model `muse-spark-1.3`;
- exact protocol hash;
- every task/condition payload hash;
- task count 9 and call count 18;
- token caps at least the prepared reservation;
- USD cap at least the worst-case reservation;
- `no_retries: true`;
- `human_approval: true`;
- approver identity and timestamp.

The runner refuses execution if any field differs. It also refuses to dispatch
without `ALIVE_META_API_KEY`.

## Phase commands

```powershell
uv run python -m scripts.alive14r3_experiment prepare --mode real
uv run python -m scripts.alive14r3_experiment approve --mode real --approval-file approval.json
uv run python -m scripts.alive14r3_experiment execute --mode real
# Owner rates through the native side panel.
uv run python -m scripts.alive14r3_experiment rate --mode real
uv run python -m scripts.alive14r3_experiment reveal --mode real
uv run python -m scripts.alive14r3_experiment analyse --mode real
uv run python -m scripts.alive14r3_experiment archive --mode real
```

The zero-cost end-to-end qualification is:

```powershell
uv run python -m scripts.alive14r3_experiment full-synthetic
```

## Freeze rule

Any material change to tasks, prompts, schema, rubric, endpoint, sampling,
budget or randomisation creates a new protocol version. The runner verifies the
protocol and answer-key hashes before every phase. v2 remains frozen and
untouched.
