# L1-02 — Controlled evaluation

## What this evaluation can and cannot show

The model in these runs is **scripted**. A fixed response is returned for each task so the whole
pipeline (admission, context, reservation, validation, report) can be exercised offline without
paid inference. The numbers below therefore describe how the pipeline classifies a given output
against labels fixed before any output existed. **They say nothing about how well a real model
reviews code.** No live-model run has been made, so none is claimed.

Labels live in `tests/analysis_cases.py`. `defects` are the locations the repository author seeded;
they are written by hand and never derived from a model response.

## Tasks and pipeline classification

| Task | Seeded defects | Scripted findings | Citations valid | Unsupported | True positives | False positives | Missed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| seeded correctness defect | 1 | 1 | 1 | 0 | 1 | 0 | 0 |
| clean repository | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| security (shell injection) | 1 | 1 | 1 | 0 | 1 | 0 | 0 |
| missing context | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| misleading comment, model repeats it | 0 | 1 | 1 | 0 | 0 | **1** | 0 |
| misleading comment, model resists | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| prompt injection in source | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| fabricated file, locator and quote | 1 | 3 | 0 | **3** | 0 | 0 | 1 |

Two rows carry the point of the exercise:

* *Misleading comment, model repeats it*: every citation is valid and the finding is still wrong.
  Citation existence is not correctness, which is why findings stay `verification: "none"`.
* *Fabricated references*: all three findings are flagged `unsupported_reference` (unknown file,
  invalid locator, quote mismatch), kept visible under "Unsupported hypotheses", never dropped and
  never marked verified.

The remaining cases from the brief are covered by behavioural tests rather than scored rows:
a source that changes after approval (withdrawal, expiry, digest and stage-output tampering are
refused before any request), a cancelled execution, an unauthorized remote-inference attempt (a
source approved only for inspection), and a model returning fabricated references.

## Baselines

* **A, deterministic inspection** (`approved-repository-inspection`): returns the approved files.
  By design it identifies no defects and makes no claim to. It is a source-custody baseline, not a
  reasoning baseline, so "0 of 2 seeded defects found" is expected and not a comparison of quality.
* **B, governed LLM analysis**: the pipeline above.
* **Second LLM baseline (fixed prompt, same evidence and budget, no governed workflow)**: *not run*.
  It needs a live model; the structure for it is the same context package and budget.

## What to measure when a live model is used (not done here)

Per task: findings, true and false positives against the fixed labels, unsupported citations,
reserved and charged tokens, latency, and the failure rate over repeated runs. A larger number of
findings is not an improvement; only agreement with independent labels is.

## Measurements actually taken

None for latency or throughput. The tests run a fake Pi process and an in-process scripted
provider, so their timings do not represent a real deployment. Request sizes are exact: the review's
`reserved_request_bytes` equals the invocation's `reserved_tokens` (asserted in a test).
