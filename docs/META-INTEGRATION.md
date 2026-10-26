# Meta Model API integration

ALIVE uses official [Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions), [native JSON-schema output](https://dev.meta.ai/docs/structured-output), [reasoning controls](https://dev.meta.ai/docs/reasoning) and model discovery at `GET /v1/models`.

Backend configuration:

```dotenv
ALIVE_META_BASE_URL=https://api.meta.ai/v1
ALIVE_META_MODEL=muse-spark-1.3
ALIVE_META_API_KEY=YOUR_LOCAL_KEY
ALIVE_META_TIMEOUT=30
ALIVE_META_MAX_OUTPUT=1536
ALIVE_ROLE_MODELS={}
```

`MODEL_API_KEY` and `META_API_KEY` are supported aliases. Credentials stay in ignored `.env` or the backend environment; they are never sent to the dashboard or extension. The legacy `ALIVE_META_URL` can override the complete chat endpoint. `muse-spark-1.3` was confirmed by live authenticated discovery, not guessed from a catalog file.

Calls use developer/user role separation, `response_format=json_schema`, `reasoning_effort=minimal`, `max_completion_tokens`, a request correlation ID and a timeout. There are zero implicit retries. Pydantic and reference validation remain mandatory even with native constrained output. HTTP authentication, access, rate-limit, network, timeout, truncation and malformed-response errors are classified without persisting raw credential-bearing upstream diagnostics. Usage and latency are recorded per invocation. Private reasoning is not exposed.

## Actual verification

A real smoke call returned a validated summary object from `muse-spark-1.3`: **92 prompt + 604 completion = 696 tokens**, including 576 reported reasoning tokens, in approximately **3.526 seconds**. The first 128-token attempt was truncated; this informed an adequate bounded output cap and was not called a passing result. That failed attempt's full billable usage was not retained; it is not silently included in later measured totals.

The First Autonomous Thought demonstration then ran real Observer/Proposer/Critic calls for relevant and contradictory browser changes, with zero calls for noise. Its complete invocation records and actual usage are in PostgreSQL and `.alive/first-thought.json`. The independently opted-in live benchmark uses the same pinned model across A/B/C and no-Critic arms, and records actual prompts/outputs/usage in its local report/ledger. See ALIVE-02-ACCEPTANCE for final qualification results.

To probe access without inference: authenticated `POST /api/v1/providers/meta/probe`. To run the owned restart demonstration, stop the ordinary development servers, then `uv run python -m scripts.first_thought --provider meta`. To run the explicitly opted-in bounded benchmark, see the README command. Never infer model quality from the smoke response or three synthetic cases.

No inference occurs when credentials are absent: Meta mode refuses to start unless model access is confirmed. Mock mode remains available and is explicitly labeled as controlled role fixtures. Dollar costs remain `null` because no billing rates or invoice data were configured; token expenditure is measured, not translated into an invented dollar amount.
