# ALIVE-04 — Living Experience: PASS_WITH_LIMITATIONS

**ALIVE changed a permitted browser action after observed feedback, retained the learned policy
across a backend restart, and reused the relevant prior experience in a matched later situation.**
The action change is deterministic and precedes Meta synthesis; it is not a different answer
selected from model sampling. This is a controlled live integration result, not broad autonomy.

## Integration and publication

P2 and P3 histories/evidence are published at
[`f257cbc`](https://github.com/ernanhughes/alive/tree/codex/alive-03-p2-predictive-learning) and
[`930fb23`](https://github.com/ernanhughes/alive/tree/codex/alive-03-p3-prediction-diagnostic).
Their owner acceptance was PASS_WITH_LIMITATIONS. Baseline checks passed before integration:
76 backend, four frontend and five browser tests plus the production build. All prior evidence
hashes verified. Local integration `3719cf4` combines latest origin/main `a060a6c` with those
branches, without changing main. Its file tree matches the tested P3 baseline.

ALIVE-04 branch: `codex/alive-04-living-experience`. Native Chrome/Meta implementation commit:
`c8c9feb60f4ebb8fcefb0ce1a69791615ba8347c`. Final UI/evidence tooling commit: `62be48adcc63794ceb65263cfccbf84d0b662cc5`.
The following archive commit contains evidence. No ALIVE-04 push, deployment or main change.
After commits, only the pre-existing `models.txt` is untracked.

## The completed journey

| Encounter | Prior relevant experiences | Action | Meta conclusion | Observed utility |
|---|---:|---|---|---:|
| First | 0 | Monitor | Safe abstention without current evidence | -0.50 |
| Related, after restart | 1 | Retrieve evidence | Verified 20, contradicting claimed 32 | +0.85 |

Both Chrome observations project to feature hash `3c6a7cfbeac50f515a66332e4ab09fb55ac2afa6df204cab5079fff5078a2568`. The page claim
and source-replacement cue match; episode/session identifiers are excluded from the state used
by the policy. The original snapshot still chooses **monitor** for the second state. The updated
policy chooses **retrieve**, using the first completed transition as its recalled experience.
First after-policy hash and second before-policy hash both equal `d7c176c18528c46f82c29a233c9bc0f0fd057090e91468f743f34f5f0e2714a2`.

Every action choice was recorded before the corresponding Meta request. Meta did not choose
the action. Its existing Proposer role supplied real, structured read-only reasoning from
visible browser evidence. The first input had no current instrument source; hidden instrument
and feedback text were excluded. The second source was extracted after an allowed DOM click.
Published end-of-episode feedback was read from Chrome after reasoning, not invented by a model.

The transition, feedback, policy update, generic Memory record and journey progress commit in
one PostgreSQL transaction. Two closed native Chrome sessions, two persisted Memory records,
two completed transitions, the policy and relevant event journal are captured in
`live/database-evidence.json`. Database dialect: **postgresql**.

## Restart and causal checks

There is a recorded `alive.started` event between the two model calls, as well as the explicit
restart proof. Identity digest, first transition, policy hash and one-call ledger persisted.
No worker or extra model call auto-resumed. The owner explicitly advanced the second encounter.
Native inference/browser code hashes match on both sides of the restart and match the preserved
implementation commit. A post-qualification classification patch separates factual support
from conclusion acceptance in the unobserved correct-fact/`investigate` edge case from P1.
The recorded native outcomes were replay-checked against that release assessment: both original
classifications, rewards and policy updates remain unchanged. No paid run was repeated and no
policy was reset. Native and release identities are preserved separately.

The causal counterfactual is the original deterministic action policy on the actual second
feature state. It is not an independently executed baseline Meta trial. A stronger fixed
history-aware rule would retrieve from the first encounter; this demonstration does not claim
to outperform that rule. There is no branch keyed on episode number that changes the action.

## Actual usage and limits

- Native Meta model: **muse-spark-1.3**, existing Proposer role, no mandatory Critic.
- **2 real model calls**, **2,250 reported tokens**.
- **$0.0049395 estimated**.
- Conservative application charge: $0.004940.
- Journey ceilings: two calls, 40,000 tokens, six browser operations, estimated $0.15.
- Browser operations: **5**.
  First observe/feedback; then observe/retrieve/feedback.
- No automatic model retries, model errors or unknown usage in this live journey.

Prices use [Meta's published rate card](https://dev.meta.ai/docs/pricing-rate-limits), checked
27 October 2026. Dollar figures are estimates, not confirmed provider billing. Utility is a
separate synthetic task reward, not money. Reasoning tokens are included in completion usage.

## Governor and acceptance checks

The grant covers only the controlled local habitat's public observations and allowed clicks.
Arbitrary destinations, selectors, external actions and model-requested tools are not accepted.
Per-request, episode, journey, session and experiment budget checks precede model inference.
The native Browser checks origins and permitted DOM operations; the Governor checks tool limits.
Budget/configuration changes and concurrent autonomous/experimental workers are blocked while
living work is active. Stop revokes permission and conservatively settles interrupted usage.

Tests: **83 backend** (76 prior plus seven living tests), **four frontend**, **six browser E2E**;
production build and Ruff checks pass. The final living-only browser check also passes after
the visual polish. Coverage includes missing/out-of-scope grants, zero budget, stop/cancellation,
unknown-call settlement, no paid replay, fixture/live context isolation, restart persistence,
matched-state counterfactuals and the actual controlled DOM visibility/clicks. Unit credentials
are explicitly empty so tests cannot inherit the owner's provider key.

## What this proves, and its limits

The complete observe → remember → predict → choose → act → reason → feedback → learn loop is
visible in the Living tab. Feedback affects the next action and remains durable across restart.
After encounter two, stored action means are monitor -0.50 (one outcome) and retrieve +0.85
(one outcome). The UI shows those counts and small-sample uncertainty, including unknown priors.

This is a tiny empirical outcome-mean policy with a zero prior and lower-resource tie-break.
The first negative outcome causes exploration of an untried option. It is not deep RL, MR.Q,
general self-improvement, calibrated prediction confidence or proof of held-out generalization.
No predictive representation learner is a runtime dependency.

The two encounters deliberately reuse an inspectable synthetic fixture. The source-replacement
cue is explicitly published in the DOM, not inferred from unrestricted browser history or real
semantic embeddings. Memory retrieval is exact context matching, not open-ended semantic recall.
The synthetic feedback contract rewards current verification and penalizes unresolved goals.
Safe factual abstention in encounter one is preserved; it is not relabeled as a wrong fact.

Controlled fixtures and real-Meta contexts are separated so mock rewards do not train live
action values. New journeys reuse existing policies; there is no hidden reset for a favorable
demo. Warm journeys can show no new action change, and the UI reports that. Real-browser use
outside this controlled habitat needs additional implementation and evaluation.

## Evidence

`live/` contains both encounter snapshots, complete redacted model ledger, qualification plan,
restart proof, PostgreSQL/browser/memory/event evidence. `acceptance.png` and `encounters.png`
show the verified UI. `validation/` holds current and baseline test/build transcripts.
Prior qualification archives are byte-for-byte intact; their checksum results are retained.
Runtime identity is represented by digest where applicable; credentials and personal browsing
data are excluded. `manifest.json` hashes every archive payload except itself.
