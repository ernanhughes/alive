# ALIVE-NOTEBOOK-02 — engineering and research report

Decision: **READY_FOR_INDEPENDENT_REVIEW** for a deterministic integrity/abstention
baseline. **Semantic qualification NOT DEMONSTRATED. Model arm C NOT RUN.**
The measured policy does not retain useful semantic connections and is not ready to
replace the companion's lexical connection workflow.

## Reproducibility and scope

Baseline: `937bdcdadd82e5fa5035a57ebe564318557621e0` (merged Notebook-01 and R1).
Branch: `codex/alive-notebook-02-evidence-qualification`; isolated worktree:
`C:\Projects\alive-notebook-02`. Design/cases/labels were frozen in `bb12ad5` before
implementation or comparison. `ef1090a` changes only checksum newline normalization for
cross-platform checkouts; no labels or cases changed. Protocol:
`evaluations/notebook02/protocol.json`. Environment: Windows 11, Python 3.13.3,
Hugo 0.165.0, uv-locked dependencies. Exact runtime file hashes and execution commit are
in `docs/validation/alive-notebook-02/evaluation.json`. Execution initially preceded the
implementation commit; hashes bind the executed files to the delivered implementation.
Implementation commit: `1a2cbe4`. Final independent-review head (including report/evidence)
is supplied in the draft PR and delivery message.

## Implementation

A read-only Core service (`alive/evidence_qualification.py`) and typed endpoint
`POST /api/v1/browser-experience/research/qualifications` operate after existing retrieval.
The request contains current snapshot ID, memory ID, versioned policy and optional exact
quote selections. Historical source text cannot be supplied as authoritative evidence.

The service resolves the existing WebExperience rows under the Core lock/session,
revalidates the live current grant, instance/goal/active-memory scope, binds retained
historical excerpts to original captured snapshots, hashes full stored source text and
validates exact bounded quote offsets. It checks current grant URL/goal bindings and
supported capture versions. Current and historical display budgets are each 2000 characters.
Historical saved evidence does not require the former tab's grant to remain live.

Authorization failures use an identical generic 404/error message for missing, foreign,
wrong-goal, withdrawn or revoked evidence (normal per-request correlation IDs still vary).
No unauthorized historical references or metadata are returned. Results are not persisted
or cached: each call revalidates current state; withdrawal/revocation cannot be bypassed
with an old qualification ID. Existing startup grant revocation is preserved, so restart
requires fresh page consent/capture. No approval or restart system was modified.

Separate dimensions record authorization, source integrity, relevance, claim relationship,
applicability, currency and sufficiency. The latter semantic dimensions remain unknown.
Intact authorized evidence produces `abstain`; missing/inconsistent backing evidence or
invalid selected quotes produces `qualified_non_use`. `candidate_connection` is reserved
in the contract and never emitted by this policy. Responses include exact authorized source
references, version/provenance, reason codes, limitations and a suggested research action.
There is no collapsed confidence score. Source quote verification is explicitly not factual
truth or external source authentication.

No new retrieval algorithm, database, extension host, source fetching, semantic keyword
rules, UI migration or provider path was added. The existing lexical endpoint/ranking and
strict R3 xfail are unchanged. New CI runs the frozen comparison after notebook checks.
See `ALIVE-NOTEBOOK-02-DESIGN.md` for the API map, data flow, architecture decision,
implementation plan, risks and future governed semantic adapter requirements.

## Frozen comparison

20 pairs: 8 development (R1–R4 plus 4 synthetic pairs) and 12 synthetic held-out pairs.
Labels and origin annotations are separate files; only IDs, policy and quote selections
reach the service. Labels are loaded for scoring after runtime outputs are produced. Cases
use opaque numeric IDs. No expected labels or explanatory metadata enter source requests.
The runner verifies frozen input hashes before it starts.

A uses the **actual legacy connection API**, B the new qualifier, D a constant abstain
control with identical source access, C NOT RUN. A and B see the same fixed candidate pair
and comparable bounded evidence. No ranking change is attributed to qualification. A legacy
lexical candidate is not counted as a substantive semantic relationship assertion. D is an
explicit trivial control, not an implemented semantic reasoner. The unavailable-backing-source
case is an operational synthetic perturbation; the retained excerpt still exists, but its
original-snapshot reference cannot be resolved. The source availability distinction is real
and is not classified as semantic reasoning.

