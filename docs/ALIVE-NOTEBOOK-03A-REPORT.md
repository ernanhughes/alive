# ALIVE-NOTEBOOK-03A — engineering and experimental-readiness report

Decision: **READY_FOR_INDEPENDENT_REVIEW** of the offline foundation.
**NOT READY FOR 03B execution.** Independent held-out labeling, output adjudication,
contract/governance qualification and separate inference approval remain prerequisites.
No semantic performance advantage is claimed. No model inference was run.

## Delivery and provenance

- Prerequisite #44 was verified merged before proceeding.
- Baseline: `a9bcf8673818e85246a268c308b64d2080792b96`.
- Branch: `codex/alive-notebook-03a-semantic-protocol`.
- Tested implementation/protocol: `ee4f9327c1609af0474e649826d53f3407967338`.
- Final review head, including this report/evidence, is in the draft PR/delivery message.
- Completion provenance: the implementation, protocol and evidence were produced by a Codex
  session. A second session (Claude) then committed the remaining evidence and this report
  and opened the draft PR. Before doing so it independently re-ran, in a detached checkout of
  `ee4f932`: `notebook03a validate` (exit 0), `notebook03a submission` (exit 0, still
  `PENDING_INDEPENDENT_LABELING`, `attested_eligibility: false`), `tests/test_notebook03a.py`
  (30 passed), `baseline --check-against expected-baselines-v14.json` (exit 0, A 22/22
  useful candidates and 0 semantic findings, matching the table below), and Ruff check/format
  (clean). It changed no protocol, task, annotation, origin or prompt file. That session
  authored none of the frozen labels and is not an independent reviewer of this work.
- Local environment: Windows 11, Python 3.13.3, Hugo 0.165.0; locked uv dependencies.
- Hosted full suites use the existing Linux/Windows Python 3.13 workflow.

Files: design/protocol/report under `docs/ALIVE-NOTEBOOK-03A-*.md`; frozen tasks,
annotations, provenance, schema exports, prompts, metrics, submission manifest and amendment
snapshots under `evaluations/notebook03a/`; pure contracts/validators/scoring in
`scripts/notebook03a_protocol.py`; reproduction CLI and Core replay in
`scripts/notebook03a.py`; adversarial tests in `tests/test_notebook03a.py`.
Production `alive/` code and existing APIs are unchanged.

## What is available

40 public cases: 7 authentic ALIVE-history cases and 33 explicitly controlled/synthetic
cases. The authentic case count includes repeated/same-document and common-limitation
comparisons, not seven independent experiments. There are 16 public development and
24 public evaluation cases, 31 pair tasks and 9 single-claim support tasks. Thirty-two
synthetic variants share eight families and are correlated. Their value is controlled
coverage, not an independent sample of real research tasks.

All public annotations were authored by this implementation process, **not independent
human annotators**. They remain draft, reviewable judgments. Public splits are exposed,
not blind. Target total: 52 cases, including 12 separately controlled independent cases.
Independent cases available: **0**; status **PENDING_INDEPENDENT_LABELING**. No consensus,
inter-rater agreement or independent semantic correctness has been measured.

R1–R4 are represented as development diagnostics. R1 has directed old/replacement claim
references and complete corrected-label evidence. R2 includes the different history-access/
recency comparisons, frozen corpus and non-generalization qualifications. R3 is a
campaign-specific independent-observations task. R4 is a single-claim support task using
a clearly synthetic title and retained authentic qualification; it is not disguised as a
two-document comparison. Other cases include matching-condition conflicts, independent
replication, different conditions, word-sense collisions, duplication, date-only ambiguity,
missing conditions/support, reversed order, distractors and injected instructions.

## Contracts, gates and independence

Relationship, evidence sufficiency, applicability and decision are separate. Unknowns are
valid. Specific relation categories take priority over the residual substantive connection.
Exact citations, required qualification coverage and directed replacement identities are
validated separately from semantic correctness. A valid hash/quote is not factual truth.

Pinned authentic quotations are checked against Git document objects and full-document
hashes, not just against fixture copies. Synthetic and controlled material cannot silently
claim authentic provenance. Task/annotation schemas reject malformed/unsupported references,
non-exact spans, invalid sufficiency/decision combinations and unsubstantiated independence
metadata. They cannot determine whether an otherwise well-formed semantic label is right.
Human adjudication remains necessary, particularly for free-text scope/limitations and
forbidden conclusions. Automatic label/citation acceptance is only an operational draft score.

The model input preparer whitelists question, task kind, exact claim/source passages and
explicit context fields. It withholds gold labels, case/family/split IDs, author notes,
inferred proposition fields and author-selected supporting-span hints. Routing IDs and
validation summaries are controller metadata; only individual prepared payload values may
be used in a future request, not the whole evaluation report/package. No payload is sent.

