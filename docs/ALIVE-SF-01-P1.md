# ALIVE-SF-01-P1 — Authoritative Research-Memory Exploration Projection

**Status:** draft integration slice; tests written but not qualified on target environment.  
**Parent:** merged ALIVE-SF-01 P0 (PR #27).  
**Scope:** read-only graph APIs over already saved ALIVE-12 research memories.

## Implemented

- `alive/exploration_api.py` introduces a bounded deterministic graph projection keyed by existing browser-companion goal ID.
- Authenticated `GET /api/v1/exploration/inquiries` lists owner-created companion goals.
- Authenticated `GET /api/v1/exploration/inquiries/{goal_id}` returns one inquiry with source nodes, owner-saved source relationships, and lexical candidate concepts appearing in at least two distinct saved research memories.
- Provenance links are existing authoritative research-memory IDs; URLs and SHA-256 fingerprints are source attributes. No source excerpts are returned and there are no external calls.
- Query selects `WebExperience` scoped by current instance, `research_memory` kind, `active` status, and goal ID. If source is withdrawn, the next read excludes it and the graph is recomputed; no stale graph DB copy exists.
- Results are bounded to 200 current active memories per goal and 12 candidate concepts. Pagination/truncation is disclosed.
- No new models, migrations, extension permissions, paid model calls or ALIVE-14 execution changes.

## Important limitations

This is **not** the complete P1 architecture. It is a first source-backed **projection**, not yet a durable graph that stores owner corrections, rejected hypotheses or multiple inquiry membership. It has no skill-registry API or browser UI. Explicit support/contradiction inference is deliberately absent. Lexical co-occurrence may overproduce meaningless candidates; candidates are not verified connections. An opaque source ID still needs drill-down via a separately authorized existing source endpoint. Research memory is only linked to its existing companion goal.

## Required validation before merge

1. Run `uv run pytest tests/test_exploration_api.py tests/test_skill_forge_p0.py` and full backend suite on the pinned Python environment.
2. API integration test with valid owner token and invalid token.
3. Source A + source B saved within an active goal -> graph has inquiry and source nodes; candidate shared terms are labelled.
4. Withdraw source B via ALIVE-12 -> next response excludes B and any concepts requiring B. Check persisted restart as well.
5. Different goal and different instance must not leak source or metadata.
6. Graph reads must not trigger retrieval model, external inference or any writes.
7. Compare query performance with a 200-memory source set; monitor SQLite JSON path behavior and Postgres.
8. Independently review endpoint error handling, URL visibility, and correctness against current migrations.
9. Check PR #26 safety review remains unresolved separately; this slice does not affect pilot approval readiness.

**Stop here:** Do not merge this slice without independent review and native API tests.

## Next

P1B should introduce correction and inquiry-membership persistence using ALIVE's existing SQLAlchemy/Alembic architecture, coupled transactionally to withdrawal. P2 should present a read-only Digital Lens in the Chrome side panel; P3 should add constrained conversational manifest compilation and explicit skill approval. This PR does not pretend those features have shipped.
