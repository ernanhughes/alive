# Cognitive society

| Role | Implementation and authority |
| --- | --- |
| Observer | Structured model interpretation of supplied observations, entities, changes and uncertainty; no tools |
| Proposer | Structured model hypotheses, bounded candidate actions and evidence-backed claims; no permission grant |
| Critic | Structured model critique against supplied evidence, missing references and contradictions; may recommend abstention |
| Investigator | Deterministic, budgeted read-only retrieval of authorised memory and version-checked controlled source records |
| Evaluator | Deterministic claim/source comparison; model evaluator is advisory only in the fixed-workflow benchmark |
| Governor | Python state machine, budget reservations, schema/reference validation, permissions, cancellation and persistence |

The runtime uses one pinned Meta model by default. `ALIVE_ROLE_MODELS` can map observer/proposer/critic to explicit available model IDs; starting Meta autonomy checks provider model access. The primary benchmark intentionally ignores role overrides and pins one Meta model across every arm. The current Investigator does not invoke Pi or an additional model: ALIVE-01 Pi remains available manually, while automatic evidence acquisition uses scoped Python operations with enforceable tool limits. Model escalation and autonomous Pi tools are deferred.

The default path is Observer → Proposer → Critic → deterministic Investigator/Evaluator/Governor. `use_critic=false` provides a real runtime ablation. Proposer or Critic abstention is honoured. Evidence changes during the investigation cause abstention rather than stale-source execution. No model can recursively start roles or grant additional budget.

## Grounded evaluation

The evaluator separately checks the original observation and proposed conclusion. Its statuses are:

- `VERIFIED`: exact subject/predicate/value match to a cited controlled measurement.
- `SUPPORTED`: value matches, but the claim lacks the independent source citation.
- `CONTRADICTED`: measured value disagrees with the claim.
- `INCONCLUSIVE`: independent evidence is absent or sources conflict.
- `FAILED`: execution/validation failure, recorded by the Governor.

Contradicted observations can produce a verified revised conclusion. Agreement between model roles cannot produce a verified verdict without a matching source. Confidence scores are model outputs, not verification probabilities.

## Action authority

Class A `record_analysis` executes automatically within the reserved budget. It writes a tagged analysis memory in the same transaction as its action status and experience. Class B `lab_draft` requires either explicit configured `lab_writes=true` or approval of that specific pending action. It can only update the current controlled environment, with a matching version. Class C `external_message` is unsupported even if an approval request is submitted.

`preferred_action=lab_draft` allows an explicitly configured laboratory draft experiment and is used by the browser approval test. This is trusted configuration, never authority inferred from a page. Humans can inspect/approve/reject/cancel pending actions through `/cognition/actions/{id}/decision`. Repeated approval of an executed action returns its existing outcome without another effect. Stop cancels pending work; historical experience is retained.
