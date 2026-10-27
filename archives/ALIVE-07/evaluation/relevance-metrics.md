# ALIVE-07 relevance evaluation

Policy: `deterministic-multilingual-relevance-v2`  
Config fingerprint: `dfba62bc4c5de72c9073162d66b8629e3edaa88e77af4b6a2bf220480c6dc205`  
Corpus SHA-256: `eef4178558a9cc668e72e73d220f5544926b7abc64d1624653cd1bb2f8e353a5`  
Cases: 27

## Overall baselines

| Baseline | Precision | Recall | False abstention | False investigation | Uncertainty | Calls avoided | Owner intervention |
|---|---:|---:|---:|---:|---:|---:|---:|
| alive06_exact_overlap | 100.0% | 36.4% | 63.6% | 0.0% | 0.0% | 20 | 0 |
| simple_no_stopwords | 100.0% | 72.7% | 27.3% | 0.0% | 0.0% | 16 | 0 |
| alive07_multilingual_v2 | 100.0% | 72.7% | 27.3% | 0.0% | 22.2% | 19 | 6 |
| conservative_uncertainty | 100.0% | 72.7% | 0.0% | 0.0% | 70.4% | 19 | 19 |

## ALIVE-07 v2 held-out by language

| Language | N | Precision | Recall | False abstention | Uncertainty |
|---|---:|---:|---:|---:|---:|
| ar | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| auto | 2 | n/a | n/a | n/a | 100.0% |
| en | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| zh | 3 | 100.0% | 50.0% | 50.0% | 0.0% |

See `relevance-metrics.json` for per-language, per-split confusion counts and all baselines.

## Interpretation

- Relevant recall counts an uncertain decision as not recalled, so a conservative policy cannot hide behind abstention.
- False abstention counts a relevant label predicted irrelevant; uncertainty is reported separately.
- Calls avoided counts every non-relevant prediction; it is not evidence of correct abstention.
- The corpus is controlled and small. It is not a general multilingual benchmark.