The external submission mechanism supports schema/completeness/hash checks and records
exposure attestations. It rejects packages in this checkout, exposed source hashes/families,
pending adjudication and answer-exposure events. These are structural gates, not proof
of OS access restrictions or real human identity. A sibling directory/worktree or a claimed
restricted path is not automatically private. A human custodian/reviewer must verify the
actual separate-account boundary. Future implementers must not read the sealed gold;
exposure invalidates blind use for later tuning. No sealed corpus has been collected here.

## Replayed baselines and scoring

Actual Core APIs were replayed for authorized pair tasks using existing allowlisted fixture
transport URLs and an isolated SQLite runtime. Those URLs are not claimed as the canonical
attribution of ALIVE sources; pinned Git provenance supplies that attribution. This is fixed,
explicitly selected pair comparison, not a retrieval-ranking experiment. It intentionally
includes duplicate-text comparisons that a ranker might exclude. No retrieval gain is claimed.
The unavailable-source guards are declared offline fixture checks, not new live browser
permission qualification. Existing authorization/recovery tests remain unchanged.

| Arm | Authorized scored tasks | API inapplicable | Access refusal | Useful candidates retained | Useful semantic findings retained | Insufficient abstentions |
|---|---:|---:|---:|---|---|---|
| A, actual lexical connection | 29 | 9 | 2 | 22/22 | 0/22 | 0/2 |
| B, actual integrity qualifier | 29 | 9 | 2 | 0/22 | 0/22 | 2/2 |
| B0, explicit abstain reference | 38 | 0 | 2 | 0/27 | 0/27 | 6/6 |

A emitted 29 lexical candidates, including 7 non-useful/insufficient-label cases; that does
not mean seven false factual assertions. B0 gets all six insufficient abstentions while
missing all 27 useful findings. No composite score conceals that loss. Single-claim support
is explicitly NOT_APPLICABLE for A/B; no fake second document or semantic output is created.
C (same-evidence general model) and D (structured semantic method) are **NOT RUN**, with
no performance values invented for them. Unit-test-only scoring fixtures are not model results.

Per-category confusion matrices, source-origin/task-kind strata, paired candidate-action
discordances and denominators are in `baseline-v14.json`. Semantic precision is undefined
for baselines with no substantive judgments. Category matches on unknown labels do not
establish reasoning. Nominal intervals are marked as illustrations under an independence
assumption violated by the corpus; they are not population or superiority evidence.

CI reruns baseline replay and compares its deterministic projection with the committed
`expected-baselines-v14.json`. It excludes UUIDs/timestamps from comparisons and fails on
changed results. Labels and baseline expectations remain separate. All task outcomes are
required; missing/duplicate records, unjustified skips and unverifiable citations fail.
Actual C/D model-result import is deliberately unavailable until a trusted governed adapter
can validate consent, source identity, budgets and usage. A model cannot self-attest those gates.

## Freeze history and fingerprints

Final protocol: **notebook03a-v1.4**. Earlier annotation/schema/protocol snapshots are
preserved, with explicit amendments. v1.1 added directed replacement and corrected the
date-only examples to uncertainty; v1.2 defined external-package isolation; v1.3 froze
validators/tools and withheld author-selected citation hints; v1.4 required full R1/R2
qualification passages rather than truncated excerpts. No semantic model output informed
these changes. Baseline decisions were unchanged through the later amendments.

The first focused run had 1 failure / 25 passes: its split mutation selected a unique
family, so it did not actually create leakage. The fixture was corrected to select a
shared family; the final suite adds further gates and passes 30 tests. This was not a
change of evaluation labels to make model results pass. Earlier logs/results are retained;
`baseline-v14.json`, `validation-v14.json`, `prepared-v14.json` and `submission-v14.json`
are the final evidence. Initial runs preceded implementation commits; their recorded
runner/contract hashes bind executed source bytes to the delivered implementation.

| Input | SHA-256 (LF normalized) |
|---|---|
| protocol.json | `ffba53c718a5600b7d0d03a8727a034031bcf7efb58e18b9bee2667244a7acc7` |
| tasks.json | `b3f68b5387379524b6255acc7a941f573b7b2d83f399962fd1925aac4f88bfc4` |
| annotations.json | `426a797abdde7fcfd76a0317dfd6cbb37250dd330d2fe26089faa6afed8338f8` |
| origins.json | `d63034b3bb3d41fb8c8af581614f73f28e69cb55e228703dcd4f81a3fbf2046e` |
| prompts.json | `8844533a4dccf14957562bce5b72a8b55ce1ca94120dff4056b8d7f5bdd1618a` |
| schemas.json | `588421d2ebcc464b785c428fdd653fd675ec858c530e33c84e8ec560c65b1f63` |
| metrics.json | `ad5ba48540cf0df3e0b935e9a25b1eb74d6ff25bae978a2914d621b8c5636daf` |

