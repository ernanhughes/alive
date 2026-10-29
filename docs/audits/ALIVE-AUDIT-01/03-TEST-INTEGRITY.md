# ALIVE-AUDIT-01 — Test integrity

## Baseline receipts

| Check | Independently observed result | Receipt |
|---|---|---|
| Main backend suite, Windows / CPython 3.13.3 | **619 passed, 7 skipped, 1 xfailed**, 500.92s | [backend-full.txt](receipts/backend-full.txt) |
| Main recovery + gateway focused baseline | 15 passed | [focused-baseline.txt](receipts/focused-baseline.txt) |
| Dashboard Vitest | 7 passed across 3 files | [dashboard-tests.txt](receipts/dashboard-tests.txt) |
| Dashboard production build | Passed | [dashboard-build.txt](receipts/dashboard-build.txt) |
| Extension + notebook Node tests | 38 passed | [extension-tests.txt](receipts/extension-tests.txt) |
| PR54 Docker/demo Python slice | 26 passed | [pr54-tests.txt](receipts/pr54-tests.txt) |
| PR55 gateway suite | 32 passed | [pr55-gateway.txt](receipts/pr55-gateway.txt) |
| Independent adversarial suite on main | **12 passed, 8 failed** (20 parameterized cases) | [adversarial.txt](receipts/adversarial.txt), [JUnit XML](receipts/adversarial.xml) |
| Independent PR55 scanner/operation probes | 3 passed, 17 deselected | [pr55-independent.txt](receipts/pr55-independent.txt) |
| Historical main CI, Ubuntu | 618 passed, **1 failed**, 7 skipped, 1 xfailed | [ci-failed.txt](receipts/ci-failed.txt) |

The skipped and expected-failure tests are not passes; see [test collection](receipts/test-collection.txt) and baseline receipts. Windows ZMQ emits Proactor/selector compatibility warnings; they did not invalidate the reported runs. No claim is made that the Linux timing failure was reproduced by the original unmodified test locally.

## Inventory and behavior mapping

[test-inventory.json](test-inventory.json) inventories all 533 Python test definitions, locations, decorators and assertion/raises counts. Parameterized instances produce the larger collection count. [01-INVENTORY.md](01-INVENTORY.md) maps test families to subsystems; [coverage.csv](coverage.csv) separately records semantic source review. Test names are claims about behavior, not proof that every assertion is strong. This investigation did not semantically review every test body or execute every native script and dashboard Playwright spec.

## Independent scenarios

Constructed after inspecting production code; all provider responses below are controlled HTTPX fixtures. These are bounded adversarial additions, not a new real-model evaluation. The input and expectation are implemented in [test_adversarial.py](test_adversarial.py). Passing cases establish only their stated invariant.

| Scenario | Expected invariant / constructed input | Observed on main | Existing-suite relationship / status |
|---|---|---|---|
| S01 | Empty string, zero, null, false, empty list nested in request data survive serialization | Exact values preserved | New edge combination; PASS |
| S02 | Nested tool-like names/arguments/ID plus Unicode, slash, quote, newline survive | Exact nested object preserved | Not a general tool executor test; PASS |
| S03 | Long Unicode value and deeper nested zero survive | Exact object preserved at transport | New size/content combination; PASS |
| S04 | Explicit zero output ceiling rejected or unchanged | Became 1536 | Baseline parity can conceal common defaulting; F-007 CONFIRMED |
| S05 | HTTP200 empty `choices` becomes typed provider failure | Raw IndexError | Green baseline missed envelope variant; F-004 CONFIRMED |
| S06 | HTTP200 null content refused at provider boundary | `Generation(text=None)` | Later caller validation is a separate layer; F-004 CONFIRMED |
| S07 | HTTP200 list content refused or explicitly normalized | `Generation(text=list)` | Same boundary gap; F-004 CONFIRMED |
| S08 | `finish_reason=length` cannot be success | Typed `output_truncated` | Consistent with implemented protection; PASS |
| S09 | Gateway/request operation mismatch refused before transport | Dispatched | Baseline unknown-factory test checks a different boundary; F-006 CONFIRMED |
| S10 | Rogue constructor in first file detected even when last file clean | Detected | Existing single-file scanner test cannot alone prove this; PASS |
| S11 | First-file import alias cannot evade direct-dispatch ratchet | No findings | Existing literal-name self-test insufficient; F-005 CONFIRMED |
| S12 | Invalid first claim reference cannot hide behind valid last claim | Rejected | Existing reference test covers one invalid claim; new all-item arrangement PASS |
| S13 | Bad bearer denied and hostile browser Origin denied independently | 401 and 403 | Existing auth family covers related behavior; PASS |
| S14 | Grant for Python page cannot capture MDN page | 403 | Existing consent identity coverage agrees; PASS |
| S15 | Withdraw first of two saved sources without removing second; cannot resurrect first | Second active, resave first 409 | Combines collection processing, persistence and identity; PASS |
| S16 | Capture with deliberately wrong SHA refused | 403 | Existing hash protection independently mutation-tested; PASS |
| S17 | Empty persisted local token cannot authorize missing credentials | HTTP read/write200; unauthenticated WS event | Existing tests configure a valid explicit token, missing persisted-file state; F-001 CONFIRMED |
| S18 | Changed second snapshot cannot inherit first hash/unchanged status | Different hashes; changed excerpt | Multi-capture state path PASS |
| S19 | Unsafe second history entry prevents partial acceptance of clean first entry | Refused | All-item path PASS; no accepted import returned |
| S20 | Deadline after durable reservation commit must settle invocation | FAILED run with `reserved` invocation | Existing timing test sees the same failure nondeterministically in CI; deterministic window confirms F-002 |

