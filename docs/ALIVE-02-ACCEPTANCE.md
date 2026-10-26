# ALIVE-02 — The First Autonomous Thought

Qualified locally on **26 October 2026**, on `codex/alive-02-cognitive-society`. Baseline: `3a73a72139b00b447394812c403b1a742094a641` on `codex/alive-01`, confirmed by read-only remote inspection as pushed to that remote feature branch. `main` remained at its initial commit. Existing untracked `models.txt` is preserved and excluded from the ALIVE-02 commits. No push, merge or deployment was performed.

The final local HEAD and exact worktree status are returned in the completion message; `git rev-parse HEAD`, `git log -2 --oneline` and `git status --short` reproduce them. The original ALIVE-01 history is unchanged.

## Delivered implementation

- Event-driven, persistent cognitive observations, world snapshots, attention scores, auction decisions and existing-store goal formation.
- Three bounded structured Meta roles (Observer, Proposer, Critic), deterministic Investigator/Evaluator/Governor, typed protocol and actual inspectable inputs/outputs/usage.
- Hard request/investigation/session/experiment ceilings, one worker, bounded queue/depth/tools/wall time, zero hidden retries, cancellation and conservative interruption accounting.
- Real native Meta Model API inference and model access discovery, with safe classified errors and backend-only credentials.
- Real pinned local MiniLM ONNX inference, PostgreSQL cosine and hybrid retrieval, compatible model-space provenance and explicit full-text fallback.
- Preview/approval/deduplication/revocation for explicitly supplied history entries; no automatic personal-history import.
- Controlled laboratory scenarios for relevant information, contradictory evidence and irrelevant noise, observed through a real managed-Chrome DOM sensor.
- Class A internal effects, Class B controlled-draft approval, rejection/cancellation/idempotency and unsupported Class C enforcement.
- Validated, queryable/exportable experience records, reward decomposition and deterministic evidence replay.
- Existing React observatory extended with Cognition control, current objective/uncertainty/roles, budgets, attention auction, structured society messages, world evidence, action review and experience.
- Reproducible live acceptance, retrieval verification, A/B/C + no-Critic benchmark, tests, Windows startup readiness and CI configuration.

## Integration classification

| Integration | Classification | Evidence |
| --- | --- | --- |
| PostgreSQL persistence, identity, events, goals | VERIFIED LIVE | PostgreSQL **16.8**, migration **0003**, retained original identity/history |
| ZeroMQ publisher/subscriber and recovery | VERIFIED LIVE | Existing independent socket/reconnect tests, persisted cursor replay, both live acceptance demonstrations |
| Meta Model API | VERIFIED LIVE | Authenticated catalog confirmed `muse-spark-1.3`; native structured output, actual reported usage/latency |
| Autonomous attention/society and Class A outcome | VERIFIED LIVE | Actual browser mutation initiated model calls without a chat prompt and wrote a traceable analysis memory/experience |
| Noise suppression | VERIFIED LIVE | Controlled page mutations produced ignored bids and **zero** model calls |
| Contradictory evidence | VERIFIED LIVE | Model-generated proposal/critique plus deterministic measured-source comparison and retained verdict |
| Local embedding inference and PostgreSQL vector/hybrid search | VERIFIED LIVE | 384-dimensional ONNX vectors; live pgvector cosine query and hybrid retrieval on approved synthetic imports |
| Class B approval and Class C denial | VERIFIED WITH CONTROLLED FIXTURES | Browser E2E used controlled role proposals; actual local draft mutation occurred only after approval; backend tests deny consequential execution |
| Completed-work restart continuity | VERIFIED LIVE | Owned backend termination/restart retained identity, goals, investigations, experience and accounting |
| Interrupted-work recovery | VERIFIED WITH CONTROLLED FIXTURES | Seeded interrupted state becomes cancelled/truncated, preserves spent tokens, releases unused reservation and does not re-infer |
| A/B/C and no-Critic comparison | VERIFIED LIVE | One pinned Meta model, final frozen three-case dataset, 25 calls and 30,632 reported tokens |
| Alternative evidence-access arrangements | VERIFIED WITH CONTROLLED FIXTURES | `critic_only` and `proposer_only` harness runs; not a live Meta result |
| ALIVE-01 Pi / managed Chrome / extension | VERIFIED LIVE | Fresh real-Pi First Contact; browser E2E and actual stable-Chrome MV3 observation/revocation smoke |
| Native docked side panel on arbitrary sites | IMPLEMENTED BUT NOT VERIFIED | Inherited limitation: actual extension document tested; native docking/non-local activeTab visual qualification remains |
| GitHub Actions | IMPLEMENTED BUT NOT VERIFIED | Windows/Linux suite, frontend, PostgreSQL First Contact and First Thought jobs configured; no remote run/push |
| Autonomous Pi tools, reasoning escalation, MR.Q/RL training | NOT IMPLEMENTED | Manual Pi retained; autonomous Investigator uses enforceable read-only Python tools; no trained policy claimed |

