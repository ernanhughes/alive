# PI-02B-H / R3 focused independent-review handoff

Base is merged #69 at `c4257e0393b98c3cd81453903e701de389185fcb`, whose tree equals
reviewed `ab066db51d3992905980aa5a1122c6e540bd1335`. Pin the new PR head reported
in its body. Read the [bounded report](ALIVE-PI-02B-H-R3.md) and preserved independent
R2/R3 inputs. No independent approval is claimed by this document.

Review scope:

1. Verify the production diff is exactly `except (Refused, TimeoutError):` replacing
   `except Refused:` around the stage adapter. No Pi/Governor/database/dispatch/recovery
   or dependency changes should appear.
2. Run the 19 new tests and ensure actual pinned Pi is used for model paths. Verify
   after-dispatch timeout remains UNKNOWN with ambiguous request/unknown_outcome;
   before-dispatch timeout remains FAILED with rejected request and zero calls.
3. Remove each of the 12 required guard clauses individually. The matching test must
   fail an intended assertion, never setup/teardown. Revert the timeout line for its
   counterfactual; whole-run deadline behavior must remain intact.
4. Verify real-route goal cancellation, one model invocation per stage, exact browser
   scope and zero outstanding reservations. Replay/recover must not add calls.
5. Inspect the raw-SQL identity tests as controlled inconsistent-record checks, not
   a claim that database corruption is a supported public attack path.
6. Rerun `scripts.workflows_r2_mutations`: require the existing 20 kills/one redundant
   unchanged plus 13 R3 kills. Read failed assertion excerpts, not only exit codes.
7. Confirm existing tests were not rewritten, frozen review inputs are unchanged,
   and both exact-head CI workflow runs are green. Full discovery must include
   `alive/intelligence/tests`, not just the older selector's explicit root-file list.
8. Review the retained inquiry-state guard and unresolved role-contract watch item.
   Do not manufacture a lifecycle test by bypassing the Governor with SQL.

The earlier independent-service concurrency exploration is outside this one-line
correction and is explicitly not presented as passing proof for a future worker
framework. Its row-lock proposal was removed; unsupported-service diagnostics remain
separate. Decide any additional behavior change in a separate reviewed scope.

No automatic merge. PI-02C code starts only after this hardening change is independently
approved and integrated. Report concrete failing scenarios and exact source locations.
