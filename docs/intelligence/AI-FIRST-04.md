# AI-FIRST-04 — Selective adaptation and verified improvement

AI-FIRST-03 proved a durable learning loop but not a quality gain: on its held-out panel the
stateless model scored 11/12 and both context-bearing arms 8/12. [The diagnosis](AI-FIRST-04-DIAGNOSIS.md)
shows most of that gap was an instrument and contract problem (a defective oracle label, a
reference-type validator error, optional output fields skipped, one truncation) rather than
demonstrated bad reasoning. AI-FIRST-04 fixes those, replaces unconditional family-level retrieval
with a selector that may choose **no lesson**, and re-measures on a fresh frozen corpus.
This change adds **no** agent framework, memory database, vector index, model gateway, trained
selector or policy hierarchy. It extends `alive.adaptation`, `alive.continuity` and the existing
live admission path.

Results, limits and gate status: [AI-FIRST-04-REVIEW.md](AI-FIRST-04-REVIEW.md).
Predeclared protocol: [AI-FIRST-04-PROTOCOL.md](AI-FIRST-04-PROTOCOL.md).

## What changed in production code

| Area | Change |
| --- | --- |
| `alive/adaptation/oracle_v2.py` (new) | `frozen-executable-fixture/v2`: observes return value *or* exception, the input before and after execution (nested), and keeps semantic correctness (tri-state), contract compliance, reference integrity, grounding and end-to-end success apart. v1 `oracle.py`, its corpus and lock are byte-identical and pinned by a test. |
| `alive/adaptation/selection.py` (new) | Mechanism-level applicability, explicit `selected` / `none` / `abstained` / `refused` decisions, utility tiers, evidence-linked empirical demotion, a persisted selection record per request, and a read-only owner projection. |
| `alive/adaptation/contracts.py` | A closed `Mechanism` vocabulary (23 tags). A lesson proposal now carries the mechanisms it addresses and the ones it must not be applied to. |
| `alive/continuity/{contracts,adapters}.py` | Contextual contract v2: typed references (`recalled_item_ids`, `historical_ids_used`, `lesson_ids_used`), an explicit review obligation, structural `contract_compliance` and `reference_integrity` recorded on every answer. |
| `alive/intent/contracts.py` | The live intent call also names `task_mechanisms` from the same vocabulary. No extra model call. |
| `alive/continuity/service.py`, `alive/admission/{live,contracts}.py` | `strategy_mode: selective` (now the default). `stateless`, `contextual` (history) and `learned` (AI-FIRST-03 family-latest) remain as labelled controls. Every arm writes an auditable selection record that is bound into the approved model-input digest. |
| `dashboard/src/admission/LivePane.tsx` | One compact panel: lesson supplied or why none, version and tier, current standing, whether the model *reported* using it, and the independent outcome. |

## The selector

Inputs: the task's mechanisms (named by the live intent call from the owner's contract text) and the
owner-approved lesson store. Decision, in order, per candidate lesson:

1. **Authorization eligibility** — active, owner-approved export, same principal and model destination.
   An otherwise applicable lesson outside owner/destination scope yields `refused`, never a silent skip.
2. **Mechanism applicability** — the lesson's declared mechanisms must overlap the task's; any of its
   `excluded_mechanisms` present on the task excludes it. A lesson with no declared scope
   (AI-FIRST-03 style) is not selectable.
3. **Empirical standing** — a lesson demoted on verified counterevidence is never selected. Standing is
   derived from `adaptation.application` events: independently measured train/dev outcomes of turns
   in which the lesson was supplied, paired with a stateless baseline on the same task when one exists.
   `useful` = at least one paired gain and more gains than losses; `contradicted`/`demoted` = losses
   exceed gains, or two failures with no pass. Held-out outcomes are refused as input.
4. **Ranking** — demonstrated utility, then specificity (overlap size), then supporting outcomes, then
   recency; at most two lessons, and a lesson that adds no new mechanism is dominated.

If nothing survives, ALIVE reasons from the evidence alone and the record says why. The decision is
deterministic and costs **no additional model call**; the model only supplies mechanism tags, and no
model confidence value participates. Whether a lesson with no demonstrated benefit may be supplied on
an exact match is a recorded policy parameter (`allow_unproven`, true for this study; such lessons
are labelled `unproven`).

Owner withdrawal (revokes permission to reuse) and empirical demotion (evidence the lesson is
unreliable) are separate durable events. Neither deletes history or outcomes.

## Response contract v2

The contextual role's instructions were rewritten, versioned and applied identically to every arm.
Typed references fix the AI-FIRST-03 `lesson_not_supplied` failure: an ID that was never supplied
is still fabricated and refuses the turn, while a real supplied record reported under the wrong type
keeps the answer, is recorded under its actual type (`reference_integrity: normalized`) and is never
credited as strategy use. When `README.md` lists named input cases the answer must carry one
prediction per case and `issue_present`; the validator reports `contract_compliance` structurally and
the oracle reports it separately from semantics. There is no repair/retry: results are first-pass.

## Security posture (unchanged and re-tested)

Lessons are untrusted data carried in the conversation snapshot and never in instructions; they grant
no tools or source access. The selected items are inside the approved model-input digest and are
re-verified at dispatch (active, latest version, same owner/destination, exact content). Withdrawal
and demotion take effect for new dispatches. Replays and history reads never redispatch. The fixture
oracle executes only author-owned fixture code in a `python -I` subprocess with a scrubbed environment
and timeout; that is a convenience boundary, **not** a security sandbox, and must never be pointed at
model output or untrusted repositories. The evaluation-only override used by the ablations is
process-local, cannot be set through any request, never bypasses authorization and labels every
record that used it.

## Running it

```powershell
# offline controls (scripted transport; cannot qualify AI quality)
uv run pytest -q -o addopts="" tests/test_oracle_v2.py tests/test_selective_adaptation.py

# fixtures: audit, then freeze (committed lock)
uv run python -m scripts.audit_selective_corpus
uv run python -m scripts.freeze_selective_corpus

# live, owner-approved, disposable database; held-out stays closed until development is complete
uv run python -m scripts.selective_experiment run C:/Temp/alive-sel --approve-live --through dev
uv run python -m scripts.selective_experiment run C:/Temp/alive-sel --approve-live --open-heldout
uv run python -m scripts.selective_experiment positive C:/Temp/alive-sel --approve-live
uv run python -m scripts.selective_experiment replay C:/Temp/alive-sel
uv run python -m scripts.selective_report C:/Temp/alive-sel/selective-ledger.json out.json
```

Do not edit files under `alive/` while a live run is in flight: the contextual implementation's
custody hash covers them and the run is (correctly) refused with `capability_authority_changed`.