The complete file inventory, tool hashes and normative document fingerprints are recorded
in protocol.json. Changes require an explicit version/amendment, not silent replacement.

## Validation and safety

Evidence directory: `docs/validation/alive-notebook-03a/`.

| Check | Result | Evidence |
|---|---|---|
| Final focused infrastructure | 30 passed, 0 failed | `python-v14.txt` |
| Final targeted integration | 159 passed, 1 skipped, 1 xfailed, 0 failed; 94.95s | `python-targeted-v14.txt` |
| Full hosted suites | PENDING final record | hosted CI evidence below |
| Local Ruff check/format | PASS; 177 files formatted | `lint.txt` |
| Six extension/Node suites | 38 passed, 0 skipped | `node.txt` |
| Hugo production/built provenance | PASS, provenance OK | `hugo.txt` |
| Six archive/three protocol verifiers | PASS | `archive-protocol.txt` |
| Frozen inputs/tools/docs and protected paths | PASS | `protected-paths.txt` |
| Frozen baseline expectation comparison | PASS locally and notebook CI | `baseline-v14.json`, hosted notebook log |

The targeted skip is the existing unimplemented semantic validity judgment; the strict R3
expected failure remains unchanged. Hosted CI also covers dashboard tests/build and the
existing PostgreSQL first-contact flow. No new native browser flow or UI was implemented,
and the earlier shipped-toolbar NOT_QUALIFIED limitation is not silently upgraded.

03A execution: **0 model calls, 0 model tokens, USD 0.00**. The Core replay forbids Meta
structured calls and disables embeddings/providers; it uses in-process APIs and local Core
transport, requiring no external network with dependencies installed. Validation/scoring
are local Python/Git operations. Tests that exercise scoring use explicit offline fixtures,
not simulated provider results presented as measurements. No production Core, Governor,
approval, payment, migration, browser permission, source document/site or old frozen archive
was changed. No application memory store or retrieval algorithm was added.

## Exact prerequisites before 03B

1. Claude's independent review of this protocol, taxonomy, source evidence and scoring.
2. Independently adjudicate public draft labels and qualitative scoring expectations.
3. Collect the 12-case independent package, verify actual restricted access and exposure
   attestations, and retain gold outside the implementer's reach.
4. Resolve all five carry-forward issues through an explicit narrow contract migration:
   aggregate requested-quote status; per-source integrity precedence; asymmetric title drift;
   bounded occurrence-count scope; old historical-derived expectation checking. New 03A
   expectation checking does not silently claim to fix the old 02-R1 gate.
5. Add a reviewed single-/dual-source adapter to existing preview/authorize/analyze governance:
   resolve real owned IDs server-side; never trust fixture access fields; bind exact evidence,
   prompts/schema/model/settings and request hash; preserve cancellation/restart and budgets.
6. Freeze explicit supported model/revision/settings, tokenizer/caps and verified pricing;
   the USD 1 ceiling in this protocol is only a proposal, with authorized spend still zero.
7. Obtain separate owner approval of exact payloads and call/token/spend caps. Validate
   returned refs/quotations and independently adjudicate free-text/forbidden conclusions
   before making semantic correctness claims. Then compare C/D on matched evidence/strata.

03A is ready for review of its experimental foundation, not permission to run that experiment.

## Reproduction

```powershell
uv sync --locked
uv run python -m scripts.notebook03a validate
uv run python -m scripts.notebook03a submission
uv run pytest -q -ra tests/test_notebook03a.py
uv run python -m scripts.notebook03a prepare --output .alive/03a-inputs-review-01.json
uv run python -m scripts.notebook03a baseline --check-against docs/validation/alive-notebook-03a/expected-baselines-v14.json --output .alive/03a-replay-review-01.json
uv run python -m scripts.notebook03a score --records .alive/03a-replay-review-01.json --arm A --output .alive/03a-score-review-01.json
uv run ruff check alive migrations scripts tests site/notebook.py
hugo --source site --environment production --cleanDestinationDir
uv run python site/notebook.py check --public site/public
```

Choose unused output names; earlier evidence/frozen inputs cannot be overwritten. The sealed
package command is only for the independent custodian on the separately controlled machine:
`uv run python -m scripts.notebook03a submission --package <restricted-package-directory>`.
It validates an attestation/package, not actual filesystem privacy. Stop after the draft
PR/report. Human merge authority only. Do not begin 03B.
