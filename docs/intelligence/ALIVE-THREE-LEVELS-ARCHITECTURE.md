# ALIVE: three levels of intelligence

PI-03C deterministic validation is being implemented independently from main `4e990bf` on
`codex/pi-03c-validation`; see `../capabilities/PI-03C-ARCHITECTURE.md`. PR #83 remains the
separate model-security dependency. No L2 production interpreter/composition integration is
authorized by a green focused validation test, and no Level 2 implementation is included here.
The older baseline matrix below is historical programme design, not current qualification.

Audited baseline: integrated main `1b97c4dc121c5f6f0962f48590ce78f2bad89d9d` (PI-03B and BESPOKE-01 merged).
This programme starts with L1-01. Later milestones are dependencies and design contracts, not
claims of implemented intelligence or independently measured improvement.

## Infrastructure and gaps

| Responsibility | Existing implementation | Gap | Integration |
| --- | --- | --- | --- |
| Capture | `sources/capture.py`, bounded repository/document/browser/collection captures | PDF/OCR absent; browser identity is untrusted | Reuse PI-03B exact captures; no crawling |
| Source custody | `SourceCapture`, `SourceApproval`, `custody.resolve` | Approval does not bind a goal/inquiry or authorize a workflow | Bind exact approval, content/scope digest and principal in admission |
| Context/intent | Explicit goal and Bespoke v1 context | V1 context requires an existing workflow grant; cannot select from source consent alone | Separate source-consent context from execution authority; preserve v1 history |
| Selection | `bespoke.selector.evaluate/select_recipe`, strict YAML recipes | No admitted model interpreter/ranker; `source.read` missing from constraints | Extend eligibility for PI-03B and use it in the admission review; L2 adds separately authorized reasoning |
| Capability discovery | PI-03A registry, immutable bindings, trusted implementations | No arbitrary plugin/tool installation | Reuse exact stage identities and effective deployment policies |
| Owner admission | Local source CLI and laboratory fixture grant | No live source-to-workflow bridge | L1-01 immutable review, local OS-owner digest confirmation, restricted start of that approved request |
| Execution | WorkflowRunner, leases, stage claims, cancellation, Pi dispatch fence | Live inquiry admission missing | Extend existing Governor reservation path; no new executor |
| Reasoning | ModelGateway/Pi, `cognition.role`, observer/proposer/critic, `RoleOutput` | New role schemas need versioned readers, admission and accounting | L1-02 analyst; L2 interpreter/designer; L3 improvement proposer through the same gateway |
| Validation | Input/output contracts, reference identities, controlled comparison | PI-03C locator/semantic validation not qualified | Keep structural, reference, locator, semantic and independent outcome statuses separate |
| Outcomes | Workflow/Pi/invocation/artifact records and Experience | Completion is not task success | L3-01 explicit independent evaluation receipts linked to actual execution |
| Improvement | Intelligence reasoning/feedback, candidate estimates, frozen active policy | Durable adapter is Aster-fixture-only, actions cannot execute | Extend with a separately qualified live adapter; never relax fixture guards |
| Promotion | Frozen active policy and evaluation-custodian patterns | No qualified production promotion/rollback route | Explicit trusted decision, new immutable recipe version, retained experiment receipt |
| UI | Bespoke, capability catalogue, generic graph, Workflow Observatory | No live exact owner-review journey | One dashboard; admission links selection to real runs; later outcome/proposal views extend it |

## Shared identity and authority contracts

The integration identity joins instance, source capture/approval/content/scope hashes, explicit
goal, prospective then admitted inquiry, recipe/version/hash, workflow definition/binding,
capability identities and deployment policies, role/model contracts, budgets, owner decision,
actual execution and independent outcome references. Each state has its own identity and receipt.

Capture is not consent. Consent is not a recommendation. A recommendation is not authorization.
Authorization is not execution. Completion is not verified success. Promotion is not a grant.

L1-01 records a bounded `owner-admission/v1` review before it creates any inquiry or execution
grant. It uses PI-03B source consent and the existing Bespoke eligibility function. It does not
reinterpret `bespoke-context/v1`, whose historical approval reference means a workflow grant.
The review pins exact resource and identity terms; a local operator restates the complete review
digest. Only that approved request can cross the existing runner boundary. A bearer token alone
cannot approve a request or upload an executable definition.

The first production profile is bounded repository inspection, `repository.inspect@1.1.0`,
without inference, outbound calls, shell, filesystem paths at execution time, or semantic claims.
This qualifies the admission seam; it is not the completed L1-02 implementation review.
Source preparation/consent remains the existing local owner CLI. The same OS-owner identity must
confirm admission. No laboratory, synthetic owner fixture or automatic cognitive auction is
required. General autonomy stays paused/stopped for this bounded explicit-run profile.

## Cognitive layer: LLMs are first-class components

LLMs supply interpretation, strategies, hypotheses, task analysis, candidate designs, criticism
and improvements. Deterministic code controls evidence custody, permissions, identity, accounting,
lifecycle, execution, evaluation integrity and promotion. Do not replace intelligence with
hardcoded domain decisions, or replace authority with persuasive model text.

