# OpenCode ALIVE-08 handoff - Learning From Experience

## Repository and commits

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Starting `origin/main` | `ef99a827aec2f335952f9370cae4f57fb5db8942` (ALIVE-07 merged) |
| Branch | `opencode/alive-08-experience-learning` |
| Feature/protocol commit | `50f312a` |
| Evidence/handoff commit | the final commit containing this document |
| PR | to be created after push; review-only, not auto-merged |

## What was implemented

A self-contained controlled experience-learning experiment:

- `alive/experience_lab.py` - simulator, hidden source dynamics, controlled action envelope,
  stateless/fixed/flat/hierarchical/history baselines, paired metrics and cluster bootstrap.
- `scripts/alive08.py` - frozen corpus generation, calibration, held-out evaluation and archive
  generation.
- `benchmarks/alive08/` - frozen protocol, environment, seeds and four corpora.
- `tests/test_experience_lab.py` - causal order, hidden-field exclusion, utility, Governor,
  learning, bootstrap, persistence and determinism tests.
- `docs/ALIVE-08.md` - formal experiment report.
- `archives/ALIVE-08/` - evidence and reproducibility archive.

No migration, browser controller, new cognitive role, neural learner, provider change or second
Governor was added.

## Exact environment

Each episode has one observation and one action:

- Observation: random source ID, cadence hint (hourly/daily/weekly/static), claim-age bucket,
  random claim value, fixed monitoring goal, permitted actions.
- Actions: `retrieve` (cost 0.20) or `monitor` (no cost; bounded no-action choice).
- Hidden: source class, source-specific change probability, current change boolean and monitor
  feedback-noise bit.
- Reward: retrieve changed +0.80; retrieve unchanged -0.20; monitor changed -1.00; monitor
  unchanged 0.00.
- Source classes: stable p=0.04, episodic p=0.22, volatile p=0.45, novel p=0.65 (evaluation only).
- Source offsets: N(0, 0.08), clipped. Claim age multiplies change probability by
  0.5/0.8/1.2/1.8.
- Monitor feedback is 10% noisy; retrieval reveals the true change.
- The environment computes utility; no model self-assessment is used.

## Experimental protocol

- Seeds: 17, 23, 31, 43, 59.
- Development: 200 episodes; calibration: 500; training: 1,000; evaluation: 1,500.
- Evaluation: 750 seen sources, 500 unseen identities from seen classes, 250 novel-class episodes.
- Training and evaluation source pools are separate except intentionally shared seen identities.
- Calibration selected `min_source_observations=2` and `source_margin=0.10`.
- Protocol and corpus hashes were frozen before held-out evaluation.
- Candidate policy receives only `observation()`; labels and hidden outcomes are read only by the
  evaluator.
- Primary comparison: ALIVE hierarchical vs flat contextual empirical learner, mean held-out
  utility, paired 95% cluster bootstrap by source/seed.
- Advantage threshold: CI lower bound > 0 and mean difference >= 0.01.

## Baselines

| Arm | Purpose |
|---|---|
| `stateless_prior` | Fixed cadence prior, no history |
| `fixed_heuristic` | Frozen age+cadence rule, no learning |
| `flat_empirical` | Simple cadence/age outcome table; critical control |
| `alive_hierarchical` | Existing empirical policy with source-specific/class/global backoff |
| `alive_no_history` | Same ALIVE policy without training experience |
| `alive_shuffled` | Same update count with shuffled rewards |
| `history_proxy_not_meta` | Offline retrieval proxy, explicitly not a Meta model |
| `alive_online_ablation` | Secondary online-update ablation |

A paid Meta-history baseline was not run; it remains pending owner authorisation. No provider
credentials or model pins were changed.

## Results

Primary comparison:

| Comparison | Mean difference | 95% CI | Episodes |
|---|---:|---|---:|
| ALIVE hierarchical - flat empirical | **-0.0248** | **[-0.0442, -0.0090]** | 1,500 |

The primary advantage criterion **was not met**. The flat learner achieved mean utility 0.0723;
ALIVE hierarchical achieved 0.0475. The result is `PASS_NO_ADVANTAGE_DEMONSTRATED` for the primary
research claim, with engineering qualification passing.

