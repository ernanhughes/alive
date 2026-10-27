# ALIVE-11 — Live native intelligence qualification

Engineering: **PASS_WITH_LIMITATIONS**. Research: **BEHAVIOUR_CHANGE_DEMONSTRATED**.
Owner utility advantage is unestablished.

## Source and native isolation

Baseline: `be47e18e329a1f1d932dbce253f703048c5fd3e3` (ALIVE-10 merge).
Both qualified native journeys ran on committed source
`cb29c336760cb62e709da73a32553663ddde7e38`. Later evidence/tooling commits
retain identical product and extension code. Original preparation and historical
archives remain unchanged; the old preparation document is separately preserved.

Headful Chrome 155.0.8059.85 used fresh profiles, free owned loopback ports,
new migrated SQLite stores and restricted temporary extension copies. The panel
was a genuine docked CDP target, absent from ordinary tabs, with full-window
screenshots. The reused test-copy extension title retains ALIVE-10 wording;
recorded source/configuration and workbench are ALIVE-11. Normal profiles,
primary-checkout services and its 25 inventoried local files were preserved.

The harness waits for service-worker side-panel registration, panel DOM readiness
and a new grant after restart. These were automation races; permissions were not
broadened. See the [Chrome sidePanel reference](https://developer.chrome.com/docs/extensions/reference/api/sidePanel).
Authenticated `/api/v1/provenance` exposes source/module hashes, runtime identity
and database fingerprint without credentials or database paths. The panel records
and displays backend source. Isolated configuration excludes the older port-8000
backend; source and database identity are checked during qualification.

## Approved Meta execution

The owner separately approved eight calls, 12,000 charged tokens and $0.10
estimated spend with zero automatic retries. **All eight calls are consumed.**

| Measure | Actual |
| --- | ---: |
| Pinned model | `muse-spark-1.3` |
| Endpoint | `https://api.meta.ai/v1` |
| Calls / validated responses | 8 / 8 |
| Reported and charged tokens | 4,486 |
| Estimated cost | $0.0123425 |
| Adaptive core | 5 calls; 2,890 tokens; $0.0081035 |
| Shared matched baseline | 3 calls; 1,596 tokens; $0.004239 |

Only frozen reviewed controlled excerpts were sent; the backend retained the key.
Availability and [published pricing](https://dev.meta.ai/docs/pricing-rate-limits)
were checked before execution. Estimates use $1.25/M uncached input, $0.15/M cached
input and $4.25/M output, rather than an invoice. Calls, tokens and the optional
cumulative estimated spending cap are checked before dispatch and persisted across
restart. Conservative failure charging remains active. `budget-reconstruction.json`
is a retrospective audit, not an original live reservation receipt. Usage is
complete; no independent packet counter instrumented the real endpoint.

## Observed loop and guards

Three genuinely distinct excerpts received scripted negative ratings. Support
reached three and analysis paused. Repeated excerpts/ratings did not inflate
support. These are declared operator branch interventions, not measured usefulness.
An explicit correction analysed an authorised page. A separate zero-budget
correction returned 409 and rolled back policy/correction rows. Three stale
snapshots were rejected when a probe became due. The designated fresh probe and
scripted useful feedback produced support four, useful rate 0.25, policy v11.

Restart retained five core notes and policy v11, revoked the old grant (403) and
replayed no inference. Three baseline calls afterward were intentional new calls.
A separate cold-recall check backed up the completed original database read-only,
used a fresh browser and provider-disabled backend with USD cap zero, recalled
the exact useful Meta note, and retained eight notes and unchanged expenditure.
This backup-clone check is distinct from the original backend restart.

Wrong-origin/hash grants returned 403; duplicate analysis/budget exhaustion 409.
Expired/revoked correction grants returned 403 in isolated API probes. Existing
cancellation regression coverage remains; no extra paid in-flight cancellation
experiment was performed. Notes passed schema and exact-quotation validation,
which does not establish whole-note factual correctness. Bounded raw output and
error categories are retained; provider output-truncation exceptions expose
usage/category but no raw text. Existing Governor/provider interfaces remain.

## Honest comparison

The twelve-observation comparison uses production APIs/Governor and a synthetic
HTTP provider. Labels describe source adequacy, not owner usefulness.

| Policy | Calls | Synthetic tokens | Adequate opportunities met | Missed |
| --- | ---: | ---: | ---: | ---: |
| Adaptive | 7 | 1,050 | 4 | 2 |
| Frozen nonadaptive | 11 | 1,650 | 6 | 0 |
| Constant analysis | 12 | 1,800 | 6 | 0 |

Thirty synthetic requests cost $0 paid; formula estimates are $0.0023625,
$0.0037125 and $0.00405. Fewer calls came with false abstentions. An irrelevant
fixture containing a negated matching word still triggered lexical relevance;
the negative result was preserved without tuning the corpus.

The three real native baseline analyses match excerpt and goal instruction.
Frozen nonadaptive and constant policies request the same three relevant cases
and share one response set: they are not independent arm replications. Probe
metadata can differ from adaptive requests; entire prompts are not claimed
identical. No utility or statistical superiority is established. Historical
ALIVE-08's negative result is unchanged.

## Checks and reproduction

Qualified source passed 142 backend tests, seven frontend tests, eight extension
tests, dashboard production build and Ruff lint/format. Both docked native journeys
passed. Windows emitted existing ZeroMQ selector warnings. Native persistence used
SQLite; PostgreSQL regression is a separate CI job.

From a clean checkout with dependencies and headful Chrome available:

```powershell
uv sync --locked
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
uv run pytest -q
npm ci --prefix dashboard
npm test --prefix dashboard
node --test tests/extension-panel.test.cjs tests/extension-background.test.cjs
npm run build --prefix dashboard
uv run python -m scripts.native11 --provider synthetic
uv run python -m scripts.native11_compare
```

Synthetic commands create owned `.alive` artifacts and require no Meta key.
The paid harness additionally requires `--provider meta --allow-paid
--credentials-env-file <ignored-local-file>` and separate approval. Do not rerun
it under the exhausted campaign allowance. Zero-inference recall accepts a prior
completed run directory: `uv run python -m scripts.native11_recall <prior-run>`.
The exporter refuses to overwrite an existing archive.

[Evidence archive](../archives/ALIVE-11/qualification-v1/README.md),
[offline three-minute replay](../archives/ALIVE-11/qualification-v1/demo.html),
[storyboard](ALIVE-11-DEMO.md) and [handoff](CODEX-ALIVE11-HANDOFF.md) preserve
results and boundaries. Replay uses actual screenshots, not live footage.
Publication is review-only. ALIVE-12 remains deferred.