| Role | Versioned output | Proposed milestone |
| --- | --- | --- |
| Intent interpreter | Explicit objective, inferred hypothesis, ambiguity, catalogue candidate IDs | L2-01 |
| Research strategist | Evidence requirements and bounded investigation alternatives | L2-01/02 |
| Procedure designer | Proposed existing `WorkflowSpec`, exact capability pins and rationale | L2-02 |
| Analyst | Evidence-linked findings, citations and uncertainty | L1-02 |
| Critic | Unsupported assumptions, missing evidence, counterexamples | L1-02/L2 |
| Evaluator assistant | Interpretation of independently obtained measurements, never invented labels | L3-01 |
| Improvement proposer | Baseline identity, cited failures, testable change and frozen experiment hypothesis | L3-02 |

Use only the required roles, not seven calls per task. Model/role selection considers evidence,
complexity, input size, consent, sensitivity, ceilings, latency and independently measured
performance. Unknown pricing stays unknown; token/call limits are not invented currency caps.
One approved model may serve several roles; different models may be approved where justified.

Current `cognition.role`, `role_contract`, adapters and Intelligence receipt reconstruction assume
the shared `RoleOutput`. New roles require an explicitly reviewed prompt/schema/validator catalogue
and retained historical readers, not new names injected into a global prompt map. Every invocation
must use the existing reservation and Pi/ModelGateway path. No new client or credential access site.
Scripted providers are qualification defaults; paid inference requires separate explicit consent.

## Evaluation and adaptation integrity

L2 compares fixed, deterministic and admitted hybrid selectors on identical sources, capability
sets, tasks and budgets. Model outputs are catalogue-bounded proposals; deterministic eligibility
runs again after interpretation. Preserve the explicit objective, rejected suggestions, role/model
identity, invocation receipts, uncertainty, resource use and concise rationale. Private reasoning
traces and model confidence are not evaluation evidence.

Generated DAGs use the existing WorkflowSpec parser, registry binding and trusted registrar.
Passing validation creates a valid proposal, not an executable grant. Diversity must measure
actual operations, source use, roles, validation, ceilings and output contracts; normalize away
presentation changes before claiming distinct procedures.

L3 shared envelopes, introduced in later independently qualified PRs, are:

1. Execution identity: exact source/recipe/workflow/capability/model and actual receipt references.
2. Outcome evaluation: frozen protocol/task/scorer/gold identities, independent custody, split,
   separate validation/outcome statuses, usage, uncertainty and failures.
3. Improvement proposal: cited observed weaknesses, exact baseline/candidate identities, hypothesis,
   permitted declarative changes and an authorized model-role receipt.
4. Experiment: matched task distribution/sources/budgets, negative controls, held-out tasks,
   repeated trials where stochastic variance matters, uncertainty and frozen decision rules.
5. Promotion: explicit trusted approval, immutable new version, complete evidence and rollback history.

The proposer cannot supply gold, modify its tests or change acceptance rules after observing
results. Reused/renamed measurements, model self-labelled success, two agreeing models, leaked
held-out tasks, fabricated citations, missing comparators and quarantined feedback are negative
controls. Accept rejection and inconclusive results. Never treat an LLM critic as independent truth.

Reuse `intelligence.receipts`, authorized-invocation protocols, feedback consumption ledgers,
quarantine and evaluation-custodian patterns. Current durable Intelligence requires controlled
fixture provenance and NULL authorized/executed actions; active policy is frozen. Preserve these
guards. Real L1 runs must not be laundered through the fixture-only learning adapter. New live
evaluation is L3-01, and promotion is L3-03. No recurring self-improvement loop is introduced now.

## Milestones and dependencies

| PR | Deliverable | Gate |
| --- | --- | --- |
| L1-01, now | Exact source/recipe/workflow owner review and admission, real bounded inspection | Draft PR, adversarial tests/mutations, PostgreSQL/Docker/browser/Windows/Linux qualification, independent review |
| L1-02 | Source acquisition → admitted Pi analyst → qualified evidence validation → result/Observatory | Depends on L1-01 and PI-03C; no citation-equals-truth claim |
| L2-01 | Versioned admitted interpreter/ranker over catalogue, comparison with deterministic baseline | Depends on independent model-call admission/accounting and evaluation |
| L2-02 | Proposed DAGs using installed capabilities and existing definition validation | Depends on stable L1 admission and L2 contracts; no raw plan execution |
| L3-01 | Independent live outcome custody and comparison harness | Depends on actual L1 receipts and independently established labels |
| L3-02 | Evidence-grounded model improvement proposals | Depends on qualified outcomes and frozen experiment contracts |
| L3-03 | Controlled experiments, explicit versioned promotion and rollback | Depends on independent evaluation, negative controls and trusted promotion decision |

Each milestone ends at a draft PR and independent-review gate. No automatic merge. Parallel
read-only L2/L3 research informed this plan; dependent implementations do not start speculatively.

## Continuous demonstration plan

Freeze a real repository-change fixture with source hashes, stable tasks and expected evidence.
Cold-start the existing runtime; capture/approve using PI-03B; review and authorize the exact
procedure through L1; inspect real stage/run receipts in the Observatory. L1-01 first demonstrates
bounded inspection and authorization refusal/revocation without a synthetic owner.

L1-02 adds a governed analyst and qualified citation/locator checks. L2 interprets an outcome
request and compares at least three genuinely different procedures for that problem class.
L3 evaluates actual outcomes, proposes a validation adjustment, freezes a comparable experiment
and presents supported/rejected/inconclusive promotion evidence. All views remain in the same
dashboard. Never guarantee an improvement for the presentation. Keep scripted qualification,
replayable receipts and optional explicitly authorized live inference separate.
