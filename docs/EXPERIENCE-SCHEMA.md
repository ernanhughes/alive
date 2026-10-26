# Experience schema v1

`ExperienceRecord` is validated before persistence. Each terminal investigation has exactly one experience, enforced by a unique investigation foreign key.

It contains experience/instance/environment/episode IDs, the full versioned prior snapshot and hash, candidate/chosen action, policy ID, deterministic selection probability, action permissions, observed outcome state, decomposed rewards, timestamp, triggering event IDs, actual model configuration, embedding version/use status, evaluation provenance, charged usage, elapsed time and split metadata.

`terminated` means the recorded environment actually terminated. Finishing an investigation does not imply environment termination. `truncated` marks interruption, cancellation or failure before the investigation's intended completion. The current laboratory normally remains ongoing, so successful thought episodes have both flags false; forced-interruption tests verify truncation separately.

Reward components are deliberately narrow:

- Correctness: 1 for a source-verified proposed conclusion, 0 for a contradicted conclusion, otherwise `null`.
- Task progress: 1 only when an analysis memory or controlled draft was actually written; otherwise 0.
- Latency cost: measured elapsed seconds divided by 180, with negative sign.
- Model dollar cost: `null` until a defensible price/billing model is configured.
- Permission violations: 0 for the supported, Governor-enforced effect path; rejected proposals never execute.

These are instrumented experimental signals, not learned rewards, engagement proxies, a claim of user usefulness or a trained MR.Q policy. Unknown rewards stay unknown. Model-generated hypotheses remain distinct from independently checked measurements.

Authenticated interfaces:

| Operation | Endpoint |
| --- | --- |
| Recent experience records | `GET /api/v1/experiences` |
| JSONL export, up to 1,000 records, stable ID cursor | `GET /api/v1/experiences/export?after=ID&limit=N` |
| Replay recorded deterministic source checks | `POST /api/v1/experiences/{id}/replay` |

Export returns `application/x-ndjson` and `X-Next-Cursor`. Replay does not call a model or execute an action; it re-evaluates the recorded environmental facts and returns both recorded and replayed evaluations. Stored prompts/responses permit diagnosis, not a promise that a fresh stochastic inference will reproduce historical text.

For semantic memory, the original `vector(384)` is preserved. `memory_vectors` separates memory ID, model ID, pinned revision and dimension. Actual local MiniLM inference uses attention-mask mean pooling and L2 normalization of ONNX hidden states. Vector and hybrid searches never mix incompatible model/revision spaces; dimension mismatches and non-finite vectors fail explicitly. Hybrid ranking uses reciprocal rank fusion of text and cosine rankings, with top-k limited to 20. SQLite is an explicitly labeled engineering fallback, not proof of pgvector execution.

The history importer accepts only explicitly supplied entries, strips URL query/fragment credentials, excludes sensitive URL paths, redacts common secret patterns, previews before approval, deduplicates and retains attribution. Revocation removes imported memories/vectors and preview content. It does not claim to erase every past derived model summary or diagnostic snapshot; no automatic personal browser history importer is implemented or used in qualification.