Experience still mattered relative to no/shuffled history:

| Comparison | Difference | 95% CI |
|---|---:|---|
| ALIVE vs no history | +0.3221 | [0.2576, 0.3875] |
| ALIVE vs shuffled history | +0.1419 | [0.1005, 0.1843] |
| ALIVE vs stateless prior | +0.0321 | [0.0045, 0.0595] |
| ALIVE vs fixed heuristic | +0.0683 | [0.0358, 0.1030] |
| ALIVE vs history proxy | +0.0367 | [0.0086, 0.0654] |

Per-seed ALIVE vs flat: seed 17 tie (0.1400), 23 -0.0473, 31 -0.0186, 43 -0.0707, 59 +0.0127.
ALIVE wins one seed, ties one and loses three.

By source status, flat beats ALIVE on seen (0.0181 vs 0.0077), unseen (0.0180 vs -0.0052) and
novel (0.3432 vs 0.2720). The online ablation reaches 0.0711, close to flat but below it.

## Validity and resources

All validity checks passed:

- protocol frozen;
- selected parameters present;
- corpus hashes match;
- observations exclude hidden fields;
- all arms use identical scenarios;
- zero provider calls/tokens;
- all actions passed the controlled action envelope.

Provider calls: **0**. Tokens: **0**. Estimated provider cost: **$0.000000**.
Mean simulator decision latency: **0.108 ms**.

## Tests executed

| Check | Result |
|---|---|
| Backend suite | **121 passed** |
| Experience-lab focused | **11 passed** |
| Frontend suite | **7 passed** |
| Production build | Passed |
| Ruff check/format | Passed |
| Extension JavaScript syntax | Passed |
| Prior archives | All manifests unchanged |

## Evidence

`archives/ALIVE-08/` contains protocol, environment, seeds, all four frozen corpora, 12,000
arm/episode transitions, paired results, per-seed/per-class/per-status metrics, ablations,
counterfactual examples, restart proof, results report, SVG chart, validation transcripts and a
SHA-256 manifest (33 payloads).

The counterfactual example is a seen stable source where ALIVE retrieves and loses -0.20 while
no-history monitors for 0.00. It is a preserved failure case, not a favourable example.

Restart proof is a simulator policy JSON round-trip with identical decisions on 20 scenarios. It is
not a live process restart; live restart is covered by earlier ALIVE-04/05 tests.

## Native qualification

**Not run.** Ports `8000` and `5173` were occupied by the primary worktree. No process was stopped,
no native Chrome session was opened against it, and no Meta call was made. This experiment is
synthetic simulator evidence only.

## Integration requirements

- New module `alive/experience_lab.py`, script `scripts/alive08.py`, benchmark data and archive.
- No migration, runtime schema change or provider dependency.
- No dashboard UI change; the static report and SVG are the evaluation view. This was a deliberate
  scope decision to prioritise the experiment over a second UI.
- Existing ALIVE-01 through ALIVE-07 archives are untouched.

## Limitations

- Synthetic environment and hand-designed source classes/rewards.
- Cadence and claim age are informative, favouring the flat table.
- Only five seeds and 1,500 held-out episodes.
- The ALIVE arm is a small adapter around `living_policy`, not the live Living/WebCompanion runtime.
- No paid Meta/LLM-with-history comparison yet.
- No native browser qualification.
- Source-specific estimates overfit despite the confidence margin; online updates help but do not
  exceed the flat learner.

## Recommended next stage

1. Review and merge this PR only if the negative primary result and protocol are acceptable.
2. Run native qualification on isolated free ports with owner authorisation.
3. Prepare a separately authorised Meta comparison proposal; do not call a synthetic baseline Meta.
4. Before another learner milestone, address source-level variance/shrinkage and run a new frozen
   held-out experiment. Do not add a larger model as a substitute for a better experiment.

## Reproduction commands

```powershell
uv run python -m scripts.alive08 generate
uv run python -m scripts.alive08 calibrate
uv run python -m scripts.alive08 evaluate
uv run pytest -q
uv run ruff check alive migrations scripts tests
npm test --prefix dashboard
npm run build --prefix dashboard
```

The evaluation command refuses a second held-out run once `results.json` exists.
