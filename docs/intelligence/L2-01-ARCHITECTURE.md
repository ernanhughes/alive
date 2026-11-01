# L2-01 — Intent interpretation: architecture

Status: implementation for independent review. Built on `main` at `2f27f3a` (L1-01, L1-02, the Level 1
destination hardening and PI-03C are all merged there). Offline and scripted only: no live model
has been used, so this document reports integration readiness, not interpretation quality.

## What it does

An owner states a goal in ordinary language. ALIVE asks one governed model call to interpret it
against the recipes that actually exist, then deterministic code decides what is executable.

```
goal + approved source (names, sizes) + catalogue projection
        │ review (profile intent-interpretation): shows exactly what leaves the machine
        ▼
 owner approves locally ──► one model call ──► validate (goal unchanged?) ──► retain
        │                                                             (interpretation only)
        ▼
 compose (no model): resolve the model's proposals against the catalogue it saw,
 re-ask the existing selector for eligibility, record the result immutably
        ▼
 recommendation + alternatives + unavailable (with reasons) + uncertainty
        ▼
 a SEPARATE owner admission to act (inspection or analysis profile): nothing here executes
```

## The four responsibilities, in code

| Responsibility | Where | Trust |
| --- | --- | --- |
| A. Context | `alive/intent/context.py`: goal text, file **names and sizes** of the approved source, a bounded projection of the active recipes. No file content, ever. | built by trusted code; names and labels are marked untrusted |
| B. Interpretation | `intent.interpret@1.0.0` (a `pi_agent` capability) through the existing Cognition → ModelGateway → Pi → egress path | model output is a proposal |
| C. Suitability | `alive/intent/recommend.py`: maps proposals onto catalogue identities; unknown ids and wrong versions are reported, never rewritten | deterministic |
| D. Eligibility | the **unchanged** `bespoke.selector.evaluate`, run per recipe with the model's `intent_kind` and the approved source | authoritative |

## How the model is kept inside the existing authority model

* The interpreter is a typed role (`IntentSpec`), admitted exactly like the L1-02 analyst: a closed
  profile `intent-interpretation`, an immutable review, local CLI approval of the exact digest, the
  same reservation, dispatch fence and pinned destination. It is **not** the L1-02 analysis grant.
* Disclosing the goal and file names is its own source-approval operation, `intent.interpret`. An
  approval for `repository.inspect` or `repository.analyze` does not cover it.
* The catalogue digest is a workflow input in the owner's Grant, so the catalogue the owner
  approved is the catalogue the model sees; a change makes the review stale.
* The workflow is `interpret → validate → record`. It executes nothing and starts nothing.

## Goal preservation

The model must copy the goal into `explicit_goal`. The validator compares it with the owner's exact
words. If it differs, the interpretation is **rejected** (`rejected_interpretation`), no proposal is
used and no recommendation is made. The original wording is stored verbatim; the model's
interpretation is stored under `origin: model_inference` and the resolution under `origin:
trusted_system`.

## Recommendation rules

1. Only proposals that resolve to a real `(recipe_id, version)` in the projection the model saw are
   considered. The interpreter's own recipe is never offered.
2. Each is checked by the existing selector for the model's `intent_kind` (an `unclear` kind makes
   everything ineligible, as before).
3. Among eligible proposals the model's judged fit (`fully`, `partly`, `tangential`) orders them,
   and the deterministic suitability breaks ties. Relevance never overrides eligibility.
4. Ineligible but relevant procedures are listed with their reasons. Eligible procedures the model
   did not propose are listed separately.
5. Clarification is reported when the model asks and nothing executable remains; it does not
   suppress a safe recommendation.
6. `authorization.execution` is always `not_authorized`. Acting needs a separate review.

## History and replay

`intent_recommendations` (migration `0015`) stores one immutable record per interpretation:
original goal, catalogue digest, interpreter role contract, model, endpoint, review and run ids,
usage, the model's interpretation, every proposal's resolution, the recommendation and the
uncertainty. Composing again returns the stored row. Reading never calls a model. A changed
catalogue makes composing fail (`catalogue_changed`) rather than resolve against different recipes.

## Boundaries

No L2-02 composition, no new executable procedure, no learning, no second selector or runner, no
new provider client. Only repository sources are supported as context; browser and document
contexts are out of scope here. Eligibility asks "could the owner be offered this?", using the
most the owner could later grant; it does not grant it.
