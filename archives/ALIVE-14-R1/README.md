# ALIVE-14-R1 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**META_READY_FOR_APPROVAL** (subject to independent recheck),
**OWNER_USEFULNESS_NOT_MEASURED**.

Baseline: `777e4d99b6908d13875c9024dfb065cb3bfcaffa` (ALIVE-14 merge).
R1 source commit: `9ff0e388cb7a874619e8acf3612beeb6260288c0`.
R2 protocol commit: `3bc28ba`; canonical LF SHA-256:
`b0e255b2b0cf5325726cf1af652d307daeb56c1f227922e184c0235ac0cac349`.
PR: https://github.com/ernanhughes/alive/pull/21 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was performed. No merge or auto-merge was requested.

## Evidence

| File | Meaning |
|---|---|
| `protocol/relationship-experiment-v1.json` | frozen six-task, three-condition R2 experiment protocol; not executed |
| `evidence/pre-fix-defects.json` | REVIEW-07 defect reproductions and corrections |
| `evidence/validator-cases.json` | bounded evidence validation cases |
| `evidence/provider-boundary.json` | kill switch, ledger, reuse, concurrency and invalid-output coverage |
| `evidence/protocol-hash-reconciliation.json` | original ALIVE-14 CRLF evidence hash versus LF Git blob |
| `evidence/native-synthetic.json` | native Chrome consent, valid/invalid output, reuse, feedback and withdrawal journey |
| `evidence/research-relationship.png` | genuine docked side-panel capture |
| `validation/*.txt` | full, focused, extension, frontend, build, Ruff, native and archive verification transcripts |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## Corrected defects

- **Quotation validation:** versioned `alive14r1-evidence-v1` validator; minimum quote length,
  meaningful non-goal terms, shared-term evidence, identical-span rejection and abstention guards.
- **USD accounting:** interrupted and ambiguous attempts remain in the conservative liability with
  no duplicate charge or restart reset.
- **Provider kill switch:** provider enablement, provider identity, pinned model, request hash,
  reservation and USD cap rechecked immediately before dispatch.
- **Reuse identity:** source fingerprints, payload/request hashes, provider, model, analysis version
  and validator version must match; cache hits do not dispatch.
- **Provenance:** original ALIVE-14 archive preserved; CRLF evidence and LF Git blob reconciled.

## Blind rating readiness

Authenticated owner ratings are server-labelled `rater_type=owner`; scripted ratings use an internal
test path and are separated. Conditions are held in a protected assignment record, display order is
seeded, provider/model/tokens/cost are hidden from the rating view, output hashes are immutable, and
ratings are append-only revisions. Reveal requires all owner ratings.

## Native synthetic

Chrome `155.0.8059.85`, genuine docked side panel, local synthetic provider:

- exact payload/request preview and remaining allowance;
- explicit authorisation;
- valid local-stub relationship with quote provenance;
- malformed output rejected with reasons and no connection;
- same provider/model/payload cache reuse without a second dispatch;
- scripted feedback marked as scripted;
- withdrawal invalidated a previously authorised consent;
- restart persistence; zero external calls; 3 synthetic note calls.

## Validation

- Full backend: 187 passed
- Focused research-memory: 41 passed
- Extension: 11 passed
- Frontend: 7 passed
- Production build: passed
- Ruff in CI scope: passed
- ALIVE-14 protocol reconciliation: verified
- Native synthetic: `NATIVE_SYNTHETIC_PASS`

## Boundaries

- No real Meta call or human usefulness rating.
- Quotation provenance is not semantic truth.
- R2 budget figures are planning estimates and must be verified against current pricing.
- Independent recheck of the corrected provider boundary is required before paid inference.