| Split/arm | Candidate connections | Correct non-use/abstention on negatives | Missed useful substantive relations | Supported substantive relation precision |
|---|---:|---:|---:|---|
| Development A | 8/8 | 0/3 | 5/5 | undefined: 0 substantive findings |
| Development B | 0/8 | 3/3 | 5/5 | undefined: 0 substantive findings |
| Development D | 0/8 | 3/3 | 5/5 | undefined: 0 substantive findings |
| Held-out A | 12/12 | 0/7 | 5/5 | undefined: 0 substantive findings |
| Held-out B | 0/12 | 7/7 | 5/5 | undefined: 0 substantive findings |
| Held-out D | 0/12 | 7/7 | 5/5 | undefined: 0 substantive findings |

A keeps candidates for all five useful held-out pairs, along with seven negative-label
pairs. Its candidate/usefulness label precision is 5/12 (41.7%); this is a diagnostic,
**not semantic relation precision or seven false factual assertions**. B and D retain none
of those useful candidates. Thus the apparent negative-case abstention gain is fully
explained by declining every semantic judgment. **No useful reasoning advantage over D
was demonstrated.** B's additional contribution is permission/source integrity checking
and structured non-use reasons, not relation classification.

The 11 complete-source held-out pairs were also reversed and given identical lexical
source distractor sentences. A still yielded 11 candidates; B/D declined all 11, missing
all five useful relations. The missing-original case was excluded from these diagnostics
as predeclared. Usefulness labels are symmetric and reused; no directional supersession
metric is inferred from reversed examples. Latencies (single local observations) and exact
per-case evidence are recorded in evaluation.json. Quotes are checked at recorded offsets
against authorized retained inputs as a hard gate, not averaged into semantic performance.

## R1–R4 findings

- **R1:** earlier ALIVE-12 evidence is available; B abstains with unknown relationship and
  currency. It does not independently identify the documented labeling-policy correction.
  Useful relationship missed; supersession understanding NOT DEMONSTRATED.
- **R2:** B preserves the source references/quotes and declines a universal/contradiction
  judgment. It does not extract or compare comparator/corpus/conditions. Complete comparator
  descriptions may be absent from the bounded chapter excerpts. Useful scoped comparison
  missed; scope reasoning NOT DEMONSTRATED.
- **R3:** B abstains without any rule for `paid`/`calls`, or any global vocabulary changes.
  This is conservative policy, not recognition that these specific experiments are unrelated.
  The legacy strict xfail continues to describe legacy behavior.
- **R4:** B abstains on the misleading title with intact underlying captures; it never invokes
  the notebook front-matter checker and does not trust matching hashes as semantic truth.
  It does not detect the mismatch. The unfamiliar held-out universal water/climate
  generalizations likewise receive abstentions, not semantic mismatch findings. A missing
  original capture gets qualified non-use. General presentation-integrity understanding is
  NOT DEMONSTRATED.

Labels were prepared by the implementer, not independently annotated by Claude or the
owner. The held-out set was not used for policy tuning, but its author is not independent.
Small synthetic, mostly lexical examples cannot establish statistical or real-world
research usefulness. Source-order/distractor stability of an all-abstain policy is trivial.

## Validation and evidence

Paths below are under `docs/validation/alive-notebook-02/`.

| Check | Result | Evidence |
|---|---|---|
| Qualifier focused tests (initial 29 cases) | 29 passed, 0 failures | `python-focused.txt` |
| Final targeted qualifier/notebook/research suites | 116 passed, 1 skipped, 1 xfailed, 0 failed; 127.42s | `python-targeted.txt` |
| Full Python | 448 passed, 7 skipped, 1 xfailed, 0 failed; 503.69s | `python-full.txt` |
| Six Node suites | 38 passed, 0 failed, 0 skipped | `node.txt` |
| Dashboard tests and production build | 7 passed; build PASS | `dashboard.txt` |
| Ruff check/format | PASS, 173 files formatted | `lint.txt` |
| Hugo production / built provenance | PASS, provenance OK | `hugo.txt` |
| Six archive and three protocol verifiers | PASS | `archive-protocol.txt` |
| Frozen A/B/D comparison, C NOT RUN | 42 pair executions; quote gates PASS | `evaluation.json`, `evaluation-summary.txt` |
| Hosted implementation CI | SUCCESS, all five jobs; Ubuntu/Windows each 448 passed, 7 skipped, 1 xfailed | `hosted-ci.json`, `hosted-notebook.txt` |

