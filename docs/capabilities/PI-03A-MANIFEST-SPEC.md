# PI-03A capability/v1 manifest specification

A manifest declares a capability's contract, limits, permissions and presentation. It
confers no authority and names no code. Source of truth: `alive/capabilities/manifest.py`
and `contracts.py`; this document describes what those enforce.

File name: `<id>@<version>.yaml`, at most 64 KiB, UTF-8, one document. The loader refuses a
name that disagrees with the declared identity.

## Fields

| Field | Rule |
| --- | --- |
| `schema_version` | Exactly `1`. |
| `id` | Dotted lowercase (`repository.inspect`), at most 64 characters. |
| `version` | `MAJOR.MINOR.PATCH`, no leading zeros. |
| `name`, `description` | 1-100 and 1-1000 characters. Rendered as inert text. |
| `implementation.provider` | `builtin` only. |
| `implementation.id` | Opaque id looked up in a server-owned allowlist. Never imported. |
| `implementation.sha256` | Optional pin of the implementation fingerprint. A mismatch makes the capability `incompatible`. |
| `execution.kind` | `deterministic`, `pi_agent`, `validation` or `approval_gate`. |
| `execution.side_effects` | `none`, `read` or `write`. |
| `execution` limits | `timeout_seconds` (1-3600), `max_input_bytes`, `max_output_bytes` (at most 65536), `max_input_items` (1-32), `max_invocations` (exactly 1), `retry_policy` (`none`), optional `max_files`, `max_source_bytes`, `max_model_calls`, `max_output_tokens`. |
| `permissions` | `filesystem` (`none` or `read_only` with root `authorized_repository`), `network` (`none` or `governed_pi`), `process` (`none`), `evidence` (`none` or `approved_context`), `persistence` (`none` or `workflow_result`). |
| `inputs`, `outputs` | A closed object contract in the bounded JSON-schema subset below. |
| `presentation` | `category`, `icon`, up to 12 sorted `tags`. |
| `deprecated` | Optional boolean. A deprecated capability still executes; it is flagged. |
| `supported_source_types`, `examples` | Optional. Every example must validate against `inputs`. |

Unknown fields, missing fields and wrong types are refused (`extra="forbid"`, strict mode).

## Contract subset

Types `object`, `array`, `string`, `integer`, `number`, `boolean`. Keywords: `properties`,
`required`, `additionalProperties`, `items`, `minItems`, `maxItems`, `minLength`, `maxLength`,
`enum`, `minimum`, `maximum`. Objects must state `additionalProperties`, arrays must state
`maxItems`, strings must state `maxLength`. No `$ref`, patterns, formats, expressions or
validator code. Nesting is limited to 8 levels. Root contracts must be closed.

## Parser restrictions

Refused before any hashing: custom or explicit tags, anchors and aliases, merge keys, duplicate
or non-string keys, more than 8192 YAML events, nesting beyond 16, mappings over 64 keys,
sequences over 256 items, strings over 4096 characters, control characters, and the
interpolation markers `${`, `{{`, `{%`. Scalars resolve with JSON-style rules only, so `yes`,
`on`, dates, hex and sexagesimal numbers stay strings.

## Identity

The canonical identity is SHA-256 over the validated manifest serialized with sorted keys,
compact separators and sorted set-like lists (`required`, `enum`, `tags`). Whitespace, key order
and set-like list order do not change it. Any change to permissions, implementation, a contract
or a limit does.

A capability identity is `{id, version, manifest_sha256, implementation_id,
implementation_sha256}`. The implementation fingerprint covers the implementation id,
interface, its permission ceiling and the normalised bytes of the reviewed source files.

## Cross-checks against the trusted implementation

At startup the registry refuses a manifest whose `permissions` do not equal the implementation's
compiled ceiling, or whose `kind` or `side_effects` differ from the implementation's. A
manifest can therefore neither widen nor silently narrow what reviewed code does.

## Statuses

`available`, `deprecated` (still executable), `unavailable` (no installed implementation),
`incompatible` (pinned fingerprint mismatch), `disabled` (deployment policy). Availability is
never authorization.

## Versioning guidance

The registry enforces only hash and fingerprint identity, and that one operation id cannot change
`kind` across versions. The remaining rules are review conventions:

- Patch: wording or presentation only; behaviour and contracts unchanged.
- Minor: backward-compatible addition, such as an optional input or a new output field.
- Major: removing or retyping a field, changing meaning, or changing permissions or limits upward.
- A permission change requires a new version and a new implementation review.
- Revoke by listing the capability in `ALIVE_DISABLED_CAPABILITIES`; deprecate with
  `deprecated: true`; remove by deleting the manifest. Pinned runs then refuse to execute and
  their retained identity stays inspectable.

## Template

`docs/capabilities/capability.template.yaml`, validated by a test.
