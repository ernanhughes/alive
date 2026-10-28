# ALIVE-INTEL-I1A-PARTIAL-CLAUDE-REVIEW

**Branch:** `feature/alive-intel-i1a-claim-foundation` @ `2631e59a9fa69e0c2950510d7bbeaa088b0c7b6e`
**Base:** `main` @ `88cd0be`. Not yet merged. Open-PR state is unknown, because the GitHub API is unavailable to this session.
**Date:** 28 October 2026. Read-only review: local runs and a scratch-copy patch only. Nothing was pushed.

## Verdict: **REVISE. One blocker, two correctness defects, one test-design gap.**

The PR's own status line is honest: "I1-A ready for I1-B: NO". That still holds.

The structure is a real improvement over C1A:
- explicit spans and offsets;
- structured `reliance`;
- the negation and qualifier sets;
- a tightened marker lexicon;
- the novel-basis and aspect rules;
- the `retained` annotation.

The anchor fix (checking the chosen occurrence) is correct.

## Tests run on the branch (these were UNRUN per the PR; now run)

| Run | Result |
|---|---|
| `uv run pytest -q` (full suite) | **274 passed, 6 skipped, 0 failed** (212.7 s; Linux, Python 3.13.18, SQLite) |
| Branch validator, C1A and anchor tests | 17/17 pass |
| Adversarial suite (`i1a_attacks.py`, 18 cases) on the branch **as-is** | see B1 |
| Same suite with the **reviewer patch** (`i1a-validator-fixes.patch`) | all cases behave correctly; the branch's 17 tests still pass, with the patched module verified as the one imported |

**Not run:** PostgreSQL, Windows, native Chrome, `node --test` (the extension is unchanged by this branch).

## Findings

### B1. BLOCKER (reproduced): the start-boundary regex never matches

`alive/claim_comparison.py` L75 is `re.search(r"[.!?]\\s+$", before)`. In a raw string, `\\s` is a literal backslash followed by `s`. As a result, **any quote not at excerpt position 0 or after `\n` is rejected**, and the observer never emits `\n`.

Consequences on the branch as-is:
- the `utcnow` golden case (anchor mid-excerpt) is **rejected**;
- every realistic mid-page quote is rejected;
- several adversarial "passes" (e.g. the `i.e.` negation-shedding case) pass **only by accident**.

The commit that introduced it, `2631e59` ("simplify sentence boundary regexes"), is the last one on the branch.

**Fix:** `r"[.!?]\s+$"`. The other regexes on L78, L83 and L84 use single backslashes and are correct.

### D1. MAJOR (reproduced after fixing B1): wrong-entity supersession when only the *next* entry is deprecated

The nearest-marker rule correctly demotes the case where both `utcnow` and `utcfromtimestamp` are deprecated. But if the newer page does **not** deprecate `utcnow` while the following entry (`utcfromtimestamp`) is deprecated, the first marker after the anchor belongs to the wrong entry, and it is **accepted** as `explicit_supersession` of `utcnow`. The PR text correctly anticipates this.

**Fix (interim, labelled heuristic; in the patch):** demote with `another_subject_between_anchor_and_basis` when an API-signature pattern (`classmethod|staticmethod|class|method|function|attribute|property|exception <identifier>`) appears between the anchor's end and the basis.

- **Result:** both wrong-entity variants are demoted; the golden case is still accepted.
- **Residual:** this is specific to the documentation format, and prose such as "class attribute" causes safe false demotions.
- **Structural fix:** capture-v2 must emit entry boundaries (`dt`/`dd`, headings as `\n`-separated blocks), and the rule should become "no block-level entry boundary between anchor and basis". Keep the signature guard as defence in depth.

### D2. MINOR (reproduced after fixing B1): over-strict starts cause false abstentions

| Problem | Example | Fix (in the patch) |
|---|---|---|
| L78 `\d\.\s*$` rejects any sentence that follows one ending in a number | "Benchmarked in 2024. The cache is slower." | Block only when the boundary sits between digits: `\d\.$` before **and** a digit at `start` |
| L77 `prefix.endswith(a)` matches word endings | "piano." matches `no.` | Compare the last whitespace-delimited token against the abbreviation set |

### T1. MAJOR (test design): the tests cannot see real captures

Every new test places quotes at position 0 or joins sources with `"\n"`, which are the only two paths that bypass B1. `extension/observer.js` collapses all whitespace into single spaces, so production excerpts never contain `\n`.

Requirement: every validator and anchor test must include a **space-joined, mid-excerpt** variant. Once capture-v2 lands, add one built from real observer output. The reviewer's `i1a_attacks.py` cases should be committed as `tests/test_claim_validator_v2_adversarial.py`.

### Confirmed correct on this branch

- Anchor validates the **chosen** occurrence (`research_memory.py` L343).
- Duplicates without an offset are rejected.
- Negation and qualifier asymmetry (`cannot`, `only`) are rejected.
- A negated or irrelevant marker ("not deprecated", "error correction") is demoted.
- Supersession on the `behaviour` aspect is demoted.
- Bidi and control characters are rejected.
- Forged basis via injected "SYSTEM:" text is demoted.
- The `retained` annotation is correct.

## Remaining I1-A scope (unchanged from the PR's own list)

These items are still blocking:
- the eight `ResearchRelationships` seams;
- `local_fixture_claim` and the `alive_claim_meta_enabled` 403 gate;
- anchor HTTP status mapping (422 vs 409);
- durable probe tests (C-real, D, E, F) plus a leak scanner;
- the claim-mode end-to-end test.

Capture-v2 belongs to I1-C, but D1's structural fix depends on it.

## Recommended next commit on this branch (small)

1. Apply `i1a-validator-fixes.patch` (B1, D1 interim, D2), or the equivalent.
2. Add `tests/test_claim_validator_v2_adversarial.py` from `i1a_attacks.py` with the expectations shown (treat the `3.` truncation case as **rejected**, which is correct fail-closed). Add space-joined, mid-excerpt variants of every existing test, and a regression test for the B1 regex specifically ("First sentence here. Second sentence is fine." must be bounded).
3. Then proceed to the seams per the INTELLIGENCE-01 review §12.

**Gate:** do not start the seams until the adversarial file passes on the branch without the scratch patch, i.e. with the fix committed.
