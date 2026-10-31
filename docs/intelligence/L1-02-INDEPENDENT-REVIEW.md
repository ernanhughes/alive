# L1-02 — Independent review handoff

A green CI run is not a security review. These are the questions to attack, where each answer lives,
and the tests that already attack it. Please add tests of your own; the ones here were written by
the implementer.

| Question | Where to look | Existing tests |
| --- | --- | --- |
| Is remote inference genuinely authorized by the owner? | `alive/admission/service.py` (`approve`, `start`, `verify_grant` via `workflows.context.authorized`); no approve route exists in `api.py` | `test_hand_published_analysis_grant…`, L1-01's `test_owner_admission.py` |
| Are model, provider, transport, role contract and budget bound exactly? | `profiles.disclosure`, `service.current_terms`, `workflows.context.model_claim` | `test_changed_model_terms_or_source_refuse_before_any_dispatch`, `test_a_change_after_start_is_refused_at_the_reservation…` |
| Can the model reach an unapproved source? | `analysis.adapters.analyze` compares each supplied byte with the approved capture; `custody.resolve` for `repository.analyze` | `test_stage_output_cannot_smuggle…`, `test_only_the_approved_files_and_one_request_reach_the_provider` |
| Does the workflow bypass L1-01 admission? | `Grant.admission_ref` forces `verify_grant`; the analysis recipe hash cannot be used under the inspection profile | `test_the_inspection_review_cannot_be_turned_into_an_inference_grant` |
| Can model output trigger an action? | `RepositoryAnalysis` is `extra="forbid"`; the role has no tools; output is only data | `test_model_output_that_breaks_the_contract…`, `test_model_output_with_extra_authority_fields…` |
| Do cancellation and retries keep governance? | existing runner/egress semantics, unchanged | `test_cancelling_during_the_provider_call_is_not_retried`, `test_a_provider_failure_is_classified…`, `test_replay_never_dispatches…`, `test_two_simultaneous_starts…` |
| Does source content leak to generic events? | `kernel.public_payload` withholds stage results | the end-to-end test greps `/api/v1/events` for a canary string |
| Can a fabricated reference be marked verified? | `analysis/validation.py`; nothing is ever marked verified | unit tests on every citation category; benchmark rows |
| Do historical identities stay truthful? | immutable `Admission.terms`; retained binding and execution snapshots | inherited from L1-01 and PI-03A |

## Known limitations to weigh

* **Dependency.** L1-01 (PR #80) is not merged or independently reviewed. Do not treat the admission
  mechanism as qualified production foundation until it is.
* **Clear-text retention.** Prompt, response and stage outputs are stored unencrypted in the local
  database (`ModelInvocation.input_json`, stage result events, the retained artifact). Withdrawal
  stops new use; it does not delete history. There is no deletion policy.
* **Pi event retention.** The generic feed withholds stage results. Pi's own retained run events were
  not audited for echoed prompt or response text with a real Pi; the tests use a fake Pi.
* **Single destination.** There is no local inference path and no network allowlist beyond the
  configured endpoint; the disclosure control is the separate source operation and the review.
* **Autonomy.** A model admission requires Cognition started with `meta`. If autonomy is running,
  the Governor's existing loop continues under its own budgets between workflows.
* **Time-of-check window.** The reservation re-verifies the Grant (including source custody) inside
  its transaction; a withdrawal landing between the stage's own custody check and the reservation
  is caught by the reservation's re-check, and again at the dispatch fence for the digest.
* **Scale.** At most 8 files and 8,192 bytes, bounded by the Governor's per-request ceiling. Larger
  repositories need an explicitly approved selection, which this milestone does not provide.
* **Not run.** Live model, real pinned Pi for this workflow, browser E2E, Docker, Linux container,
  full backend suite (CI).