## Real Meta evidence

Primary provider/model: **Meta Model API / `muse-spark-1.3`**. The initial successful native-schema smoke reported **92 prompt + 604 completion = 696 tokens**, 576 reasoning tokens included, approximately **3.526 seconds**. Local validation succeeded. An earlier 128-output-token attempt was truncated and is explicitly not a passing call; its full reported billable usage was not retained.

Final First Thought used role specifications v2. All six model invocations were schema/reference validated. The two meaningful cases each made three calls:

| Scenario | Result | Model calls | Reported tokens | Investigation elapsed |
| --- | --- | ---: | ---: | ---: |
| Relevant information | Completed; supported observation and source-checked conclusion retained | 3 | 6,556 | 7.567 s |
| Irrelevant noise | NO ACTION WARRANTED | 0 | 0 | No model investigation |
| Contradictory evidence | Completed; observed claim contradicted by controlled measurement | 3 | 6,788 | 7.477 s |

The acceptance run's **13,344** tokens are actual API usage, not an estimate. Dollar costs remain unknown (`null`); no price or invoice was invented. Across all persisted runtime Meta invocations during development, 18 validated calls reported 37,734 tokens; earlier engineering attempts are included in that broader scope. The preliminary benchmark separately reported 29,865 tokens, and the final benchmark 30,632. Together with the successful smoke, these known reported scopes total 98,927 tokens; that excludes the initial truncated smoke's unknown full usage and is not a provider-account billing total.

## Principal demonstration and persistence

Executed successfully:

```powershell
uv run python -m scripts.first_thought --provider meta
```

The script started the real backend/dashboard, confirmed PostgreSQL, started autonomy, opened an isolated managed Chrome session, navigated to a controlled habitat and authorised its sensor. A laboratory state change altered visible DOM content. The existing browser event path persisted that change; cognition normalized/deduplicated it, scored attention, proposed a goal, reserved resources and invoked actual Meta roles. The deterministic Investigator reread version-checked sources, the Evaluator compared explicit claims, and the Governor permitted only an internal recorded analysis. The actual outcome became a validated experience and was displayed in the dashboard. The script then restarted its owned backend and verified continuity.

| Item | Relevant case | Contradiction case |
| --- | --- | --- |
| Investigation | `57f38da4-803d-423b-9b37-62b2b30512b5` | `ae969108-e264-4189-979d-a9c648a04a37` |
| Goal | `5061bebf-ea30-482c-82bf-6b330ac04df9` | `5ae82ed4-87e4-44be-951d-68e0f167ce2e` |
| Experience | `095ef5e6-0304-4fe0-882f-0eb283b40fdd` | `6ca714d7-b92d-4577-b927-29994ce4d6b2` |

Original identity remains `c63edf59-5194-4ccd-b5c2-7e528be49d36`. The run verified that the six-call/13,344-token session and persistent experimental counters survived restart. There were no extra quiet-habitat investigations in this final run. A noisy page produced ignored observations without a flood of cognitive goals or model escalation.

