# ALIVE-EXT-01 — Research Extension Packs (design proposal)

Status: **DESIGN ONLY / NOT QUALIFIED**. This document proposes a modular extension system; it does not claim implementation of its runtime. Base: current `main` at branch creation. Related: [ALIVE-12](ALIVE-12.md), [architecture](ARCHITECTURE.md).

## Decision

Keep evidence, memory, permission, policy, model access and audit in ALIVE Core. Add an opt-in **Extension Host** which discovers versioned, inert manifests. Compose reusable **skills** into domain-specific **scenario packs**, each with synthetic demos and benchmark fixtures. The core must never load arbitrary Python/JavaScript code from a pack during discovery.

The word *skill* means a constrained research operation, not automatic activation of Pi's native tool or prompt system. ALIVE currently disables Pi skills/tools in supervised agent runs; do not weaken that boundary.

## Scope and non-goals

In scope: specification, catalogue, input/output contracts, deterministic runners, demonstrator layout, capability declarations, policy checks, replayable evaluations, packaging/versioning.

Out of scope in EXT-01: installing third-party executable plugins, arbitrary filesystem access, site-wide Chrome history, unattended model calls, automatic external sends, new memory stores, proof of research benefit, production deployment, UI rewrite.

## Layers

1. **Core (existing)**: source snapshots; goal-scoped research memory; lifecycle/withdrawal; retrieval; evidence quote validation; Governor and budget; owner grants; persistence and events.
2. **Extension Host (new, proposed)**: local catalogue of explicitly enabled manifests, schema validation, compatibility negotiation, workflow interpreter, privilege narrowing, result validation, audit, replay.
3. **Research Skills (new)**: reusable operations such as `retrieve-relevant`, `validate-quotation`, `compare-constraints`, `check-supersession`, `assess-applicability`, `abstain-if-insufficient`, `suggest-follow-up`. Start with deterministic operations wrapping *existing* services.
4. **Scenario Packs (new)**: declarative recipes of skill invocations and policy thresholds; copy for user-facing guidance, examples and expected result semantics.
5. **Demonstrations (new)**: invented, labeled sample pages and owned synthetic memory, positive and negative cases, frozen expected decisions, and test harness. Never write demo memories to a user's normal research store by default.

### Data flow

```text
approved current-page snapshot + authorized goal
  -> Host validates pack and request / narrows capabilities
  -> permitted Core retrieval of active goal-scoped memories
  -> deterministic evidence and applicability checks
  -> optional bounded Meta analysis ONLY after exact payload preview + explicit approval
  -> Core validates source quotations and links
  -> structured candidate / qualification / abstention
  -> existing browser panel or dashboard renders provenance, reasons and feedback
```

No extension receives raw browser access, API tokens or database connections. It consumes bounded read-only DTOs, invokes an allowlisted Core operation, and returns a schema-checked result. Source text is untrusted data. No pack may grant itself access beyond a live owner grant. Revocation and withdrawal invalidate queued work and cached projections.

## Package layout

```text
extensions/
  README.md
  schemas/                    # future machine-validated manifest / result schemas
  skills/
    evidence-qualification/
      skill.yaml              # identity, version, declared inputs, bounded operations
      SKILL.md                # human/Pi-style procedural guidance; never executable authority
  packs/
    design-review/
      pack.yaml               # compose skills and evaluation rules
      demos/
        kestrel-memory-helps.yaml
        kestrel-memory-inapplicable.yaml
  catalogue/                  # later index (no implicit execution)
```

Future third-party packs can live outside the repository and be explicitly installed from audited, pinned artifacts. Their activation requires a version/publisher digest, owner opt-in and capability review. No dynamic remote import or auto-update.

## Manifest contract (v0 design)

A pack declares `schema_version`, `id`, `version`, `display_name`, `description`, `core_compatibility`, `entrypoint` (declarative only), `capabilities`, `skills`, `workflow`, `output_contract`, `demos`. Skill entries declare `kind` (deterministic or bounded_model), strict input/output types, prerequisites and no implicit side effects.

Allowed initial capabilities: `current_authorized_snapshot.read`, `goal_research_memory.retrieve`, `source_quote.validate`, `candidate.render`, `feedback.submit`. An optional `model.analyze_approved_payload` capability requires a separate explicit approval for every actual model submission and passes through the existing Governor and spend ledger. Permission listing alone does not confer permission.

Workflow execution is a DAG: each step references registered skill identifiers, typed inputs and prior outputs. Reject cycles, unknown operations, excessive fan-out, missing provenance, invalid manifests and undeclared capabilities *before* execution. Enforce step/time/input/token/result-size caps. Deterministic fallback must be available when a model is unavailable. Schema version changes are explicit migrations, not silent reinterpretation.

### Output

Use three first-class outcomes: `connection_candidate`, `qualified_non_use`, `abstain`. Every outcome includes pack/version, workflow/run ID, goal ID, current source ref/hash, historical source refs/hashes where allowed, decision reason codes, quote-verification state and model provenance if any. `connection_candidate` is a *hypothesis*, never proof of corroboration. An abstention is a normal successful policy result, not an exception.

