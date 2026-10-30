# Independent reviewer handoff

Review this draft against base `07c0c0663b8e5b1b0b77ec7ed9bde0920805bcfa`.
Resolve its exact head with `git rev-parse HEAD` or the PR metadata. The final report
records the implementation commit; its own documentation commit cannot contain its
own hash. Do not approve based on test counts alone.

Attempt to forge observer authority through `/api/v1/events`; replace source,
snapshot, workflow input or stage identity after assessment; change a reward under
the same feedback ID; replay an accepted record after restart; and race independent
worker locks. None may produce another learning update. Verify transaction rollback
on failure/cancellation and that the frozen active hash never changes. Inspect
the episode-two proposal/decision separation and the absence of authorized actions.

Run `python -B -m pytest -q`, Ruff check/format, the explicit disposable PostgreSQL
`scripts.intelligence_check` harness and `scripts.intelligence_mutations`. Mutation
baselines must pass; mutated tests must fail normally, without collection/setup
errors. Inspect every receipt in the report and distinguish real Pi with scripted
upstream from the fixture-backed Intelligence lifecycle. PI-02B and live model
admission remain unavailable. No inference budget is granted by this handoff.

Read `ARCHITECTURE.md` for the reuse matrix and trust limits. In particular, inspect
the source/type custody check, exact feedback payload binding, unique constraints,
CAS update, read-time history validation, quarantine behavior and typed API field
allow-lists. Privileged DB tampering and live evidence authorization are not solved
by hashes. No automatic merge, action execution or policy promotion is authorized.
