# PI-03C deterministic foundation — delivery for independent review

Status: **draft / not qualified as the full PI-03C milestone**. No automatic merge.

Baseline main: `4e990bfadb886eba933a88f1c07e1b2543ab8f02`.
Branch/worktree: `codex/pi-03c-validation`, `C:/Projects/alive-pi03c`.
Final executable-code baseline: `e0992b39a9429a2eb8dbbc27eb132b3c7bfee23d`.
The exact delivered SHA, draft PR and final CI are reported on the PR, without extra status-only
pushes. PR #83's correction is separately on `b2f39251ca6915e847133214179be799ec068f58`;
its Ubuntu CI has passed, while Windows and independent security review were pending at delivery.
No security code from that PR is copied into this branch.

## Scope delivered

* Versioned captured-reference, locator and controlled-comparison capabilities plus deterministic
  report composition, with reviewed implementations and bounded manifests.
* Existing source custody, stable source ids, repository line-bound checks, registration,
  per-stage resource grants, WorkflowRunner, retained artifacts and Observatory are reused.
* Original reference validator 1.0.0 and L1-02 quotation behavior remain unchanged. Implicit
  legacy workflows and aliases retain 1.0.0, including when only the new explicit version is
  disabled. No new security exception/legacy hash allowlist is added.
* Three different deterministic graphs execute: repository inspection/reference/locator review,
  document extraction/section review, and two separately approved sources joined by controlled
  comparison. They retain actual approvals, bindings, execution, artifacts and replay.
* The existing Observatory shows composed text inertly alongside the structured evidence and
  statuses. No new database, model client, executor, public grant or registration API.

The required **authorized-Pi research workflow is not delivered/qualified**. The document graph
is a deterministic evidence path, not a substitute for it. Production research/model integration
depends on independent acceptance of PR #83 and an admitted document-analysis contract. L2-01
and L2-02 are not implemented. No inference, semantic intelligence or improved selection claim
is attached to these deterministic primitives.

## Tests and evidence

| Check | Result |
| --- | --- |
| Final primitive / source-identity / locator / comparison / report / runner / cancellation / replay / historical tests | 46 passed before the additional explicit-version availability control; that control passed separately |
| Source, registry compatibility, manifest and legacy adoption initial group | 46 passed |
| Capability reuse under aliases, contract enforcement/resolution, source capabilities, L1-02 units and workflow-store regressions | 112 passed; includes real pinned Pi compatibility using a scripted upstream |
| Broader primitive/workflow/catalogue/authority/hardening/owner-admission/Bespoke/Intelligence receipts group | 160 passed before the final typed-dependency control; affected primitive/runner cases rechecked as above |
| Final registry resolution/registry/adoption checks after availability projection alignment | 29 passed |
| Dashboard workflow component / production build | 18 passed / built |
| Real Chrome / real disposable backend and retained artifact | Passed; authenticated read-only graph/report inspection, all network API requests GET |
| PostgreSQL deterministic graphs | All three passed; repository and comparison rechecked after findings/file-ceiling changes; all three rechecked after canonical dependency matching |
| PostgreSQL source-custody race/migration chain | Passed on a separate initially empty disposable database |
| Docker | Image built with Pi 1.4.0, PostgreSQL migrations/startup and smoke/HTTP journeys passed; exact final image/result recorded on PR |
| Changed-file Ruff / format / diff checks | Clean |
| Full backend, full dashboard/extension and Windows/Linux exact delivered-head qualification | CI pending; no duplicate local bare full-suite run |
| Independent adversarial review | Pending; author tests and gold fixtures are not independent acceptance |
| Authorized-Pi research composition and L2 integration | Not run/implemented; explicit dependency gate |
| Live/paid inference | None |

Final Docker smoke image:
`sha256:fe9755fb36ddfe2e936e81cd40eb20804046e7df5633ea94606852716728e8ae`.
The final image passed all eight smoke checks and all six existing HTTP journey groups.
Disposable Compose volumes and the separate PostgreSQL qualification container were removed.

Existing Windows Proactor/ZeroMQ warnings remain. Qualification sources are synthetic. Captures,
observations, prompts from older paths and report/stage records can remain stored in clear text.
No deletion/retention policy or remote-provider confidentiality guarantee is introduced.

Resource use is bounded to zero model calls/tokens for these paths, 65,536 input/output bytes,
65,536 captured-view bytes, at most 64 repository files and 30 seconds per capability call.
Observations display at most 512 characters with explicit truncation; full observed/item
digests remain available for the defined comparisons. Reports refuse beyond 16,384 UTF-8 bytes.
The existing runner retains per-stage/run duration and output provenance. Deployment latency,
throughput and storage-cost benchmarking are not claimed from test timings.

## Qualification findings corrected

The initial graph fixtures incorrectly required optional document pagination fields and attempted
an array literal that WorkflowSpec does not permit. They now use the existing manifest required
set and a declared array input; no executor/schema boundary was relaxed. A second Governor
inquiry needed a separately admitted observation, supplied through the normal fixture path.

One initial item-hash mutant caused an incomplete test double to crash after guard removal.
That attempt is preserved as **invalid**, not a kill. The probe now mutates a real detached
ApprovedSource with complete metadata and kills the guard behaviorally.

Review also found an unenforced lower repository-file ceiling and Python's `True == 1` /
`False == 0` record-equality ambiguity. Both were reproduced/corrected before delivery: the
adapter enforces the granted file count, and trusted dependency identity compares canonical
JSON bytes. Original finding identities are preserved for both sides of a controlled comparison.
Legacy availability projection now matches the original 1.0.0 binding, preventing a disabled
new version from revoking an old implicit workflow.

## Mutation receipts

[Receipts and gzip transcripts](validation/pi03c/) include the original attempts and stronger
follow-ups, each with immutable baseline and exact pytest command. The `qualified-mutations`
campaign at `afb598c8d25b3abf34a51f479dce1d8266eb5415` kills all **11** selected guards:
typed dependency identity, file ceiling, source scope, captured-item digest, evidence id,
line bounds, exact quotation, semantic non-promotion, trusted dependency implementation,
source-byte ceiling and implicit compatibility. The compatibility guard was killed again at
the final executable baseline after aligning the availability projection. No runtime crash is
counted as a behavioral kill. The earlier invalid item-hash attempt remains visible.

No production checkout is deliberately mutated: every edit is in a new git archive directory,
with original production-source hashes checked after the campaign. This is targeted guard
coverage, not a claim that every possible security mutation was enumerated or independently
qualified. Baselines differ across receipts; they are not one fictional exact-head full campaign.

## Merge/exit prerequisites

Independent review and exact-head CI must pass. Complete the named research/model dependency
through the qualified transport and owner admission, rather than adding a second model client or
fabricating an executable role. Then qualify the required research workflow, its real model/source
permissions and receipts. Retention/sensitivity decisions remain explicit owner policy work.
Until these gates are satisfied, keep this as a reviewable deterministic foundation and do not
claim the full PI-03C exit gate or begin production L2 invocation.