Hosted implementation [run 40780798558](https://github.com/ernanhughes/alive/actions/runs/40780798558)
tests commit `1a2cbe4aa36ff3cc5be0cedfa92690e2bd414fa6`. The notebook job concluded
success: production Hugo/provenance, existing Python notebook tests (30 passed, 1 skipped,
1 xfailed), Node capture (2 passed, 0 skipped), and the frozen Notebook-02 comparison all
executed. Dashboard and PostgreSQL first-contact jobs also concluded success. Both backend jobs
passed: Ubuntu 448 passed / 7 skipped / 1 xfailed in 303.34s; Windows 448 passed /
7 skipped / 1 xfailed in 627.07s. The full run concluded **success**. These conclusions
identify the tested implementation commit; subsequent documentation-only commits trigger
separate runs and are not silently attributed the earlier conclusion.

Focused test development initially exposed test-harness assumptions: wrong retrieval-score
field/error envelope, foreign-key-invalid fixture edits and attempted concurrent runtime
ownership. After correcting those fixtures, recovery correctly refused a pre-restart grant;
the test now explicitly obtains fresh consent instead of weakening that protection. Initial
run: 8 failed / 21 passed; intermediate run: 1 failed / 28 passed; the 29-case focused run
then passed. Five additional cases cover foreign current evidence, cross-goal backing
sources, bounded quotes, frozen-label tampering and absence of persistent qualification
writes; final targeted/full results above include them. No expected evaluation labels or
runtime semantic policy were tuned to these outputs.

No browser-native migration was performed or required for this backend-only integration.
The companion and shipped manifest/config are unchanged. The existing Notebook-01 shipped
toolbar acceptance remains **NOT QUALIFIED**; no model/native semantic qualification is claimed.

## Security, costs and remaining work

Targeted adversarial coverage: missing/foreign/wrong-goal/withdrawn memory; missing/revoked/
expired/incorrectly bound current grants; capture/retained-excerpt/hash/title/version drift;
hallucinated/out-of-budget quotes; untrusted instructions and unfamiliar unsupported claims;
unknown/provider request fields; unauthenticated access; restart and fresh-grant behavior;
label-hash tampering; no qualification persistence. Provider and governed-analysis entry
points are instrumented to raise if the qualifier reaches them.

Runtime/evaluation model calls **0**, tokens **0**, paid inference **USD 0.00**. No prompts
or model versions were executed for arm C; provider/model fields are null. There is no new
external dispatch path. Existing ResearchRelationships governance is assessed in the design
as the future boundary: exact payload preview/approval, budgets, cancellation/restart,
structured output and exact quote validation must all be retained. An unexecuted future
proposal is not live model qualification.

Original docs, notebook chapters, research ranker/memory code, frozen archives/experiments,
Governor, approval/payment/budget systems and browser host permissions are unchanged.
Review the service/route/evaluation/tests and the hard gate results before deciding whether
to authorize a separately governed semantic experiment. Do not migrate the UI or claim
that ALIVE understands supersession, scope, contradiction or misleading presentation.

## Reproduction

```powershell
uv sync --locked
uv run pytest -q -ra tests/test_evidence_qualification.py tests/test_notebook_01.py tests/test_research_memory.py
uv run pytest -q -ra
uv run ruff check alive migrations scripts tests site/notebook.py
uv run ruff format --check alive migrations scripts tests site/notebook.py
hugo --source site --environment production --cleanDestinationDir
uv run python site/notebook.py check --public site/public
npm ci --prefix dashboard
node --test tests/extension-background.test.cjs tests/extension-panel.test.cjs tests/extension-capture.test.cjs tests/extension-live-background.test.cjs tests/extension-live-companion.test.cjs tests/notebook-capture.test.cjs
npm test --prefix dashboard
npm run build --prefix dashboard
uv run python -m scripts.notebook02_evaluation
```

The comparison creates an isolated `.alive/notebook02-eval-*` SQLite database/workspace;
it never uses the owner's database. Repeated outputs have stable policy outcomes/counts,
while UUIDs and latency vary. Integrity gates fail the runner on frozen-input or quote drift.
Stop after the draft PR/report for independent Claude review. Human merge authority only.
