# PI-02B controlled mutation report

Run: `python -B -m scripts.workflows_execution_mutations` on 2026-10-30.
The opt-in pytest plugin mutates a single guard per subprocess; application files
are not rewritten. Each selected test first passes without its mutation. A nonzero
exit only counts as a kill with a relevant assertion failure, never collection/setup
failure. Full per-probe test names, exits and assertion excerpts are in
[mutations.json](validation/pi02b/mutations.json).

| Mutation | Guard removed or weakened | Baseline | Outcome |
| --- | --- | --- | --- |
| dispatch_fence | Current authority at existing Pi dispatch marker | PASS | KILLED: actual revoked reservation must make zero upstream requests |
| operation | Owner's permitted literal operation set | PASS | KILLED: unapproved operation admitted |
| hash | Immutable definition hash revalidation | PASS | KILLED: changed definition reached execution |
| claim | Atomic unique execution owner | PASS | KILLED: independent claims repeated work |
| budget | Owner/definition ceiling comparison | PASS | KILLED: widened grant admitted |
| admission | Exact claimed stage before model reservation | PASS | KILLED: bad owner reached reservation/dispatch |
| pi_success | Required complete Pi success receipt | PASS | KILLED: uncertain receipt completed stage |
| ambiguity | Conservative possible-effect recovery | PASS | KILLED: interrupted effect lost UNKNOWN classification |
| output | Declared output schema enforcement | PASS | KILLED: extra output field accepted |
| evidence | Owned approved context scope | PASS | KILLED: wrong-goal context authorized |
| replay | Completed historical execution short-circuit | PASS | KILLED: replay altered completed state |

Final result: **11 passing baselines, 11 killed mutations, zero survivors**.
These probes establish sensitivity of specific tests, not proof of every possible
interleaving or semantic safety. Real-runtime qualification and manual boundary
review remain necessary. Earlier detector/AnyIO harness issues and their corrections
are disclosed in the qualification report.
