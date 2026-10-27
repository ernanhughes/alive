# OpenCode ALIVE-07 handoff - Multilingual-ready relevance

## 1. What changed

ALIVE-07 keeps the ALIVE-06 decision contract and replaces its hard-coded English relevance
resources with a validated external configuration and a versioned successor policy.

- Language stop words, stop characters, tokenisation strategy, normalisation and minimum token
  lengths now live under `config/relevance/`.
- `alive/relevance.py` loads and validates the configuration and implements script detection,
  tokenisation, normalisation and deterministic relevance.
- `alive/web_experience.py` uses policy v2, persists policy/config/language provenance, and returns
  `uncertain` for mixed, mismatched or unsupported scripts.
- The analysis endpoint independently enforces both `no_action` and uncertain-language decisions.
  Uncertain analysis requires an explicit owner override; it still passes the grant and Governor.
- The extension panel exposes an Auto/English/中文/العربية selector and explains relevance,
  matched terms, uncertainty and no-action decisions.
- `scripts/relevance07.py` evaluates v1, a simple no-stop-word baseline, v2 and a conservative
  uncertainty baseline on a frozen 27-case corpus.

No migration, new learner, new role, new store or new Governor was added.

## 2. Why language resources are external

The ALIVE-06 stop-word list and English token rules were embedded in Python. That made a language
policy change a code change and encouraged treating English as the default for every observation.

The new configuration is data-only UTF-8 TOML. It cannot introduce executable Python. Unknown
keys, malformed TOML, missing declared language files, unsupported strategies and invalid
normalisations fail closed with `RelevanceConfigError`. Missing resources never silently mark an
observation irrelevant.

## 3. Policy versions

| Policy | Status |
|---|---|
| `deterministic-goal-excerpt-overlap-v1` | Historical ALIVE-06 policy; archived decisions unchanged |
| `deterministic-multilingual-relevance-v2` | Current policy |

Every v2 decision records `relevance_policy`, `config_fingerprint`, requested language, resolved
language, language source, matched terms and uncertainty reason. The v1 archive is not rewritten.

## 4. Supported languages

- English (`en`): external stop words, word tokens, minimum length 4.
- Chinese (`zh`): Han character bigrams, configured stop characters, no English whitespace
  assumption.
- Arabic (`ar`): word tokens, NFKC + casefold, diacritic removal and basic orthographic
  normalisation, external stop words.

The implementation is a deterministic baseline, not semantic understanding, segmentation or
morphology.

## 5. Tokenisation and normalisation

| Language | Strategy | Normalisation |
|---|---|---|
| en | words via `[a-z0-9]+` | NFKC + casefold |
| zh | Han runs -> character bigrams | NFKC |
| ar | Arabic word runs | NFKC + casefold + diacritics + alef/ya/ta-marbuta/tatweel normalisation |

Auto-detection is script-based. Clear Latin/Han/Arabic majorities select a language. Materially
mixed scripts, unsupported scripts and explicit-language/script mismatches produce `uncertain`.
Language selection can be explicit in the request; Auto remains the default.

## 6. Configuration loading and validation

Files:

```
config/relevance/policy.toml
config/relevance/languages/en.toml
config/relevance/languages/zh.toml
config/relevance/languages/ar.toml
```

`load_relevance_config()` validates schema version, policy identifier, supported language list,
default language, every declared language file, strategy, normalisation, token length, n-gram size
and stop resources. It computes a SHA-256 fingerprint of the policy and language tables. The
fingerprint for the evaluated files is
`dfba62bc4c5de72c9073162d66b8629e3edaa88e77af4b6a2bf220480c6dc205`.

The `WebCompanion` loads configuration at construction. Invalid configuration fails the app rather
than silently falling back.

## 7. Evaluation methodology

Frozen corpus: `benchmarks/relevance/alive07.jsonl`.

- 27 cases: development, calibration and held-out splits.
- English, Chinese, Arabic, mixed-script and unsupported-script cases.
- Relevant, irrelevant and independently labelled uncertain cases.
- Candidate policy receives goal, excerpt and selected language only.
- Labels are read only by `scripts/relevance07.py`.
- Baselines: ALIVE-06 exact overlap, simple no-stop-word overlap, ALIVE-07 v2, conservative
  uncertainty.