The browser E2E separately configured a Class B draft proposal. The draft remained empty while awaiting approval, then changed through an authenticated approval operation. The test subsequently set the call budget to zero through the real dashboard form and verified a new meaningful observation was budget-rejected. Backend tests additionally prove rejection/cancellation, unsupported Class C denial and idempotent approval without duplicate effects.

## Embedding and retrieval qualification

Actual model: `sentence-transformers/all-MiniLM-L6-v2`, revision **`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`**, dimension **384**. Local ONNX inference performs masked mean pooling and normalization; no random, padded or truncated vectors are used. The original vector column remains intact; new tagged vectors are stored separately.

`uv run python -m scripts.verify_retrieval` approved three synthetic entries, indexed real vectors, executed PostgreSQL cosine and hybrid queries, retrieved the electrical-cell report for a battery-runtime query, and revoked the import. Imported memories and vectors were removed. Separate unit fixtures prove model-revision isolation, dimension rejection, provenance and explicit text fallback. This is controlled correctness evidence, not a general retrieval-quality claim.

## Benchmark: predeclared criterion and actual outcomes

The final component comparison used **`benchmarks/heldout.json`**, split `heldout-qualification-v1`, frozen before role-specification-v2 qualification. Prompts, dataset hash, exact model ID, outputs, latency and expenditure are retained. Expected labels are never supplied to a model. Earlier `cases.json` runs were engineering checks and are not treated as unseen tests.

All arms received equivalent controlled source facts and used the same deterministic evaluator. A useful positive decision required detection plus a proposed conclusion that exactly matched a cited measured source; an irrelevant case required abstention. A missing citation can therefore fail this criterion even when the proposed physical value is correct. The Critic's abstention is honoured. No benchmark action is executed; real Governor effects/recovery are tested separately.

| Arm | Criterion met | Calls | Reported tokens | Noise calls | Total case latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| A: direct Meta | 2/3 | 3 | 3,246 | 1 | 9.322 s |
| B: fixed society | 3/3 | 12 | 14,941 | 4 | 25.314 s |
| C: adaptive society | 3/3 | 6 | 7,935 | 0 | 12.430 s |
| C without Critic | 3/3 | 4 | 4,510 | 0 | 7.001 s |

All four arms had detection precision/recall 1.0 on just two positive and one negative case, no provider failures, and one abstention. The direct arm's miss was missing independent citation support. **The Critic added expense without improving this dataset's score.** This is evidence against claiming a demonstrated Critic benefit here. Three closely related synthetic cases cannot support general superiority, statistical significance or broad model-quality claims. The primary benchmark isolates components; it does not measure full browser/scheduler latency or establish a retrieval improvement.

The separate final ledger settled at **25 calls / 30,632 tokens**, within its 30-call/100,000-token ceiling. Alternative evidence access was exercised only with controlled role fixtures: removing evidence from the Proposer degraded the fixture criterion, but this is not a live-model causal conclusion.

## Tests and regression results

- **33 backend tests passed**, none skipped: all 12 original tests retained (migration-head expectation updated to 0003), plus attention/noise/duplicates/concurrent arrivals, structured contracts, independent evidence, action approval/rejection/cancellation, Class C denial, request/tool/session limits, persistent benchmark budget, invalid output, provider error/timeout, interrupted recovery, history lifecycle, hybrid fallback and vector model/dimension compatibility.
- **4 frontend Vitest tests passed**, none skipped. **TypeScript/Vite production build passed**, dashboard version 0.2.0. `npm audit`: **0 vulnerabilities** at qualification.
- **2 stable-Chrome browser E2E tests passed**: preserved First Contact UI behavior, and the new autonomous observation/role exchange/Class B approval/budget-control path.
- **Real-Pi First Contact passed again after ALIVE-02 changes**, including PostgreSQL FTS, ZeroMQ, Chrome, dashboard and restart continuity.
- **Stable-Chrome extension smoke passed** after the cursor-scanning fix; credentials/private fields, hidden-text exclusion and revocation remain covered.
- **Actual embedding/retrieval/import-revocation smoke passed** against PostgreSQL/pgvector.
- **Ruff check/format and Git whitespace checks passed.** The expected Windows pyzmq/Tornado selector-bridge warning remains visible; no integration tests were silently skipped.
- **PowerShell startup/stop/readiness passed.** Startup now waits for both backend and Vite before reporting ready, fixing a startup race found by an immediate extension smoke.

