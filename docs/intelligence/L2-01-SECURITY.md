# L2-01 — Security notes

## What is disclosed, to whom

To the configured model destination (pinned endpoint, bound into the review): the owner's goal
text, the **names and sizes** of the approved files, the source label and classification, and the
trusted recipe catalogue. **No file content.** Because file names and labels come from the owner's
repository they are marked untrusted data in the prompt. The prompt and response are kept in clear
text in the local database (inherited retention decision, still open: see
`L1-02-SECURITY-DECISIONS.md`).

The owner's Grant (goal text, file names) is an authenticated event, as in L1. File content is not
in any event. Tests assert both.

## Authority

* Disclosure needs its own source operation, `intent.interpret`; inspect and analyze approvals do
  not cover it, and the picker offers only sources approved for it.
* The interpreter's authority is a separate immutable review, local approval and Grant; the
  recommendation grants nothing and `execution` is always `not_authorized`.
* Layers that enforce one invariant (model, role contract, goal, catalogue, destination) are
  attacked jointly or separately with the dispatch fence switched off; see the delivery report.
* The recommendation cannot start work: there is no route that does, and a recommended procedure
  needs its own review and approval.

## Model output is untrusted

Strict schema (unknown fields refused), bounded arrays and text, enums for the intent kind. Candidate
ids are matched exactly: padded, re-cased, wrong-version and invented ids are reported, not
corrected. Prose is stored and rendered as text. Output that does not return the goal unchanged is
rejected as a whole.

## Known limits

* Eligibility proves executability, not appropriateness (measured negative control).
* Only repository sources; one destination; no local inference path; no network allowlist beyond
  the pinned endpoint (the proxy/CA environment point from the Level 1 review still applies).
* Clear-text retention and no deletion policy; encryption and purge remain owner decisions.
* The model's `intent_kind` feeds the existing selector, whose recipes today share one intent, so
  the practical effect of the kind is limited until more recipes exist.
