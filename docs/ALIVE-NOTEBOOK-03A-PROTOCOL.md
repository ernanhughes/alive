# ALIVE-NOTEBOOK-03A — frozen protocol

Protocol: `evaluations/notebook03a/protocol.json`, version `notebook03a-v1.4`. Baseline main:
`a9bcf8673818e85246a268c308b64d2080792b96`. No inference or spending is authorized.

## Hypothesis and primary task

A structured semantic qualifier may preserve useful historical evidence and detect specific
corrections while reducing unsupported connections relative to lexical candidates. It must
outperform indiscriminate abstention on useful findings, under identical evidence access.
This is a research hypothesis, not an observed ALIVE capability.

Each task supplies a question, exact claim passage(s), bounded source text/hash and explicit
unknown context fields. Pair tasks compare two identifiable propositions. Claim-support
tasks compare one presented assertion with its evidence, including within one source.
No automatic crawling, page discovery, new retrieval or model execution is part of 03A.

The strict schemas are exported in `schemas.json` and implemented in
`scripts/notebook03a_protocol.py`. Gold annotations, annotation notes and origin provenance
are separate from `tasks.json`. `prepare_payload` uses a whitelist and drops task/family/
split IDs, origin labels, inferred proposition fields, authored supporting-span hints and all
gold/annotation metadata. Full bounded source excerpts remain identical for all arms.
Whitelisted source and claim IDs are local citation identities, not encoded outcomes.

## Corpus and provenance

40 public draft cases: 16 development, 24 public evaluation. Seven are authentic ALIVE
history; 33 are synthetic/controlled (including the R4 headline attack). All public material
and labels are IMPLEMENTER_EXPOSED. Template variants belong to eight common families;
they are not independent samples. The authentic cases are also correlated historical reports.

| Provisional relation | Cases |
|---|---:|
| Supersession | 5 |
| Scoped change | 6 |
| Corroboration candidate | 4 |
| Contradiction candidate | 4 |
| Other substantive connection | 3 |
| Independent observations | 5 |
| Unsupported claim | 5 |
| Unknown | 8 |

There are 31 pair tasks and 9 claim-support tasks. Two pair tasks declare inaccessible
fixture evidence (one unauthorized, one withdrawn) and are hard-gate/refusal diagnostics.
Among the 38 authorized tasks there are 27 provisionally useful findings and 6 insufficient
cases. Missing evidence/conditions are represented as incomplete support, not manufactured
historical passages. Single-source negative findings can be useful corrections.

R1–R4 and additional ALIVE cases are development examples, not blind generalization tests.
R1 binds old/new specific labeling passages with directed superseded/replacement claim IDs.
R2 includes the history-access comparator, eligible-row correction, frozen corpus and limits;
no universal reversal is acceptable. R3 distinguishes campaigns, not a keyword exclusion.
R4 combines a clearly synthetic headline with a verifiable ALIVE qualification in one
source. `origins.json` pins full document Git hashes and exact original offsets; authentic
text must be verbatim. Controlled material must retain its declared source quote and be
explicitly marked. Synthetic material may not masquerade as a canonical document.

Chronology/serialization reversal, alternative names, distractor terminology, changed
comparators, conflicting matching-condition results, independent replication, unrelated
word senses, missing baselines, date-only discussion and injected instructions are covered.
Identical same-source claims are duplicates, not independent corroboration. Ambiguous
same-entity/date-only cases are insufficient rather than automatically independent.

## Independent held-out workflow

Target total 52: 40 available public cases plus 12 independently authored held-out cases.
Available independent cases: **0**. Status: **PENDING_INDEPENDENT_LABELING**.
No independent labels, consensus or inter-rater agreement has been collected or fabricated.

A custodian outside the implementer's access boundary must create a package containing
`tasks.json`, `annotations.json`, `origins.json`, and `independent_submission.json`, using
these schemas. Tasks use the independent_heldout split and unfamiliar source texts/families.
Each label identifies author/reviewer attestations, rationale, required exact passages,
forbidden conclusions, applicability/sufficiency and ambiguity. The current attestation
schema requires two distinct reviewer identities separate from the author; this is a
proposed adjudication gate, not evidence those people exist or agree.

Only the custodian runs `submission --package <restricted-directory>` on an independently
controlled account/machine. The validator rejects repo-local packages, exposed task families/
source hashes, incomplete labels, inconsistent package hashes and answer-exposure events.
It validates attestations, not operating-system ACLs or human identity. An outside directory
alone does not establish blindness. The human reviewer must verify actual access controls.
Share only package hashes, counts and aggregate reports; keep inputs/gold away from the
03B implementer until its implementation and prompts are frozen. Any exposure of answers
is logged and invalidates that set as a blind holdout for subsequent tuning. Never use
public repo evaluation files as a purported sealed test set.

## Arms and matching conditions

A: actual current Core lexical connection API (`deterministic-lexical-connection-v1`),
including inherited ALIVE-13/14 conservative candidate policy. No category is invented for it.
B: actual Notebook-02 integrity qualifier, not semantic judgment. A/B are pair-only APIs.
For the 9 single-claim tasks they report NOT_APPLICABLE, not a fabricated comparison.
B0: explicit all-task constant-abstain reference, additional to B; not a simulated model or
a claim that the existing Core supports single-source qualification.
C: same-evidence general model with the shared schema/category definitions; NOT RUN.
D: same model/settings/evidence/schema plus the specialized procedure; NOT RUN.