## Migration, APIs and files

Migration **0003** adds ten cognitive/experience/memory/laboratory tables and tagged vector/HNSW storage. ALIVE-01 tables and migration history remain preserved. See ALIVE-02-DESIGN for exact table names.

New authenticated interfaces include `/cognition`, `/cognition/control`, `/cognition/configuration`, `/cognition/observations`, `/cognition/investigations`, investigation details/cancellation, `/cognition/actions` and action decisions; `/experiences`, JSONL export and deterministic replay; `/providers/meta/probe`; `/memories/index`; `/history/preview`, approval/revocation; `/lab` and injection; and browser-session observation grants. The public laboratory page exposes only its explicitly synthetic state. OpenAPI remains at `/docs`.

New implementation modules, benchmark fixtures, migration, scripts, tests and `dashboard/src/Cognition.tsx` are documented in ALIVE-02-DESIGN. Required implementation-level documents are present: design, protocol, society, auction, Meta integration, experience schema, provenance and this acceptance report. README/development/architecture/security and CI were updated.

## Reproduce and inspect

```powershell
uv sync --locked
cd dashboard
npm ci
cd ..
uv run alembic upgrade head
uv run python -m scripts.prepare_embeddings
# Configure ignored .env: Meta credential and ALIVE_EMBEDDING_ENABLED=true.
./scripts/dev.ps1
uv run python -m scripts.verify_retrieval
uv run python -m scripts.extension_smoke
# Owned restart qualification requires normal servers stopped:
./scripts/stop.ps1
uv run python -m scripts.first_thought --provider meta
./scripts/dev.ps1
```

The explicit paid benchmark command, data/ledger paths and offline substitute are in README. A previously used ledger retains its expenditure. Full local evidence is ignored under `.alive`: `meta-smoke.json`, `first-thought.json`, `first-thought.png`, `benchmark-final.json`, `benchmark-final-ledger.json`, preliminary `benchmark.json`, `retrieval-evidence.json`, `cognition-e2e.png`, `alive-02.png`, and acceptance logs. Credentials, weights, profiles, private history and raw runtime artifacts are not committed.

Local URLs: dashboard **http://127.0.0.1:5173**, API **http://127.0.0.1:8000/docs**, controlled laboratory pages `/world/{environment_id}`. The development service is left running with autonomy stopped after qualification; select Cognition/provider and start explicitly. No recurring paid inference runs while stopped.

## Limitations and ALIVE-03

Verification is grounded in synthetic controlled measurements, not general web truth. The current normalizer supports generic prose triage and structured fixture claims; robust entity/claim extraction, richer source changes and broader retrieval evaluation remain future work. Model IDs are explicit provider-managed versions, not downloadable frozen inference weights. Input accounting reserves a conservative byte/schema envelope; ALIVE is not a provider-account billing quota. Historical derived traces are not fully purged by importer revocation.

Native side-panel docking/non-local activeTab behavior and remote CI remain unverified. Autonomous Pi tools, escalation, vision, native streaming, personal-history ingestion and reinforcement learning are not implemented. Proposed consequential external actions are unsupported. No consciousness, general intelligence, learned attention policy or self-improvement is claimed.

Recommended ALIVE-03: extend measured outcome environments and a larger predeclared evaluation set before learning; test whether evidence access/selective criticism helps beyond its cost; add prediction/outcome error and provenance-aware representation experiments; then evaluate an MR.Q-inspired policy against the deterministic baseline with defensible termination/reward definitions. Preserve both First Contact and First Thought as regression gates.
