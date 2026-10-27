# ALIVE-03-P3 — What makes prediction useful?

One focused diagnostic, not an architecture expansion. P2 is accepted as a simulator
qualification with limitations; its code, design, checkpoints and negative result remain intact.
P2's complete mean returns were heuristic 0.033623, value-only 0.083224, predictive 0.065783
and reward-only ablation 0.072382. None of its predeclared return intervals excluded zero.

## Design frozen before evaluation

The diagnostic constructs pairs of synthetic browser-like situations with **identical current
observations and four-dimensional synthetic embeddings**. Their recent histories differ:
one contains a corroboration event; the other contains a source-replacement event. A history
feature summarizes that event. It is not hidden truth and is not a learned recurrent memory.
These are synthetic inputs, not actual browser embeddings or live browser interaction.

In corroborated worlds the displayed claim is correct. In replaced-source worlds it has changed
with probability 0.75, unknown to the learner before collecting evidence. Retrieving reveals the
current truth and costs a visible resource amount drawn in [0.1, 0.5). Monitoring skips retrieval.
Both actions advance to a terminal accept/reject decision, rewarded +1 if correct and -1 otherwise.
A deterministic mask permits only these actions in their respective phases.

This gives retrieval a negative expected value in corroborated worlds and positive expected
value in replaced-source worlds. The optimal no-retrieval decision in a replaced-source world
can reverse the old claim using the known 0.75 change probability. Retrieval's incremental
expected value over that best decision is **0.5 minus cost**, not 1.5 minus cost. The latter
applies only to a continuation that blindly follows the displayed claim. Both action contrasts
are labeled separately, and realized intervention outcomes are retained.

## Five questions

1. **State quality:** count exact current-observation collisions across paired histories. Compare
   identical learners with feature 12 masked versus exposed. Rich history changes only that slot.
2. **Action consequences:** clone each frozen world, retrieve or monitor, and use a fixed
   follow-belief terminal continuation. Record reward contrasts and the generative expected-value
   reference. Cloned outcomes are controlled simulator interventions, not independent trials.
3. **Prediction:** evaluate every learner on the same balanced held-out transition probes.
   Report full observable-state MSE, first-step belief MSE and reward MSE. Compare a train-only
   empirical conditional-mean predictor that copies known unchanged fields and phase/resource
   updates. This simple baseline has explicit simulator structure, not access to hidden truth.
   Unlike P2's on-policy errors, these MSEs share an identical probe distribution.
4. **Decision quality:** compare paired realized returns and retrieval rates by history context.
   Prediction loss can shape the encoder; policies still act via learned Q values, not planning.
5. **Sample efficiency:** use nested replay sizes of 384, 1,536 and 6,144 transitions (32, 128
   and 512 paired training situations). Hold optimization at 1,500 updates of 64 transitions.
   Smaller datasets are revisited more often; this is unique-data efficiency at fixed compute,
   not a separate optimization-budget study.

## Matched learners and freeze

Reuse the **unchanged P2 Controller**: 18 inputs, 32 hidden units, Double-Q, Adam 0.002,
discount 0.95 and target copies every 100 updates. Value-only has zero predictive encoder
weights; predictive uses 0.2 latent and 0.2 reward weights, inherited from P2. The two views,
three replay sizes, two learners and five seeds form one predeclared factorial diagnostic
(60 small networks). No new model role, paid call, hyperparameter sweep, checkpoint selection
or live-action authority is added. No separate tuning phase is performed.

Replay enumerates six balanced completed transitions per world: both first actions, followed
by each terminal choice. Nested prefixes contain complete history pairs. Policies in a cell
receive identical replay, initialization and minibatch order. Current-only versus rich views
preserve rewards, actions, next-action masks and scenario identity; only the history slot changes.
Train/test scenario IDs differ by namespace. Every model trains and has its checkpoint hashed
before held-out prediction or policy evaluation begins.

Held-out evaluation uses **128 paired histories / 256 distinct worlds**, reused across five
training seeds. Pair members share visible features and exogenous randomness. Intervals resample
learner seeds and whole history pairs (both members together), using 2,000 bootstrap resamples
with seed 33027. The six predictor-versus-value comparisons and six history-versus-current
comparisons are exploratory; intervals are not adjusted for multiplicity. Do not select a
favorable budget point and claim general superiority.

`benchmarks/alive03-p3/design.json` binds source hashes, exact held-out IDs, replay identity,
budgets, seeds and analysis choices. The original P1/P2 freezes must continue to verify.

## Interpretation limits and next step

The experiment can expose state aliasing and test the incremental value of the existing
predictive regularizer. It does not show that prediction is necessary: a value-only policy
with history can learn the same action distinction. History is supplied as a summary feature,
not learned from a browser event sequence. The environment is hand-designed and short-horizon.
The observable predictor is a detached probe of the encoder, not the optimized next-latent
target itself; better latent loss alone would not prove useful control. Both reward and latent
encoder weights change together here; P2's separate reward-only ablation remains archived.

Preserve all outcomes and stop after this diagnostic. The next major product work should make
the existing intelligence visible: observe a consented page, predict a bounded consequence,
choose an action, obtain actual feedback, and display how experience changes a later choice.
Start with shadow recommendations and deterministic Governor checks. Use a fixed first-episode
demonstration and an unchanged baseline; do not claim simulator transfer before measuring it.

```powershell
uv run pytest -q
uv run python -m scripts.diagnostic03 freeze  # author once; future checkouts use verify
uv run python -m scripts.diagnostic03 verify
uv run python -m scripts.diagnostic03 run
```

Outputs are persisted under ignored `.alive/prediction-diagnostic`. Frozen designs and existing
outputs refuse replacement. Model files restore inference, not training continuation. No silent
reruns or follow-up learner optimization are part of this milestone. P2/P3 remain local unless
separately authorized for publication.
