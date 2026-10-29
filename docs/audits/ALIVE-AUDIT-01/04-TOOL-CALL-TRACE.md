# ALIVE-AUDIT-01 — Model and tool-call trace

Baseline: `1b6da07b856e497b3a44a9e1b9794e94adff55ab`. No paid inference or real provider transport was used.

## Ownership boundary

The commissioning report conflates two possible interfaces that must be tested separately:

* External contributor/agent tooling generates tool-call arguments and invokes editor/shell tools. No raw failing tool schema, generated argument object, serialized dispatch, tool execution log, or provider-side record was supplied for Meta's reported dropped parameters. Its failure cannot be located or attributed from the quotation alone.
* ALIVE sends native structured chat-completion requests and validates JSON outputs. It does **not** expose a general tool-call names/arguments/ID execution protocol through MetaProvider. Tool-like strings nested in ALIVE request data survive tested JSON serialization, but that is not proof about an external agent tool interface.

PiRunner uses RPC prompt/abort IDs (`alive-task`) and expressly disables tools, skills, extensions, MCP, templates and context discovery. The prompt contains an explicitly submitted objective. Its stdout events are parsed for text and completion; they are not arbitrary executable tool instructions. Real Pi RPC execution was NOT EXECUTED in this audit.

## Migrated cognition path (PR53)

| Boundary | Data / authority owner | Verification |
|---|---|---|
| API caller / configuration | Authenticated start; validated `AutonomyCommand`; model discovery before Meta start | Source and existing tests; empty persisted-token defect is upstream of all authority checks |
| Scheduling/admission | `Cognition.auction`: budget reservation; one investigation; persisted observation/goal identity | Selected source review, cognition/recovery tests |
| Request construction | `Cognition.call_role` at line672: `role_prompt`, context, `RoleOutput.model_json_schema`, role-specific model | Reserve counts serialized input bytes + margin + output cap before dispatch; config ceiling check before invocation |
| Durable record | ModelInvocation ID/provider/model/input/reserved_tokens and run usage | Written before transport; correlation equals invocation ID; cancellation gap at transaction exit is F-002 |
| Factory | `gateway_for(settings, "cognition.role")` | Unknown factory operation raises KeyError; main does not recheck request operation (F-006) |
| Gateway | `DirectMetaGateway.structured(StructuredRequest)` | Forwards instructions/data/schema/model/max_output/correlation and optional test transport; no retries/fallback |
| Serialization | `MetaProvider.structured` | Two messages: developer instructions, user `json.dumps(data, ensure_ascii=False)`; `model`; `max_completion_tokens`; reasoning `minimal`; json_schema response format |
| External request boundary | `_request`: HTTPX POST to configured Meta URL/base + `/chat/completions` | Bearer header; `X-Request-ID` correlation or UUID; bounded timeout. MockTransport captures actual dispatched body. No external Meta request sent |
| Provider response | JSON `choices[0].message.content`, usage, finish reason | Length refusal works; malformed envelope/content defects F-004 |
| Local validation | `RoleOutput.model_validate_json`; every claim reference checked against supplied source/memory/event IDs | Failure does not execute action; existing reference guard mutation killed |
| Settlement / persistence | Invocation validated/failed/cancelled; output JSON, latency, usage; conservative charge retained for uncertain failures | Source and tests; independent transaction-exit cancellation leaves stale reserved record |
| Next stages | Proposer/optional critic, tool evidence, deterministic evaluator, Governor action decision | Models do not own tool permissions or scheduler; consequential class C remains unsupported |

`StructuredRequest` is a frozen dataclass, not a runtime validation model; freezing is shallow and does not make nested dictionaries immutable. No independent mutation-during-await exploit was reproduced. Current caller constructs and awaits its own request. Treat deeper immutability as a design/coverage question, not a confirmed dropped-parameter defect.

## Other request paths

