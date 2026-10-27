# ALIVE-07 - Multilingual-Ready Relevance and Adaptive Evaluation

ALIVE-07 keeps ALIVE-06's deterministic browser decision boundary but moves language-specific
resources into versioned external configuration and introduces a successor relevance policy.

The goal is not general multilingual understanding. It is a transparent, testable baseline that
can support English, Chinese and Arabic observations without language rules living inside the
decision loop.

## Policy versions

| Policy | Status | Behaviour |
|---|---|---|
| `deterministic-goal-excerpt-overlap-v1` | Historical | ALIVE-06 English content-word overlap |
| `deterministic-multilingual-relevance-v2` | Current | Config-driven English, Chinese n-grams and Arabic normalisation |

The v2 decision records the policy, configuration fingerprint, requested and resolved language,
language source, matched terms and uncertainty reason. Historical v1 decisions are not rewritten.

## Configuration

```
config/relevance/
  policy.toml
  languages/
    en.toml
    zh.toml
    ar.toml
```

All files are UTF-8 TOML. TOML is data-only, so configuration cannot introduce executable Python.
The loader `alive/relevance.py` validates:

- schema version and policy identifier;
- supported-language declarations and default language;
- every declared language file, with matching language code;
- tokenisation strategy and normalisation mode;
- minimum token length, n-gram size and stop resources;
- unknown keys and malformed TOML fail closed with `RelevanceConfigError`.

The policy configuration is loaded by `WebCompanion` at construction. A missing or invalid file
prevents a silent fallback to an English-only decision. The configuration fingerprint is part of
every persisted decision and of the evaluation report.

## Languages and tokenisation

| Language | Strategy | Normalisation | Notes |
|---|---|---|---|
| English (`en`) | word tokens | NFKC + casefold | External stop words, minimum token length 4 |
| Chinese (`zh`) | Han character bigrams | NFKC | No English whitespace assumption; configured stop characters |
| Arabic (`ar`) | word tokens | NFKC + casefold + Arabic diacritic/orthographic normalisation | External stop words, minimum token length 3 |

Language selection is explicit when the owner chooses a language, otherwise script-based:

- a clear Latin, Han or Arabic majority selects that language;
- Han/Arabic text with limited Latin technical terms can still select the non-Latin language;
- materially mixed scripts, a selected language that does not match the text, or an unsupported
  script produce an **uncertain** decision;
- uncertain decisions create no note, no provider reservation and no Meta call;
- the owner can choose a language or explicitly use the bounded “analyse anyway” override. The
  override still passes the existing grant and Governor checks.

A language mismatch is never silently converted into “irrelevant”.

## Decision contract

`no_action` means a supported-language observation shares no configured term with the goal.
`uncertain` means ALIVE cannot make a trustworthy automatic relevance decision. Neither creates a
model call. `analyse` and `recall` retain the ALIVE-05/06 exact-match and usefulness semantics.

## Frozen evaluation

Corpus: `benchmarks/relevance/alive07.jsonl`, 27 cases across development, calibration and
held-out splits, with independent labels. Candidate policy code receives only goal, excerpt and
language; labels are read only by `scripts/relevance07.py`.

Overall results:

| Baseline | Precision | Recall | False abstention | False investigation | Uncertainty | Calls avoided |
|---|---:|---:|---:|---:|---:|---:|
| ALIVE-06 exact overlap | 100.0% | 36.4% | 63.6% | 0.0% | 0.0% | 20 |
| Simple no-stop-word overlap | 100.0% | 72.7% | 27.3% | 0.0% | 0.0% | 16 |
| ALIVE-07 multilingual v2 | 100.0% | 72.7% | 27.3% | 0.0% | 22.2% | 19 |
| Conservative uncertainty | 100.0% | 72.7% | 0.0% | 0.0% | 70.4% | 19 |

ALIVE-07 improves relevant recall over ALIVE-06 from 36.4% to 72.7% on this corpus, while
explicitly marking 22.2% uncertain. The remaining 27.3% false abstention is the important
limitation: relevant cases without literal overlap are still declined. The conservative baseline
has zero false abstention only by sending 70.4% of cases to owner intervention; that is not better
intelligence.

Held-out v2 by language:

| Language | N | Precision | Recall | False abstention | Uncertainty |
|---|---:|---:|---:|---:|---:|
| Arabic | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| English | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| Chinese | 3 | 100.0% | 50.0% | 50.0% | 0.0% |
| Mixed/unsupported | 2 | n/a | n/a | n/a | 100.0% |

Per-language and per-split confusion counts are in the ALIVE-07 archive. This corpus is small,
controlled and not a general multilingual benchmark.

## Experience reuse

ALIVE-05/06 exact-match reuse remains the only demonstrated history mechanism. Existing tests
show:

- identical goal, URL and excerpt after useful feedback -> `recall`, zero new calls;
- changed excerpt -> fresh `analyse`;
- different goal -> fresh `analyse`;
- negative feedback -> no reuse.

ALIVE-07 does not treat lexical similarity as learned generalisation. The evaluation reports that
boundary explicitly instead of claiming that history improved relevance.

## Native qualification

Native Chrome/Meta qualification was not run for ALIVE-07. Ports `8000` and `5173` remain occupied
by the primary development worktree, and no paid inference was authorised. The controlled
FastAPI/SQLite evidence is not native-browser evidence.

## Limits

- Lexical/ngram overlap is not semantic relevance; false abstention remains 27.3% overall and
  50% on Chinese held-out cases.
- Chinese implementation is a character-bigram baseline, not segmentation or semantic parsing.
- Arabic normalisation is deliberately small; it does not model morphology or full orthography.
- Language detection is script-based and can be uncertain for genuinely mixed content.
- The side-panel multilingual UI was not exercised in a new native Chrome journey.
- The corpus is controlled and small; no generalisation claim is made.
- No paid model calls were made by ALIVE-07.