A `qualified_non_use` identifies stale, superseded, inapplicable, retracted, unauthorized or otherwise unsafe memory without leaking a forbidden source. Do not expose existence, names, excerpts or timing of unauthorized memories. A no-permission case is a generic `not_authorized` outcome.

Keep independent axes for relevance, evidence integrity, applicability, currency, source reliability and authorization. Do not sum these into a single trust score. Owner ratings teach local usefulness, not historical truth.

## First four packs

| Pack | Domain question | Positive case | Do-not-use case |
| --- | --- | --- | --- |
| `design-review` | Does a proposed architecture violate a remembered constraint? | Kestrel continuous compaction omitted rate limit | constraint explicitly superseded after validation |
| `literature-review` | Does a new paper relate to earlier research? | method/result connected with verified excerpts | remembered paper retracted or method incomparable |
| `book-consistency` | Does a new chapter conflict with existing definitions or obligations? | earlier definition copied accurately | explicitly documented intentional revision |
| `agent-failure-review` | Is an agent repeating a previously observed failure? | same tool, preconditions and failure signature | transient failure or changed environment |

Only `design-review` receives starter manifest/demo specimens in this proposal. The others require independent task contracts and labels before implementation.

## Twenty-role catalogue

Family A (engineering): design review, software development, incident response, code review, AI agent supervision.
Family B (science): literature review, experimental research, mathematics proof review, research synthesis.
Family C (trust): security review, compliance, fact checking, procurement.
Family D (learning): studying, book writing, journalism, independent research.
Family E (AI): autonomous-agent review, multi-agent research, self-improvement experiments.

These are applications of common skills, **not twenty privileged runtimes**.

## Proposed evaluation programme

Build 20 roles × 6 conditions = 120 *synthetic* labelled cases: useful connection; superseded memory; false-context similarity; insufficient evidence; conflicting sources; unauthorized evidence. Every test stores source snippets, provenance, goal, grants, expected decision, reasons, quote spans and forbidden behavior. Evaluate four frozen arms with identical candidate sources: current-only, retrieval-only, qualification, qualification+abstention. Where applicable add a strong unrestricted-history control (ALIVE-12 demonstrated parity with such a control). Freeze datasets, versions, prompts, budgets, decisions and labels before scoring; hold out scenarios and include distractor-rich corpora.

Report per-role false alerts, unsupported connections, appropriate abstentions, quote validity, permission leakage, decision usefulness (independently labelled), latency, inference cost and recovery/revocation behavior. A demo passing its own fixtures is *not* validation that ALIVE improves real research. Do not claim ranking or usefulness advantages without powered independent evaluation.

## Demo UX

Homepage: family -> role -> paired `Memory helps` / `Memory should not drive` authored examples; clearly mark invented scenarios. For an authorized real page, show source anchors, policy reason, uncertainty and owner feedback. The demo may not simulate a successful Meta call as if paid inference occurred. Pack selection does not change browser grants. Display pack version and why a memory was set aside.

## Incremental implementation plan

- **EXT-01 P0 (this branch)**: design, starter declarative manifests, paired synthetic fixtures; no runtime change.
- **P1**: formal JSON Schemas, offline validator, deterministic registry, negative malformed/privilege tests, CLI demo harness.
- **P2**: Core adapter for existing ALIVE-12 memory, quote checker, scoped read-only host, structured outcomes; no model needed.
- **P3**: browser-panel pack chooser and paired demo presentation; ensure demos isolated from production memory.
- **P4**: explicit approved-payload Meta path through Governor, budget, traces and refusal semantics.
- **P5**: frozen four-arm benchmark, independent labels and 20-role catalogue expansion.

## Acceptance gates

1. Existing ALIVE tests, security invariants and Chrome permission boundary remain unchanged.
2. Discovering/previewing a pack makes zero model calls, zero network calls and no writes to user memory.
3. Unknown, incompatible, cyclic, unsigned/untrusted (under enforced trust policy) or over-privileged packs are rejected.
4. Unauthorized source data cannot appear in result text, prompts, logs or diagnostics.
5. Withdrawn memories cannot be retrieved, reused or restored after restart.
6. Source quotes are verified against authorized source snapshots; otherwise abstain.
7. Any external model submission needs current owner approval of the exact payload plus Governor/budget enforcement.
8. Deterministic replay produces stable results, including withheld evidence and abstention.
9. Demo output is conspicuously synthetic, separated from real research runs.
10. No claimed research improvements without independent, reproducible comparison.

## Open decisions

Choose whether an external pack distribution format is needed before P3; prefer in-repo manifests initially. Determine the host implementation location only after inspecting current service boundaries and tests. Retain ALIVE's current Pi sandbox policy rather than relying on native Pi skill loading. Keep a future dynamic skill generator out of P1 until source, permissions and evaluation contracts are stable.
