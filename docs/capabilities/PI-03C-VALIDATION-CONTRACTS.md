# PI-03C validation contracts

## Installed versions and authority

| Operation | Version | Implementation | Permissions |
| --- | --- | --- | --- |
| `evidence.validate_references` | 1.0.0 retained | `validate-references-v1` unchanged | Existing approved workflow context |
| `evidence.validate_references` | 1.1.0, explicitly pinned | `captured-references-v1` | `source.read`; no network/filesystem/process/persistence |
| `evidence.verify-locators` | 1.0.0 | `captured-locators-v1` | `source.read`; no network/filesystem/process/persistence |
| `evidence.compare-claims` | 1.0.0 | `captured-claims-compare-v1` | No ambient resource access; exact trusted dependency records |
| `report.compose` | 1.0.0 | `captured-report-v1` | No ambient resource access or persistence; exact trusted dependency records |

The existing operation uses underscores; it is upgraded under that identity rather than adding
a competing hyphenated alias. New versions cannot inherit an old grant. Registration captures
manifest and implementation hashes; owner grants bind exact identities, limits and permissions.
Implicit PI-02 operations retain the original 1.0.0 implementation, including reused aliases.
The new source-reading contract must be selected explicitly. No legacy allowlist is extended.

## Source validation input

Strict `Batch` contains `source_ref`, `source_sha256`, `scoped_sha256` and up to eight findings.
Every finding has an immutable-within-the-record id, claim text (512 characters), and up to four
references. Every reference carries its stable source id, item key, captured item SHA-256 and
an explicit locator. Extra fields, including `verified` or execution permissions, are refused.
Duplicate finding ids are refused; missing/duplicate evidence ids receive named classifications.

Custody resolves source ownership/instance, capture hash, approval, operation, scope, expiry and
withdrawal before the adapter receives `ApprovedSource`. The adapter independently compares
capture and effective-scope identity, checks each captured item hash, and validates repository
paths. It does not open a path, URL or live document. Stages support at most 65,536 captured-view
bytes, 65,536 input/output bytes, 30 seconds, one invocation, zero model calls and zero tokens.
The existing runner enforces grant/deployment intersections, output limits and cancellation.

`source_id` is the existing PI-03B identifier. Capture id, approval id, full and effective scope
digests are retained separately: identical bytes or ids alone are not evidence of owner consent.

Reference outcomes: `identity_valid`, `missing_reference`, `duplicate_reference`,
`unknown_reference`, `hash_mismatch`. Absent source/approval, scope expansion or substituted
capture is a stage refusal; no false successful source identity is returned.

## Locator policy, v1

| Kind | Interpretation | Unsupported / refusal behavior |
| --- | --- | --- |
| `file_lines` | Repository file, one-based inclusive line bounds; uses existing L1-02 bounds checker | Missing file or out-of-range bounds cannot pass |
| `section` | Captured document/browser section index, both bounds equal that index | No invented document page coordinates |
| `text_span` | Zero-based half-open character span in captured item text | Bounds must exist in captured content |
| `page` | Reserved named unsupported kind | Always `unsupported_locator_kind` for current captures; no PDF parser added |
| `none` | Explicit missing locator | `missing_locator` when locator validation is requested |

CRLF and bare CR normalize to LF for locator coordinates and quotation comparison. Hashes still
cover original captured bytes. Quotes are exact substrings after newline normalization; arbitrary
whitespace is not squashed. This new policy does not change L1-02's existing quotation contract.
Outcomes distinguish `not_run`, `locator_valid`, `quote_matches`, `quote_mismatch`,
`invalid_locator`, `missing_locator`, `unsupported_locator_kind`. Invalid locators produce no
comparison observation. No locator result establishes semantic support.

## Controlled comparison, v1

Inputs select two stable ids from records equal to actual trusted validation dependencies,
including records from two separately approved captures. A model or caller cannot impersonate
a dependency by supplying a plausible provenance field. Each observation retains original item
digest, observed-value digest, locator status, a 512-character display and explicit truncation.

* `exact`: compare the observed values' full digests (raw captured text for reference records,
  newline-normalized selected text for locator records).
* `changed`: compare full captured item digests, returning `changed` or `unchanged`.
* `normalized_fields`: compare explicitly selected scalar JSON fields; object key order is ignored,
  types remain distinct (`true` differs from `1`). Missing/duplicate keys, non-finite numbers,
  non-scalar fields and truncated observations yield `not_comparable`.
* `text_span`: compare validated locator-selected text only, without semantic similarity. Missing
  valid locators or truncated display yields `not_comparable`.

Other field-selection arguments are refused, rather than silently implying a subset comparison.
`equal`, `different`, `changed`, `unchanged` and `not_comparable` describe controlled records,
not truth in the world or semantic entailment.

## Composition and persistence

`report.compose` accepts only records equal to an actual successful dependency from the reviewed
validation implementations. It preserves findings, source identities, classifications,
observations, omissions and truncation. Report text is capped at 16,384 UTF-8 bytes; exceeding it
refuses rather than silently dropping findings. Existing capability output-byte enforcement
also applies. Existing `result.record` retains the resulting artifact; there is no new store.
The Observatory renders report text inertly, with original structured records available.

The internal `validation.independent` implementation trait means a deterministic validation
dependency suitable for result recording. It never means a factual claim was independently
verified. All records retain `semantic_support: unverified`, `independent_verification: false`,
and `task_outcome: unknown`; `contract` and `structural` describe schema/shape checks only.
Individual reference and locator classifications remain separate. A false claim with an exact
citation remains unverified. Stage `passed` means the procedure ran, not that every citation passed.

Source content may be retained in observations, reports and stage outputs in clear text. Only
synthetic/non-sensitive or deliberately public qualification sources are supported here. No
retention/deletion policy, provider confidentiality guarantee or new model disclosure is created.