The transport receipts retain synthetic intended data beside actual dispatched JSON, without Authorization headers: `receipts/transport-*.json`. Scenario S19 asserts refusal; it is not a comprehensive row-count rollback check for all importer failures.

## Mutation checks

[mutation_probe.py](mutation_probe.py) makes changes **only to in-memory functions in fresh subprocesses**. Production files and frozen material are untouched. Each original target also passed unchanged ([control receipt](receipts/mutation-control.txt)).

1. Replace `society.validate_references` with a no-op. Existing `test_attention_protocol_and_evidence_integrity` fails at the expected `pytest.raises(ValueError)` assertion: mutation **KILLED**. [Receipt](receipts/mutation-references.txt).
2. Disable only the initial reviewed capture hash check in an in-memory copy of `WebCompanion.snapshot`. Existing `test_exact_consent_hash_and_owner_goal_isolation` fails because the bad-hash request is accepted: mutation **KILLED**. [Receipt](receipts/mutation-capture-hash.txt).

Main's existing request-ceiling mutation proof also ran in the gateway suite. It inflates validated configuration rather than deleting a guard. That establishes sensitivity to the configured threshold but is narrower than a mutation of every admission/settlement path. PR55's added call-budget mutation test ran in its 32-test suite; its assertion demonstrates a second dispatch when that budget input is inflated.

**Not executed:** exhaustive mutation campaign; independent guard-removal tests for every ALIVE-14 fatal barrier, restart reconciler, source invalidator, stage index, credential check, and concurrency fence. Existing historical regression families pass, but their presence must not be relabelled independent mutation evidence.

## Why green was insufficient

* **Shared implementation oracle:** Main wire parity compares direct MetaProvider with a gateway using the same MetaProvider. If shared serialization/defaulting is wrong, both sides agree. Independent sentinel expectations catch zero-cap defaulting; PR55 adds a golden request but its provenance is still code-generated and warrants review.
* **Single-item scanner oracle:** Existing ratchet self-test supplies a literal constructor in one file. It cannot prove all-file traversal or alias handling. Our first-file/last-clean-file case exonerates the reported indentation pattern at this commit, while the alias case exposes a different real guard defect.
* **Fixture state blind spot:** Most API fixtures explicitly inject a valid bearer token. They never exercise startup with a truncated persisted token. This explains how authentication-positive and invalid-bearer tests can pass while F-001 exists.
* **Timing rather than owned lifecycle barrier:** Sleeping inside a provider usually cancels after the reservation handler begins. It does not force cancellation during transaction exit. The red Ubuntu run is meaningful evidence, and the new controlled exit barrier shows the gap. Increasing sleeps or weakening the expected status would hide it.
* **Integration levels differ:** Browser DOM mocks, API tests, Docker HTTP lifecycle checks, and real docked-extension tests establish different claims. PR54's real Chrome gap was real before this audit; now that specific pinned configuration has an independent native-browser receipt.
* **Quantity is not assurance:** 619 passing backend tests coexist with independent confirmed defects. Assertion counts, test names, and source-file import coverage do not prove every invariant. [coverage.csv](coverage.csv) intentionally exposes unfinished review instead of claiming complete coverage.

## Next test work

Add persisted-token corruption/absence races, explicit lifecycle cancellation barriers, and malformed provider envelope/usage cases first. Keep each regression red on its affected baseline and green only with its correction. Then independently mutate durable ALIVE-14 fatal/ordering/withdrawal fences. Expand failure/restart tests across SQLite and PostgreSQL and rerun Linux CI at the final pinned candidate. Leave frozen protocols/evaluations unchanged.
