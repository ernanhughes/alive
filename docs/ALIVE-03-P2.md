# ALIVE-03-P2 — Predictive Cognitive Learning, simulator qualification

Question: does shaping a learned state representation with reward and transition prediction
improve cognitive resource allocation beyond a fixed heuristic and matched value-only learning?
An improvement is an experimental possibility, not an acceptance requirement.

## Controlled world

The first-party simulator contains four kinds of synthetic evidence problems: history-sensitive,
reasoning-sensitive, misleading and routine. Hidden truth generates an imperfect initial signal.
Visible state includes belief, uncertainty, noisy evidence-affordance hints, current goal value,
error risk, resource price, budget/time remaining, acquired-evidence flags and four synthetic topic
coordinates. These coordinates are simulator features, not real browser embeddings.
Truth, scenario family, identifiers and oracle answers are excluded from controller input.

Six actions are available: retrieve, investigate, Critic, accept, reject and monitor. The first
three produce new observations with scenario-dependent reliability, change the belief and consume
different resource amounts. A review can repair a misleading prior in this deliberately designed
simulator; this does not establish that the real Meta Critic can do so. Accept/reject terminate
with goal-dependent rewards or error penalties and a decision cost. Monitoring terminates without
intervention or reward. A four-step horizon and deterministic action mask enforce resource,
single-use and termination constraints. Costs are synthetic units, not dollars or Meta tokens.

Each action's noise uses scenario/action keyed random numbers. Shared actions encounter the same
outcome across policy arms, rather than being advantaged by different random-number consumption.
Goals, risks and costs vary across episodes. This first qualification does not model changing
objectives within an episode, open-world beliefs or real semantic memory retrieval.

## Measurement

Primary quality is realized net episodic return: goal reward minus errors and resource costs.
Record factual correctness separately as whether the terminal belief agrees with hidden truth.
Decision correctness uses a privileged full-information terminal reference: monitor if the goal
value cannot cover a decision, otherwise accept/reject according to truth. It is an oracle
diagnostic, not a guarantee that a partially informed agent could know the correct action.
Net return remains the primary measure of decisions under uncertainty.

Record each completed `(state, action, reward, next_state, done)` with its action masks,
observed evidence and cost. During evaluation, save predicted reward and next observable state
**before** stepping the world, then save observation and prediction error. No imagined trajectory
is substituted for actual simulator experience. Complete training experience and held-out
trajectories are persisted, with model checkpoint hashes and a fixed before/after demonstration.

## Learners and predictive ablations

The fixed heuristic uses visible uncertainty, affordances, costs and goal/risk-weighted terminal
utility; it is hashed and never tuned against held-out returns.

The value-only learner is a small original NumPy Double-Q network: 18 inputs, 32 ReLU latent
units, six Q values, discount 0.95, Adam learning rate 0.002, batch size 64, 2,500 updates and
target copies every 100 updates. It trains from a fixed replay collected with a mixture of
random permitted actions and the fixed heuristic. Q-learning uses completed transitions and
bootstrapped next-state values; this is actual offline learning, not prompt routing.

The predictive learner uses the identical network, replay, initialization and minibatch order,
with additional shared-encoder gradients from next-latent and reward prediction, weights 0.2
each. The latent target uses a stop-gradient target encoder. A reward-only ablation removes
the transition gradient. Setting both weights to zero must reproduce value-only training
exactly; a test checks all parameters. Every learner trains identical diagnostic heads, including
a next-observation probe whose gradients do not enter the encoder. Thus probe availability and
head capacity are matched. Predictions support measurement, not online planning.

This borrows the idea of predictive representations supporting model-free value learning from
[Fujimoto et al., *Towards General-Purpose Model-Free Reinforcement Learning*](https://arxiv.org/abs/2501.16142).
It is **MR.Q-inspired, not an MR.Q reproduction**: no upstream code or weights are copied, and
this implementation omits the original algorithm's full architectural/training recipe. The
[official implementation](https://github.com/facebookresearch/MRQ) remains the reference.

## Frozen comparison

Before training/evaluation, `benchmarks/alive03-p2/design.json` hashes simulator, learner,
experiment code and dependency lock; it records exact scenario IDs, replay identity, metric,
hyperparameters and five learner seeds: 11, 29, 47, 71, 97. Splits are 2,000 training,
200 development and 400 test scenarios, balanced across the four families. IDs are split-specific
and disjoint. All arms receive the **same collected transitions**. Only training transitions
can enter gradient updates. All training and checkpoint hashing finish before any test rollout.

Development curves at 0, 250, 1,000 and 2,500 updates show change with experience. The final
checkpoint is fixed in advance; curves do not select a winner, checkpoint or hyperparameter.
The test uses the same 400 unseen scenarios for all models and seeds, with learning disabled.
The fixed heuristic's repeated outcomes across seeds are not independent trials.

Report per-family performance, action frequencies, factual/decision correctness, net return,
cost, prediction error, training change and runtime. Pair return differences by scenario and
learner seed. Use 2,000 hierarchical bootstrap resamples (seed 32027), resampling five training
seeds and common environment IDs while preserving family balance. These intervals condition
on four designed simulator families. They cannot establish transfer to novel worlds or the
live runtime. No claim of improvement is warranted if paired uncertainty includes zero.

The held-out demonstration is always the first test scenario and the first learner seed,
including untrained and trained trajectories. It is not selected for the most favorable result.

## Safety, persistence and reproduction

Learners have no provider client, browser, tool executor or permissions interface. The local
dashboard only reads checksummed completed artifacts. It cannot promote a policy into autonomy.
The existing deterministic Governor continues to control actual runtime permissions and budgets.
No new model role is added. All P1 evidence and frozen source identities remain intact.

```powershell
uv run pytest -q
# Freeze is for the initial design author, once; existing checkouts use verify.
uv run python -m scripts.learning03 freeze
uv run python -m scripts.learning03 verify
uv run python -m scripts.learning03 run
```

Outputs go to ignored `.alive/learning`. The runner refuses to overwrite an existing output
directory or frozen design. Interrupted runs leave evidence and do not automatically replay or
resume. Model checkpoints restore inference; optimizer/replay continuation is not implemented.
After completion, restart the local app and open Cognition → Predictive cognitive learning.
The evidence archive contains the design, models, experience, predictions, results and tests.
P2 is local unless separately authorized for publication. There are zero paid calls in this
simulator qualification; real Meta or browser transfer remains future work.
