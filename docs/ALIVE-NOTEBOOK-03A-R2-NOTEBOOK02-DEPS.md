# ALIVE-NOTEBOOK-03A-R2 — Notebook-02 contract dependencies (narrow-migration spec)

R2 does not rewrite production qualification. The items below must be
resolved in a separate, narrowly scoped migration before Notebook-03B may
consume the affected Notebook-02 contracts. Each item names the current
behavior, the required contract, and the acceptance check.

## 1. Per-source requested-quote status

- Current: an aggregate quote status can mask which source's requested
  quotation failed.
- Required: versioned per-source requested-quote status; never use the
  aggregate as consent or citation proof.
- Accept: regression test with one failing source among several passing;
  per-source statuses preserved and the aggregate not consulted for proof.

## 2. Integrity precedence and per-source errors

- Current: a missing historical source can mask a current-source hash
  mismatch behind a single precedence enum.
- Required: preserve per-source integrity outcomes; any hash mismatch
  fails the affected source; no single enum hides a per-source failure.
- Accept: paired fixtures (missing-history vs tampered-current) produce
  distinct, correctly attributed failures.

## 3. Title consistency

- Current: historical title drift blocks the body while current title
  drift does not (asymmetric presentation handling).
- Required: separate presentation consistency from body/quote validity in
  a narrow migration; document which drift blocks what and why.
- Accept: title-only drift fixtures pass body/quote validity while
  presentation flags remain visible.

## 4. Bounded occurrence-count semantics

- Current: occurrence counts cover only bounded excerpts without explicit
  scope/offset units.
- Required: explicit scope and offset units; no full-document uniqueness
  claim from bounded-excerpt counts.
- Accept: counts carry scope/offset metadata; tests assert bounded scope.

## 5. Historical derived-metric comparison in CI

- Current: the old derived-report gate has no committed expectation
  comparison in CI (03A/03A-R1 expectation checks cover only the new
  baseline projections and must not be read as fixing this gate).
- Required: deterministic committed-expectation comparison for the old
  historical derived report, in a separate narrow follow-up.
- Accept: CI fails on changed derived output unless expectations are
  explicitly amended.

## 6. Single-source and two-source qualification adapters

- Required: reviewed adapters binding exact serialized evidence plus
  prompt/schema/model/settings, owner approval of that exact request,
  persisted caps, cancellation and restart state, source revalidation,
  and structured output/citation checking. Fixture `access` fields are
  experimental conditions, never production authorization proof.
- Accept: adapter tests resolve owned IDs server-side and refuse
  caller-supplied access bits.

## 7. Exact-payload preview and authorization; cancellation and restart

- Required: exact-payload preview → authorize → analyze binding
  (payload/source hashes, provider/model, token and spend caps);
  cancellation and restart qualification for the new adapters.
- Accept: interrupted-attempt accounting and restart-state tests pass
  for the adapter paths.

## Windows recovery/budget observation

One previously observed Windows recovery/budget failure was not
conclusively reproduced. Its status is **unconfirmed**: do not depend on
that path in 03B, do not assume a confirmed regression, and do not
silently bypass it. The narrow migration must re-attempt reproduction on
Windows with a clean profile and record the outcome before the 03B
governance adapter relies on recovery/budget behavior.
