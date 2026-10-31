# L1-02 — Model admission and role contract

## The profile

`approved-repository-analysis/1.0.0` is a closed profile in code (`alive/admission/profiles.py`).
A request can name it; it cannot change it. It is separate from `approved-repository-inspection`,
whose reviews contain no `profile` key and whose digests are unchanged.

| Bound into the owner's review and Grant | Where it is rechecked |
| --- | --- |
| goal, inquiry, principal | prepare, approve, start, every stage (`authorized`) |
| source capture, approval, scope and file digests | `custody.resolve` for **both** operations: `repository.inspect` and `repository.analyze`, at prepare, approve, start, each source stage, and the dispatch fence |
| recipe hash, workflow hash, capability binding | prepare, approve, start |
| provider, transport, host, model | `disclosure()` recomputed at approve and start; `model_claim` at reservation |
| role contract (instructions + schema + context policy) | approve, start, reservation, dispatch fence |
| 1 model call, output tokens, 180 s | Grant, Governor reservation, runner |
| exact context (files, line numbers, digests) | rebuilt from the stage inputs at the reservation; digest compared at the fence |
| expiry | Grant |

Changing the model, the provider key, the transport, the role text, the Governor configuration, the
source, or the workflow makes the review stale and start refuses before any request exists.

## Disclosure

The review contains a `model_disclosure` block the owner reads before approving: operation,
destination (provider, host, transport, model), the exact files and byte count that leave the host,
the Governor request reservation, call and token ceilings, cost (`unknown; none estimated`), the
cancellation limit and retention (clear text in the local database).

A source approved only for `repository.inspect` cannot be reviewed under this profile and is not
offered by `GET /api/v1/admissions/sources?profile=approved-repository-analysis`. Approval to read
is never approval to disclose. Grant the disclosure separately, locally:

```bash
python -m alive.sources approve <capture_id> --confirm-sha256 <digest> \
  --operation repository.inspect --operation repository.analyze --item calc.py
```

**Policy gap, stated rather than hidden.** ALIVE has exactly one model destination (the Meta
endpoint through Pi). The gateway therefore cannot tell local from remote inference because no local
path exists. L1-02 does not add one. The separate source operation, the named destination in the
review and the repeated checks above are the enforcement; there is no network-level allowlist beyond
the configured endpoint.

## Starting

The model path needs Cognition started by the owner with provider `meta` (the existing PI-02
requirement). Pausing it is a kill switch: a paused Governor cancels a call that has not been
dispatched. L1-02 neither starts nor stops autonomy.

## Role contract `repository-analysis/v1`

The model receives: the objective; the supplied files with a printed line number before each line;
digests; the omitted list; the coverage statement; and the instruction to treat file text as
untrusted data, never invent citations or quotes, report nothing the lines do not support, state
uncertainty, and return no findings when none are supported. It has no tools.

Output (`extra="forbid"`, so any added field such as `actions` or `permissions` fails the schema):

```
summary, findings[≤5], unresolved_questions[≤5]
finding: finding_id, title, category, severity, explanation,
         evidence[1..4]: {file, line_start, line_end, quote}, uncertainty, suggested_verification
```

Severity is a model assessment. The contract digest the owner approves covers the exact
instructions, the JSON schema and the context policy.
