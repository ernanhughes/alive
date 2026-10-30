# Adversarial coverage

Tests validate contracts and transaction behavior; they do not prove semantic
correctness, model intelligence or policy improvement. Fixture authority is a
trusted in-process harness, not a public trust flag.

| Requested cases | Executable coverage |
| --- | --- |
| 1–7: episode, workflow, goal, instance, hash, withdrawal and history | `test_identity_substitution_and_cross_instance_reads`, `test_feedback_revalidates_workflow_before_learning`, `test_withdrawal_correction_and_historical_immutability`, lifecycle/restart test. |
| 8–13: proposal/decision/action separation, frozen policy, unsupported actions, shadows, no early learning | `test_complete_restart_replay_and_read_only_api`, `test_independent_feedback_tracks_frozen_decision_after_proposal_diverges`, `test_shadow_never_overrides_frozen_decision`, original candidate-mask tests. |
| 14–21: trusted feedback, self-certification, wrong decision, duplicate/conflict, rewards, source substitution, correction | `test_untrusted_observer_self_certification`, `test_feedback_bound_to_independent_payload`, `test_reward_substitution`, `test_durable_identical_duplicate_conflict_and_restart_safe`, `test_conflicting_independent_measurement_versions_refused`, original reward-bound tests and quarantine test. |
| 22–28: deterministic, unique, source-bound durable learning and rollback | Lifecycle/restart, independent-lock concurrency, failed/cancelled transaction tests, measurement-consumption tests (literal and renamed replay), read-time deterministic chain/hash validation and frozen-policy tests. |
| 29–32: provider/credential/Pi/admission boundary | Original fresh-import and missing-capability tests, unchanged ModelGateway ratchets, `test_assessment_cannot_manufacture_workflow_or_model_execution`. Durable adapter accepts fixture results only and has no dispatch capability. |
| 33–35: Pi receipts, ambiguous execution and immutable workflow identity | Ten synthetic receipt-resolution cases; existing real Pi tests and 13-check scripted upstream integration separately. The Intelligence lifecycle does not claim their Pi receipts. |
| 36–41: replay, concurrency, restart, interruption, revisit immutability, unknown outcomes | PostgreSQL explicit harness, separate-interpreter replay, container process restart/HTTP replay, concurrent feedback, transaction failure/cancellation and immutable-history tests. Episode two remains feedback-unknown unless a separate observer supplies an outcome. |

`python -B -m scripts.intelligence_mutations` runs an ordinary passing baseline
before each test-only runtime mutation. A nonzero collection/setup result does
not count as a killed mutation. Monkeypatch restores the original after each test;
there are no production mutation flags or bypasses.

| Mutation | Regression expected to fail |
| --- | --- |
| Ignore custody source/type authority | `test_untrusted_observer_self_certification` |
| Ignore exact independent feedback payload binding | `test_reward_substitution` |
| Substitute candidate estimates for frozen active policy | `test_complete_restart_replay_and_read_only_api` |
| Suppress empirical update | `test_complete_restart_replay_and_read_only_api` |
| Ignore historical fixture workflow binding | `test_feedback_revalidates_workflow_before_learning[context]` |

Individual actual receipts are in `mutations.json`. These five targeted mutations
are all killed, with five passing baselines and zero survivors. The normalized
measurement consumption constraints additionally have positive/negative tests
across distinct decisions and renamed evidence identities; they were not included
in the five-mutation score.