All reasoning arms may abstain. Shared definitions and source access are identical for C/D;
only the procedure prompt changes. Baseline fixture URLs are existing allowlisted transport
addresses in an isolated SQLite test runtime, not the canonical attribution of ALIVE sources.
Access diagnostics are fixture-gate checks, not a new qualification of live browser grants.

Source budgets: at most 2000 characters each, 4000 total; serialized payload at most 16000
characters. No silent truncation of claims/qualifiers. Retrieval rankings are not evaluated
or changed; fixed candidate claim sets are held constant. Compare C/D with A/B only on the
common pair stratum, and report single-claim support separately versus B0. Origin and task
kind strata are provided. A full-history access experiment would require a separate protocol.

Proposal for 03B, **not authorization**: same explicit provider/model family (UNSELECTED),
proposed temperature 0 subject to model support, one attempt per arm/case, no automatic
retries, at most 8192 input tokens including prompt/schema and 800 output tokens, 104 calls
for 52 tasks × two reasoning arms, USD 1 proposed ceiling. Authorized calls/spend remain 0.
Select and freeze exact supported model/revision/settings and verify current worst-case
pricing under the ceiling before owner approval; amend if that is not feasible.

## Scoring, denominators and uncertainty

Every task needs exactly one outcome per executed arm. Missing, duplicate, unknown-reference
or unjustified NOT_APPLICABLE records fail; difficult tasks cannot disappear. Explicit access
refusals, API-inapplicable tasks and missing/pending labels have separate coverage counts.
Unknown/insufficient gold is valid; missing gold is not automatically assigned an answer.
Draft-label metrics are provisional, not independently established semantic accuracy.

- Category accuracy: accepted relationship-set matches / scored cases. Unknown predictions
  remain unknown even if they happen to match an unknown gold label.
- Sufficiency accuracy: sufficiency matches / scored cases, distinct from category accuracy.
- Correct substantive judgments: non-unknown offline test/03B proposed classifications with
  accepted category, sufficiency, applicability, decision, directed replacement IDs where
  relevant, and coverage of every required gold evidence span. The label judgment is not
  independently verified truth. Negative non-use corrections can be substantive judgments.
- Unsupported substantive judgments: proposed classifications failing any acceptance check.
  Substantive precision = accepted judgments / proposed judgments; zero proposals => null.
- Useful finding retention: accepted judgments on useful-labelled cases / useful-labelled
  scored cases. Missed useful findings = denominator minus accepted useful findings.
- Useful candidate recall: retain_candidate actions on useful-labelled cases / useful-labelled
  scored cases; candidate actions alone do not become semantic findings.
- Correct insufficient abstention: explicit abstentions on insufficient-labelled cases /
  insufficient-labelled scored cases. An always-abstain system may score 100% here while
  missing every useful finding; there is no composite score that hides that tradeoff.

Confusion matrices and per-category/origin/task-kind reports retain explicit denominators.
A/B paired candidate discordances are reported without semantic interpretation. For future
C/D use paired case outcomes, retain variant-family clustering and report both directions of
discordance. Nominal Wilson 95% intervals are provided only as a clearly marked illustration
under an independence assumption that these deliberately selected family cases violate.
They are not valid population uncertainty or statistical superiority evidence. Public
synthetic/draft-label results do not support significance or generalization claims.

Citation validity is an integrity gate, not entailment: exact quotes must name authorized
supplied sources and match their offsets/hash. Correct-looking labels with missing required
qualifications are not credited by the scorer. Natural-language scope explanations,
limitations and forbidden conclusions still require independent output adjudication before
03B can claim semantic correctness; deterministic substring checks cannot establish them.

Authorization/disclosure, fabricated citations, unsupported refs, missing consent and budget/
cancellation violations are hard gates, never averages. Model execution/import is unavailable
in 03A. CLI scoring permits only baseline records; an explicit unit-test-only flag exercises
scoring mathematics using offline fixtures, not pretend model results. A 03B trusted adapter
must resolve real Core evidence and verified consent/usage receipts before model results can
be admitted. No caller-supplied access bit or synthetic ledger can substitute for that gate.

## Freeze, amendments and 03B prerequisites

Inputs, draft annotations, prompts, schema exports and metrics have LF-normalized SHA-256
fingerprints in protocol.json. Earlier draft protocol/schema/annotation snapshots remain
preserved. Amendments before replay added directed replacements, corrected date-only
uncertainty, defined external package isolation gates, and strengthened R1/R2 required qualification spans. Changes after freeze must append
an amendment/new version and retain the previous evidence. Baseline expectations are derived
from measured policy replay, stored separately from gold, and compared deterministically
in CI; do not rewrite them merely to conceal changed baseline behavior.

Before 03B: Claude protocol review; resolve the five Notebook-02 contract dependencies in
an explicit narrow migration; independently adjudicate public labels; obtain and verify a
restricted independent package; freeze exact model/settings/pricing and trusted single-/
dual-source governance adapter; separately approve exact payloads/prompts/schema/call/token/
spend caps; qualify cancellation/restart and source/citation revalidation. None is authorized
by 03A. Stop after the 03A draft PR/report; human merge authority only.
