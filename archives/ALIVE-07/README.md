# ALIVE-07 - Multilingual-ready relevance and adaptive evaluation

Status: **PASS_WITH_LIMITATIONS** (controlled evaluation; native qualification blocked).

This archive records ALIVE-07's config-driven multilingual relevance policy, its frozen
evaluation corpus and the per-language baseline results. It is **controlled test-harness
evidence**, not native Chrome or Meta qualification.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Base | `origin/main` at `70e2639b0136da9c675c68a24598e96321d3e28a` (ALIVE-06 merged) |
| Branch | `opencode/alive-07-multilingual-relevance` |
| Current policy | `deterministic-multilingual-relevance-v2` |
| Previous policy | `deterministic-goal-excerpt-overlap-v1` (historical) |
| Evidence kind | Controlled FastAPI/SQLite evaluation and synthetic provider |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |

## External configuration

`config/` in this archive is a frozen copy of:

```
config/relevance/policy.toml
config/relevance/languages/en.toml
config/relevance/languages/zh.toml
config/relevance/languages/ar.toml
```

The runtime loads and validates these files in `alive/relevance.py`. TOML is data-only; unknown
keys, malformed TOML, unsupported strategies and missing declared language files fail closed.
The configuration fingerprint is `dfba62bc4c5de72c9073162d66b8629e3edaa88e77af4b6a2bf220480c6dc205`
for the evaluated files. Full hashes are in `evidence/config-provenance.json`.

## Language behaviour

| Language | Strategy | Normalisation |
|---|---|---|
| English | word tokens, external stop words | NFKC + casefold |
| Chinese | Han character bigrams | NFKC, configured stop characters |
| Arabic | word tokens, external stop words | NFKC + casefold + diacritic/orthographic normalisation |

Unsupported scripts, materially mixed scripts, and an explicit language that does not match the
text produce `uncertain`. Uncertain and `no_action` decisions create no note or provider
reservation. An explicit owner override is required before an uncertain state can be analysed.

## Frozen corpus

`corpus/relevance.jsonl` contains 27 independently labelled cases:

- development, calibration and held-out splits;
- English, Chinese and Arabic relevant/irrelevant cases;
- relevant cases without literal overlap;
- ambiguous English cases;
- mixed-language and unsupported-script cases.

Policy code receives goal, excerpt and language only; labels are read by the evaluator. The corpus
SHA-256 is `eef4178558a9cc668e72e73d220f5544926b7abc64d1624653cd1bb2f8e353a5`.

## Overall metrics

| Baseline | Precision | Recall | False abstention | False investigation | Uncertainty | Calls avoided |
|---|---:|---:|---:|---:|---:|---:|
| ALIVE-06 exact overlap | 100.0% | 36.4% | 63.6% | 0.0% | 0.0% | 20 |
| Simple no-stop-word overlap | 100.0% | 72.7% | 27.3% | 0.0% | 0.0% | 16 |
| ALIVE-07 multilingual v2 | 100.0% | 72.7% | 27.3% | 0.0% | 22.2% | 19 |
| Conservative uncertainty | 100.0% | 72.7% | 0.0% | 0.0% | 70.4% | 19 |

ALIVE-07 improves relevant recall over ALIVE-06 on this corpus while explicitly marking 22.2% of
cases uncertain. The 27.3% false-abstention rate is the central limitation: relevant cases with no
literal/ngram overlap are still declined. The conservative baseline reaches zero false abstention
only by routing 70.4% of cases to owner intervention.

## Held-out v2 by language

| Language | N | Precision | Recall | False abstention | Uncertainty |
|---|---:|---:|---:|---:|---:|
| Arabic | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| English | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| Chinese | 3 | 100.0% | 50.0% | 50.0% | 0.0% |
| Mixed/unsupported | 2 | n/a | n/a | n/a | 100.0% |

Per-language and per-split confusion counts are in `evaluation/relevance-metrics.json`.

## Experience reuse

The only demonstrated history mechanism remains ALIVE-05/06 exact-match reuse:

| Case | Decision | New calls |
|---|---|---:|
| Same goal/URL/excerpt after useful feedback | recall | 0 |
| Changed excerpt after feedback | analyse | 0 before call |
| Same excerpt, different goal | analyse | 0 before call |
| Negative feedback on matching note | analyse | 0 before call |

This is exact-match reuse, not learned generalisation. ALIVE-07 does not treat lexical similarity as
an improved experience policy.

## Verification

| Check | Result | Transcript |
|---|---|---|
| Backend suite | 110 passed | `validation/backend.txt` |
| Relevance + web + Living focused | 31 passed | `validation/relevance-web-living-focused.txt` |
| Frontend suite | 7 passed | `validation/frontend-tests.txt` |
| Production dashboard build | Passed | `validation/frontend-build.txt` |
| Ruff check and format | Passed | `validation/ruff.txt` |
| Extension JavaScript syntax | Passed | `validation/extension-js.txt` |
| Whitespace diff | Clean | `validation/whitespace.txt` |

## Native qualification

`evidence/native-status.json` records the blocker: standard ports `8000` and `5173` were occupied
by the primary worktree. ALIVE-07 did not start or stop those processes, did not open native Chrome
against them, and did not make a Meta call.

## Limits

- Lexical/ngram overlap is not semantic relevance. False abstention is material, especially for
  relevant Chinese text without a shared bigram.
- Chinese uses character bigrams, not segmentation or semantic parsing.
- Arabic normalisation is deliberately small and not morphological.
- Language detection is script-based; mixed content is reported as uncertain rather than guessed.
- No native side-panel or Meta qualification was performed for ALIVE-07.
- The corpus is small and controlled; no general multilingual performance claim is made.
- The previous ALIVE-05/06 archives remain unchanged.