- Metrics: precision, recall, false-abstention rate, false-investigation rate, uncertainty rate,
  calls avoided and owner intervention, overall and per language/split.
- Relevant recall counts uncertain decisions as not recalled, preventing a conservative policy
  from hiding behind abstention.

## 8. Baseline results

| Baseline | Precision | Recall | False abstention | False investigation | Uncertainty | Calls avoided |
|---|---:|---:|---:|---:|---:|---:|
| ALIVE-06 exact overlap | 100.0% | 36.4% | 63.6% | 0.0% | 0.0% | 20 |
| Simple no-stop-word overlap | 100.0% | 72.7% | 27.3% | 0.0% | 0.0% | 16 |
| ALIVE-07 v2 | 100.0% | 72.7% | 27.3% | 0.0% | 22.2% | 19 |
| Conservative uncertainty | 100.0% | 72.7% | 0.0% | 0.0% | 70.4% | 19 |

Held-out v2 by language:

| Language | N | Precision | Recall | False abstention | Uncertainty |
|---|---:|---:|---:|---:|---:|
| Arabic | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| English | 3 | 100.0% | 100.0% | 0.0% | 0.0% |
| Chinese | 3 | 100.0% | 50.0% | 50.0% | 0.0% |
| Mixed/unsupported | 2 | n/a | n/a | n/a | 100.0% |

## 9. False abstention

The central limitation is **27.3% overall false abstention** and **50% on held-out Chinese**.
Relevant cases without literal content-token or character-bigram overlap are still declined.
The conservative baseline reaches zero false abstention only by sending 70.4% of all cases to
owner intervention. That is explicit uncertainty, not improved relevance.

## 10. Native qualification status

Native Chrome/Meta qualification was **not run**. Standard ports `8000` and `5173` were occupied by
the primary development worktree. ALIVE-07 did not stop, restart or interact with those processes
and did not make a Meta call. Evidence is controlled FastAPI/SQLite plus a synthetic provider.

## 11. Limitations and unsupported scenarios

- Lexical/ngram overlap is not semantic relevance.
- Chinese is a bigram baseline, not word segmentation; held-out recall is 50%.
- Arabic normalisation is small and not morphological.
- Script detection can be uncertain on mixed content; that is represented explicitly.
- The side-panel language selector is covered by backend tests and syntax checks, not a new native
  Playwright side-panel run.
- The corpus is small and controlled; no general multilingual performance claim is made.
- Exact-match history reuse remains the only demonstrated experience mechanism; no approximate
  history or learned generalisation is claimed.
- No ALIVE-06 or earlier archive was modified.

## 12. Recommended next stage

1. Review and merge this PR if the v2 policy and uncertainty semantics are acceptable.
2. When free isolated ports and owner authorization are available, run a native Chrome/Meta
   qualification against the same corpus subset and record native versus controlled evidence
   separately.
3. Then run the planned held-out comparison between an agent with relevant experience and an agent
   without it. Do not treat a changed decision as an improved decision without independent outcome
   labels.

## File references

- `alive/relevance.py`
- `alive/web_experience.py`
- `config/relevance/`
- `benchmarks/relevance/alive07.jsonl`
- `scripts/relevance07.py`
- `tests/test_relevance.py`
- `tests/test_relevance_evaluation.py`
- `tests/test_web_experience.py`
- `docs/ALIVE-07.md`
- `archives/ALIVE-07/`

## Commands

```powershell
uv run pytest -q
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
uv run python -m scripts.relevance07
npm test --prefix dashboard
npm run build --prefix dashboard
node --check extension/background.js
node --check extension/panel.js
```

## Commits

- Starting `origin/main`: `70e2639b0136da9c675c68a24598e96321d3e28a`.
- Feature/config commit: `369055d`.
- Evidence/handoff commit: the final commit containing this document.
- Branch: `opencode/alive-07-multilingual-relevance`.

## Branch and PR

- Branch pushed: `opencode/alive-07-multilingual-relevance`.
- PR: to be created after push; review-only, not auto-merged.
- Target: `main`.

## Integration notes

- Built directly on merged ALIVE-06 main; no dependency on an uncommitted branch.
- No migration or data schema change.
- Extension panel/background and `alive/web_experience.py` are the main integration points.
- The config directory is new and additive.
- Historical decisions remain readable; v2 adds fields rather than rewriting old rows.
