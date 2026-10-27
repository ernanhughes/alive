# ALIVE-08 results

Status: **PASS_NO_ADVANTAGE_DEMONSTRATED**

Protocol SHA-256: `f32bfad1e60c497b1e958f8ddce041fe3e1977d3cfd4987ac95cb92f8922dd92`  
Corpus SHA-256: `3eb0cc7b8ad3bb23f7c708881ea7f07ba4fff0b099312c25f37070573dd1de67`  
Seeds: 17, 23, 31, 43, 59

## Primary comparison

| Comparison | Mean difference | 95% cluster bootstrap CI | Clusters | Episodes |
|---|---:|---|---:|---:|
| alive_hierarchical - flat_empirical | -0.0248 | [-0.0442, -0.0090] | 229 | 1500 |

## Arm means

| Arm | Mean utility | Success | Missed changes | Unnecessary retrievals | Retrieval rate | Memory coverage |
|---|---:|---:|---:|---:|---:|---:|
| stateless_prior | 0.0153 | 0.586 | 114 | 507 | 0.537 | 0.000 |
| fixed_heuristic | -0.0208 | 0.688 | 167 | 301 | 0.364 | 0.000 |
| flat_empirical | 0.0723 | 0.348 | 16 | 962 | 0.905 | 1.000 |
| alive_hierarchical | 0.0475 | 0.389 | 47 | 869 | 0.823 | 1.000 |
| alive_no_history | -0.2747 | 0.725 | 412 | 0 | 0.000 | 0.000 |
| alive_shuffled | -0.0944 | 0.512 | 203 | 529 | 0.492 | 1.000 |
| history_proxy_not_meta | 0.0108 | 0.462 | 95 | 712 | 0.686 | 1.000 |
| alive_online_ablation | 0.0711 | 0.390 | 25 | 890 | 0.851 | 1.000 |

## Paired comparisons

| A vs B | Mean difference | 95% CI | Clusters |
|---|---:|---|---:|
| alive_hierarchical_vs_flat_empirical | -0.0248 | [-0.0442, -0.0090] | 229 |
| alive_hierarchical_vs_stateless_prior | 0.0321 | [0.0045, 0.0595] | 229 |
| alive_hierarchical_vs_fixed_heuristic | 0.0683 | [0.0358, 0.1030] | 229 |
| alive_hierarchical_vs_alive_no_history | 0.3221 | [0.2576, 0.3875] | 229 |
| alive_hierarchical_vs_alive_shuffled | 0.1419 | [0.1005, 0.1843] | 229 |
| alive_hierarchical_vs_history_proxy_not_meta | 0.0367 | [0.0086, 0.0654] | 229 |

## Held-out utility by source status

| Arm | seen | unseen | novel |
|---|---:|---:|---:|
| stateless_prior | -0.0200 | 0.0104 | 0.1312 |
| fixed_heuristic | -0.0283 | -0.0164 | -0.0072 |
| flat_empirical | 0.0181 | 0.0180 | 0.3432 |
| alive_hierarchical | 0.0077 | -0.0052 | 0.2720 |
| alive_no_history | -0.2320 | -0.2000 | -0.5520 |
| alive_shuffled | -0.1109 | -0.1088 | -0.0160 |
| history_proxy_not_meta | -0.0120 | -0.0148 | 0.1304 |
| alive_online_ablation | 0.0131 | 0.0236 | 0.3400 |

## Ablations

| Ablation | Mean utility | Difference vs correct | 95% CI |
|---|---:|---:|---|
| correct_history | 0.0475 | 0.0000 | [0.0000, 0.0000] |
| no_history | -0.2747 | 0.3221 | [0.2576, 0.3875] |
| shuffled_history | -0.0944 | 0.1419 | [0.1005, 0.1843] |
| fixed_heuristic | -0.0208 | 0.0683 | [0.0358, 0.1030] |

## Validity and resources

- Validity checks: `{'protocol_frozen': True, 'selected_parameter_present': True, 'corpus_hashes_match': True, 'observations_exclude_hidden_fields': True, 'all_arms_use_same_scenarios': True, 'zero_provider_calls_and_tokens': True, 'all_actions_governor_allowed': True}`
- Provider calls: 0
- Tokens: 0
- Estimated provider cost: $0.000000
- Mean decision latency: 0.108 ms

## Counterfactual example

```json
{
  "scenario_id": "evaluation-17-00000",
  "source_status": "seen",
  "source_class": "stable",
  "observation": {
    "cadence": "weekly",
    "goal": "Keep the source's current measurement accurate.",
    "claim": 33.5,
    "claim_age": "day",
    "source_id": "src-4d2533abecce",
    "permitted_actions": [
      "monitor",
      "retrieve"
    ]
  },
  "true_changed": false,
  "alive_action": "retrieve",
  "no_history_action": "monitor",
  "alive_utility": -0.2,
  "no_history_utility": 0.0,
  "counterfactual_utilities": {
    "monitor": 0.0,
    "retrieve": -0.2
  },
  "alive_context": "class:weekly:day",
  "alive_recalled_ids": [
    "alive_hierarchical:training-17-00196",
    "alive_hierarchical:training-17-00197",
    "alive_hierarchical:training-17-00198",
    "alive_hierarchical:training-17-00199"
  ],
  "policy_hash_before": "cfce377bab36883f3d05233f97df4756c1f3be8a7ab9e0c206f9a4c1657d4e9f",
  "policy_hash_after": "cfce377bab36883f3d05233f97df4756c1f3be8a7ab9e0c206f9a4c1657d4e9f",
  "note": "Simulator-defined counterfactual; not a real-world outcome."
}
```

## Interpretation boundary

The counterfactual utilities are simulator-defined, not real-world outcomes. The history proxy is not a Meta model. No paid inference or native Chrome was used. A positive result applies to this frozen, controlled environment only.