The main ratchet allowlist includes seven structured construction sites in total: one gateway plus six direct sites. Direct structured sites are `living.reason`, `experiment.service.call`, `research_relationships._analyze_bounded`, `research_relationships.analyze`, `web_experience.execute`, and `scripts.benchmark.invoke`. It also enumerates six discover paths and an app capabilities-only construction. This agrees with PR53's stated scoped migration; the entire runtime has **not** been moved behind the gateway.

* **Relationships / bounded A-B / claim mode:** Preview discloses exact instructions/input/schema, derives request and payload hashes, binds provider/model/snapshot/memory/goal/anchor, and checks again before marking possible dispatch. Durable reservations and campaign index/stage/fatal checks precede transport. After response, exact quote/schema validation and source revalidation precede retained analysis/connection writes. Withdrawal scrubs/invalidate dependents; restart settles possible dispatch conservatively without replay. Selected paths reviewed; ALIVE-14 test families passed.
* **Web notes:** Snapshot hash and active exact-page grant, relevance/explicit correction, Governor/session/spend gates, durable note reservation, second grant check, bounded Meta structured request, DocumentationNote validation plus exact evidence quote, usage settlement. Direct provider path remains deliberate. Source/model outputs are labelled separately.
* **Living:** Permission and conflict checks, bounded episode/journey/session spend, durable ledger then direct Meta call or clearly labelled fixture; actions in synthesis output refused; settlement precedes subsequent work. Selected `reason` path reviewed; all journey failure windows not independently mutated.
* **Frozen experiments:** Exact frozen protocol/source checks and explicit evaluation authorization; bounded `call` writes ledger/control reservations; structured RoleOutput validation; scorer binds numerical target and citations. Original failure/output accounting is kept rather than substituting successful fixture data. Only selected source paths reviewed.
* **Standalone benchmark/discovery:** Explicit native/benchmark tools are different entry points. Audit never ran their real-provider modes. Discovery methods use a GET models boundary and do not execute tools. Health capability probing does not dispatch inference.

## Sentinel parity and failure matrix

Independent [audit probes](test_adversarial.py) compare expected objects with the actual MockTransport request, not just the output of another copy of the same provider. Synthetic transport receipts are `receipts/transport-*.json`.

| Field / edge | Result |
|---|---|
| Nested objects, tool-like names/argument keys/call IDs in data | Preserved exactly |
| Empty strings, zero, false, null, empty array in data | Preserved exactly |
| Unicode / escaped strings / newline / long value / nested zero | Preserved exactly in decoded dispatched JSON |
| Schema/instructions/model/output/correlation normal cognition path | Existing gateway parity/sentinel suite passed; PR55 field tests and golden request suite passed |
| Explicit max_output0 | Silently becomes1536; F-007 |
| Omitted optional model/output/correlation at direct provider API | Defaults exist; exhaustive omitted-vs-null-vs-empty compatibility matrix NOT EXECUTED |
| Unknown factory operation | Refused by main |
| Mismatched request operation on selected gateway | Main dispatches; PR55 refuses; F-006 |
| Truncated response | Typed output_truncated with response-received liability |
| Empty choices/null/list content | Defective typed validation; F-004 |
| General tool-call execution/tool ID response mapping | NOT APPLICABLE to this structured request contract; external tool interface UNVERIFIED |
| Real Meta response variants / actual upstream serialization receipt | NOT EXECUTED; no paid calls |
| Retry/fallback | No automatic retries/fallback in reviewed MetaProvider/gateway; workflow error classification is separate |
| Full concurrent mutation/transport cancellation matrix | COVERAGE GAP |

## Finding on the original dropped-parameter allegation

No silent loss of the supplied nested argument data was observed at ALIVE's controlled HTTP transport boundary. Zero output defaulting is a separate confirmed field transformation, and request operation identity is ignored on main. Neither demonstrates where the external contributor's reportedly dropped tool parameters disappeared.

To resolve the external allegation, collect one synthetic failing call's tool schema, model-emitted raw arguments, validated object, serialized invocation, execution inputs and correlated result. Redact credentials before retaining it. Without those records, ownership remains unverified and should be reviewed independently of ALIVE's application defects.
