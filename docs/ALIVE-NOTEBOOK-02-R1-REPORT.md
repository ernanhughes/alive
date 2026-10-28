# ALIVE-NOTEBOOK-02-R1 — review corrections

Recommendation: **READY_FOR_REVIEW**. Semantic qualification remains **NOT DEMONSTRATED**;
model-assisted qualification remains **NOT RUN**. No Notebook-03 work is included.

Baseline: `7bae6eb56806f587bf4d6dd2692041ab5239b496` (merged PR #43).
Branch: `codex/alive-notebook-02-r1-review-corrections`.
Implementation: `5216d26b988b1781bf7f41b3c290fdcddbdad9ee`.
Environment: Windows 11, Python 3.13.3, Hugo 0.165.0; uv-locked dependencies.
Final review head, including evidence, is identified in the draft PR and delivery message.

## M1 — requested quotes versus automatic display context

The previous `reference()` chose the first 300 characters when a caller omitted a quote
and reported it as a verified quotation. The revised response distinguishes
`selection_method: automatic_excerpt` with `displayed_excerpt` from `caller_quote` with
`quote`, exact-match offsets and match metadata. Automatic excerpts have null quote,
quote offsets and `quote_exact`, and cannot acquire quote-verification status by extraction.

`quotes_requested` means at least one non-null quote selection was supplied. With no quote
request, `source_quotes_verified` is **null**, including when evidence is unusable. With
requested quotes, it is true only when the pair is usable and the requested matches pass;
otherwise false. A single supplied quote does not imply that the other source's automatic
excerpt was requested or verified: per-source selection metadata distinguishes them.
Repeated/overlapping exact matches report their occurrence count and explicitly select the
first match. No uniqueness, semantic relevance or factual validity is inferred.

The operation policy remains `evidence_qualification_v1`; the revised response explicitly
identifies `response_contract_version: evidence_qualification_v1.1`. Consumers must adapt
to nullable quote fields and the title relocation. The existing browser UI does not call
this new endpoint and is unchanged.

## M2 — separate trust dimensions

`displayed_title` now appears only within `untrusted_presentation`, with
`integrity: not_bound_to_capture_hash` and `semantic_validity: unestablished`. Matching
memory/snapshot title metadata does not cryptographically bind a title to the body.

Retained source-text integrity and requested-quote matching are separate: an altered
requested quotation can fail while the retained text integrity still passes. The sufficiency
reason then identifies `requested_quote_unverified`. A misleading-title adversarial case
has an unchanged body hash and valid requested quote while its title remains explicitly
untrusted. No semantic mismatch detection is claimed.

The capture hash algorithm, persisted rows and source identities are unchanged; no
migration is needed. Hashes check consistency **within the existing database trust boundary**,
not independent source authenticity or factual truth.

## M3 — output-derived evaluation and historical preservation

The old missed-useful-substantive-relationship count was always set to the number of
positive labels. It is retired rather than renamed. The corrected scorer classifies the
recorded API actions and separately computes useful candidate retention/recall, unsupported
candidate rate, correct abstention, false abstention and integrity rejection (including
useful/negative-label breakdowns). Unknown actions fail rather than being guessed.

Useful recall = useful candidates emitted / useful labels. Unsupported candidate rate =
negative-label candidates / all emitted candidates; negative candidate rate separately uses
all negative labels. Correct/false abstention count explicit abstain actions on negative/
positive labels. Integrity rejection is separate from abstention. Useful candidates lost =
useful labels minus actual retained useful candidates. These are author-prepared usefulness
labels, not proof of false factual assertions or independent relation truth.

| Held-out arm | Useful retained / recall | Unsupported candidates / rate | Correct abstention | False abstention | Integrity rejection |
|---|---|---|---:|---:|---:|
| A, unchanged lexical baseline | 5/5; 100% | 7/12; 58.3% | 0 | 0 | 0 |
| B, conservative qualifier | 0/5; 0% | 0 emitted; rate undefined | 6 | 5 | 1 negative-label case |
| D, constant abstain control | 0/5; 0% | 0 emitted; rate undefined | 7 | 5 | 0 |

Both B and D lose all five useful held-out candidates. B's six correct abstentions plus
one integrity rejection account for the seven negative cases; they are no longer conflated.
The lexical baseline retains useful candidates as well as negative-label candidates. Its
candidates are not substantive factual findings. No semantic or research-usefulness gain
is established by refusing every intact pair.

Original frozen inputs under `evaluations/notebook02/`, prior recorded evidence under
`docs/validation/alive-notebook-02/`, and the original design/report remain unchanged.
The new `historical-derived.json` rescores those original actions without executing any arm,
records the original artifact's LF-normalized hash, original execution commit, frozen input
hashes and scorer hash. It does not retrospectively repair old quote-verification claims.
The fresh `evaluation.json` separately records corrected-contract runtime outputs and file
hashes. Both produce the same action-derived counts above. All 42 pair executions retain
the fixed source sets, original labels and predeclared source-order/distractor diagnostics.

The CLI now defaults to the R1 evidence directory and refuses to overwrite the original
archive, even when explicitly asked. Portable metric summaries use repository-relative
paths (or `external-output/<filename>` outside the checkout). Runtime warning streams are
stored separately from the portable stdout summaries. Historical logs containing old local
paths remain preserved as historical evidence.

## Additional regression and scope checks

The allowlist regression makes the snapshot URL and live grant URL match an unlisted origin;
qualification must still return the generic 404. This isolates the current-URL allowlist
condition that the prior mismatched-URL test did not protect. An ephemeral in-memory
mutation probe confirmed the regression fails when only that condition is removed; no
production file was altered. Its first invocation failed collection because the standalone
file lacked the repository import path; rerunning with `uv run python -m pytest` passed
both the original regression and mutation-kill check. The initial collection log is retained.

Tests cover absent/exact/altered/repeated/overlapping quotes, both-source explicit quotes,
untrusted misleading titles, separation of quote/text integrity, output-sensitive metric
counts, separate integrity rejection, unknown actions, historical derivation provenance,
portable paths and archive overwrite refusal. The existing permission/withdrawal/restart
coverage remains. Existing R3 strict xfail and lexical ranking/baseline code are unchanged.

No provider integration, paid inference, Governor/approval/payment change, migrations,
Chrome UI work, broadened browser permissions, canonical documentation rewrites or frozen
experiment changes. All new execution uses the existing isolated SQLite evaluation harness.
Calls **0**, tokens **0**, cost **USD 0.00**; model arm C **NOT RUN**.

## Validation and evidence

All paths below are under `docs/validation/alive-notebook-02-r1/`.

| Check | Result | Evidence |
|---|---|---|
| Focused qualifier/scorer regressions | 47 passed, 0 failed | `python-focused.txt` |
| Final targeted qualifier/scorer/notebook/research suites | 129 passed, 1 skipped, 1 xfailed, 0 failed | `python-targeted.txt` |
| Full Python | 461 passed, 7 skipped, 1 xfailed, 0 failed; 906.54s | `python-full.txt` |
| Ruff check / format | PASS, 174 files formatted | `lint.txt` |
| Allowlist mutation probe | original regression passes; deleting only the allowlist condition is killed (2 probe checks passed) | `allowlist-mutation.txt` |
| Six Node suites | 38 passed, 0 skipped | `node.txt` |
| Dashboard tests / production build | 7 passed; build PASS | `dashboard.txt` |
| Hugo production / built provenance | PASS, provenance OK | `hugo.txt` |
| Six archive / three protocol verifiers | PASS | `archive-protocol.txt` |
| Historical corrected derivation | PASS; no arm execution or source rewrite | `historical-derived.json`, `historical-summary.txt` |
| Fresh corrected-contract comparison | PASS, 42 pairs; no requested quotes, verification null | `evaluation.json`, `evaluation-summary.txt` |
| Hosted implementation CI | SUCCESS, all five jobs; Ubuntu/Windows each 461 passed, 7 skipped, 1 xfailed | `hosted-ci.json`, `hosted-notebook.txt` |

Hosted [run 40785595292](https://github.com/ernanhughes/alive/actions/runs/40785595292)
concluded **success** on implementation `5216d26`: notebook, dashboard, PostgreSQL,
Ubuntu backend and Windows backend all passed. Ubuntu recorded 461 passed / 7 skipped /
1 xfailed in 304.77s; Windows recorded the same counts in 467.28s. The notebook job ran
both fresh and historical-derived reproductions and emitted portable artifact names.
Final documentation/evidence commits trigger separate runs; their status is not inferred
from this observed implementation conclusion.

The targeted skip is the existing unimplemented semantic validity judgment. The strict
expected failure remains the legacy R3 non-abstention limitation. Initial focused tests
preceded the final quote/text-dimension separation; the final targeted/full runs validate
that separation. New evidence records file hashes because initial execution preceded the
implementation commit. No semantic tests or labels were tuned to improve the result.

## Reproduction

```powershell
uv sync --locked
uv run pytest -q -ra tests/test_evidence_qualification.py tests/test_notebook02_r1_evaluation.py tests/test_notebook_01.py tests/test_research_memory.py
uv run pytest -q -ra
uv run ruff check alive migrations scripts tests site/notebook.py
uv run ruff format --check alive migrations scripts tests site/notebook.py
hugo --source site --environment production --cleanDestinationDir
uv run python site/notebook.py check --public site/public
uv run python -m scripts.notebook02_evaluation --derive-from docs/validation/alive-notebook-02/evaluation.json --output docs/validation/alive-notebook-02-r1/historical-derived.json
uv run python -m scripts.notebook02_evaluation
```

The notebook hosted job runs both the fresh comparison and historical derivation. Exact
provider/model names and semantic prompts are inapplicable: no model arm was run. Native
Chrome qualification is unchanged and is not claimed by these backend corrections.
Human merge authority only; stop after the draft PR/report for independent review.
