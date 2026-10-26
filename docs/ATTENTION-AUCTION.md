# Attention auction v1

All scores are deterministic. The policy tokenizes visible content and authorised goals/topics, removes common workflow words, and normalizes components to 0–1. Generic words such as “observation” cannot make a quiet habitat relevant. An explicitly accepted commitment receives full relevance, so a meaningful existing obligation need not share the default research vocabulary.

```
score = clip(0.25 relevance + 0.20 urgency + 0.25 benefit
             + 0.20 novelty + 0.10 uncertainty - 0.20 cost, 0, 1)
```

Relevance is the matched topic-term count divided by two and capped at one. Benefit initially equals relevance; estimated cost is 0.2. Novelty uses token-set change and raises the novelty floor to 0.8 when a structured claim's value changes. Uncertainty is 0.6 for parsed claims and 0.3 otherwise. Ordinary urgency is 0.2; accepted commitments start at 0.3 and rise with age up to one. Every bid records these inputs, matched terms and the formula.

Default eligibility requires score ≥0.45 **and positive relevance**. Below threshold is `NO ACTION WARRANTED`, with no model call or cognitive goal. Fingerprints combine instance, environment URL and canonical content; structured claim text removes unrelated local-draft changes from the trigger. Identical observations do not start duplicate investigations.

Candidates normally rank by descending score, then oldest timestamp, then stable ID. Accepted commitments receive explicit relevance and aging urgency. After 60 seconds they enter a deterministic oldest-first priority lane, without overriding budgets; a stream of higher-score fresh observations cannot indefinitely overtake them. Cancelled commitments are rejected before execution. Ordinary bids expire after five minutes; accepted commitments remain pending until cancelled or served. The queue holds at most 128; overflow is labeled backpressure. The event scanner reads at most 100 persisted events per tick.

The auction selects at most one investigation. It checks both session and persistent experimental ceilings, including outstanding reservations, then reserves the **entire** investigation envelope before creating the active goal/worker. Considered IDs, selection, rejected bids and allocation are persisted as events. Pausing/stopping cancels queued work and releases unused reservations from cancelled investigations.

## Hard limits

Default limits: four model calls, 50,000 charged tokens, three scoped tool operations, 90 seconds, depth one, concurrency one, zero retries. Each request has its own input/output envelope and native output cap. Defaults permit 30 calls/200,000 tokens per session and 100 calls/500,000 tokens for the persistent runtime experiment. Configuration has absolute validated ceilings and cannot change while autonomy is running.

Each request reserves serialized UTF-8 input/schema bytes plus 1,024 overhead and its full output cap. Reported actual usage settles a successful request; absent/failed/unknown usage retains the pessimistic reservation. A request that cannot fit is rejected before inference. An unexpected provider overrun stops further work and remains charged; ALIVE is not an account-wide provider billing quota. Output limits include Meta's private reasoning tokens. The app never spends a budget by sending only a notification about exhaustion.

Session reset preserves the experimental counters. Backend restart preserves both charged usage and reservations; interrupted work is truncated and settled without replay. The standalone benchmark uses a separate persistent ledger with its own explicit experiment cap and paid opt-in. These experiment scopes are not combined into a provider-account spending limit.
