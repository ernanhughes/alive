# ALIVE

**Adaptive Living Intelligence** — a persistent local runtime that perceives browser observations, remembers experience, proposes goals and survives restarts.

**ALIVE-05 adds the native Chrome documentation companion:** review an authorised
page excerpt, obtain a bounded Meta note, rate its usefulness, then recall the same
note after a restart. Goals, page evidence, model notes and feedback stay distinct.
See [installation, qualification and the three-minute demo](docs/ALIVE-05.md).
This is exact-match experience reuse on two public documentation pages, not general
website adaptation or evidence that predictive learning outperforms simpler policies.

**ALIVE-06 adds contextual goal relevance to the documentation companion:** before any
model call, a deterministic local check compares the owner's goal with the reviewed
excerpt. If they share no content terms, ALIVE records **no action warranted**, creates
no note and makes no Meta call. The side panel shows the match terms and the basis.
This is transparent lexical relevance, not semantic understanding or open-web autonomy.
See [the ALIVE-06 protocol](docs/ALIVE-06.md).

**ALIVE-07 externalises relevance language resources and adds a versioned multilingual policy:**
English, Chinese character n-grams and Arabic normalisation are configured in
`config/relevance/` rather than hard-coded in the decision loop. Unsupported or mixed
scripts produce an explicit **uncertain** decision, with no automatic Meta call.
A frozen 27-case corpus reports per-language precision, recall, false abstention
and uncertainty against the ALIVE-06 baseline. See [the ALIVE-07 protocol](docs/ALIVE-07.md).

**ALIVE-08 tests whether experience improves decisions.** A frozen sequential simulator compares
ALIVE's empirical source memory with a flat contextual learner, no history, shuffled history,
stateless and fixed policies. Correct history beats no/shuffled history, but the primary comparison
did **not** show an advantage over the flat control. The negative result is preserved in the
[ALIVE-08 report](docs/ALIVE-08.md) and its [evidence archive](archives/ALIVE-08/README.md).

**ALIVE-09 connects feedback to future companion decisions.** A completed owner rating now updates a
persisted, versioned usefulness policy for the exact goal, page and language. After three independent
ratings showing at most 20% usefulness, the companion recommends no action and makes no Meta call;
the owner can explicitly correct that abstention through the existing grant and Governor. Useful
feedback can restore analysis. Exact useful-note recall still takes precedence. The evidence is a
controlled companion API sequence with a synthetic provider, not native Chrome or Meta inference.
See [the ALIVE-09 report](docs/ALIVE-09.md) and its
[evidence archive](archives/ALIVE-09/README.md).

ALIVE-01 is a working vertical slice: FastAPI + PostgreSQL/pgvector + ZeroMQ + React dashboard + managed Chrome + Manifest V3 extension + Pi RPC. Deterministic policies drive curiosity, coherence and commitment. They do not require recurring model calls or claim to be reinforcement learning.

**ALIVE-02 adds a bounded autonomous cognitive loop.** Authorised browser changes compete for attention; structured Meta Observer/Proposer/Critic roles cooperate while a deterministic Investigator, Evaluator and Governor control evidence, permissions and budgets. Real ONNX embeddings, hybrid retrieval, human action approval, persistent experience and restart recovery are implemented. Open **Cognition** in the existing observatory to inspect real traces. Autonomy starts stopped and recovers paused.

Read the [ALIVE-02 acceptance report](docs/ALIVE-02-ACCEPTANCE.md) and [design](docs/ALIVE-02-DESIGN.md). ALIVE-01 documentation remains the historical foundation, not the latest integration status.

The reviewed ALIVE-02 specifications, results, screenshot and redacted usage records are retained in the [qualification archive](archives/ALIVE-02/README.md), with checksums and explicit evidence limitations.

## Run on Windows

Prerequisites: Python 3.13, uv, Node 24+ (tested with 25.8.2), PostgreSQL and stable Chrome.

```powershell
uv sync --locked
Copy-Item .env.example .env
# Edit .env locally: set DATABASE_URL (or ALIVE_DSN) and a strong ALIVE_API_TOKEN.
# If ALIVE_API_TOKEN is omitted, ALIVE generates an ignored .alive/token file.
uv run alembic upgrade head
cd dashboard
npm ci
cd ..
./scripts/dev.ps1
```

Open the [dashboard](http://127.0.0.1:5173) and enter your local token. The [API documentation](http://127.0.0.1:8000/docs) describes the interface. The [controlled habitat](http://127.0.0.1:8000/demo) contains explicitly permitted interaction controls.

Stop the development processes with `./scripts/stop.ps1`. For foreground processes, use the separate commands in [development instructions](docs/DEVELOPMENT.md).

## First Contact

Stop the backend first. This demonstration owns its backend processes, restarts them and **adds** test experience to your existing ALIVE database. It never drops or resets it.

```powershell
uv run python -m scripts.first_contact --runner mock
# With local Pi credentials/model configured:
uv run python -m scripts.first_contact --runner pi
```

It launches managed Chrome, changes the habitat, verifies PostgreSQL full-text retrieval, ZeroMQ delivery, dashboard rendering and agent completion, accepts a follow-up goal, restarts the backend and checks continuity. Evidence stays in ignored `.alive/first-contact.json` and `.alive/first-contact.png`.

Use `--existing-dashboard` when Vite is already running. See [acceptance evidence and limitations](docs/ALIVE-01-ACCEPTANCE.md).

## The First Autonomous Thought

Configure `ALIVE_META_API_KEY` locally. The confirmed primary model is `muse-spark-1.3`. For actual local semantic retrieval:

```powershell
uv run python -m scripts.prepare_embeddings
# In ignored .env set ALIVE_EMBEDDING_ENABLED=true.
```

Start the app and open **Cognition**. Select the provider, start autonomy, open/observe a laboratory habitat and inject its environmental change. No chat prompt starts the investigation. Inspect its attention bid, goal, role exchanges, grounded verdict, permitted effect and experience. Stop revokes managed sensors; pause cancels cognition. Budgets and permissions can be edited while paused. Choosing `preferred_action=lab_draft` demonstrates explicit approval before changing a controlled draft.

For the reproducible demonstration with an owned backend restart, first stop normal development servers:

```powershell
./scripts/stop.ps1
uv run python -m scripts.first_thought --provider meta
# Offline engineering substitute, explicitly labeled:
uv run python -m scripts.first_thought --provider mock
./scripts/dev.ps1
uv run python -m scripts.verify_retrieval
```

The live demonstration runs relevant-information, irrelevant-noise and contradictory-evidence cases, records actual model expenditure and verifies identity/goals/investigations/experience/budget continuity. Evidence remains ignored in `.alive/first-thought.json` and `.alive/first-thought.png`.

The bounded A/B/C + no-Critic comparison uses one pinned model and fixed datasets. Paid bulk inference requires deliberate opt-in; the ledger persists reservations across interruption:

```powershell
uv run python -m scripts.benchmark --provider mock --output .alive/benchmark-engineering.json
uv run python -m scripts.benchmark --provider meta --allow-paid --max-calls 30 --max-tokens 100000 --dataset-path benchmarks/heldout.json --output .alive/benchmark-final.json --ledger .alive/benchmark-final-ledger.json
```

An existing ledger retains its spent calls/tokens; use distinct explicit ledger/output paths for a new experiment. These three-case component comparisons cannot establish general superiority. The final report includes the Critic ablation, failures, abstentions, latency and measured token cost; unknown dollar costs stay null.

## Chrome extension

ALIVE-03-P1 adds the frozen Selective Cognition experiment and a policy-comparison view under
Cognition. See the [protocol and bounded reproduction steps](docs/ALIVE-03-P1.md) and
[qualification evidence](archives/ALIVE-03-P1/README.md). The full paid evaluation requires
separate owner authorization after reviewing its projected expenditure.

The [authorized full evaluation](archives/ALIVE-03-P1-FULL/README.md) completed 120 tasks:
Never and Selective scored 120/120; Always scored 119/120 under the unchanged scoring contract.
Selective's frozen calibration chose Never-like behavior, so no adaptive-routing advantage
was demonstrated. Full paired evidence and the single recommendation-contract regression
are archived with actual usage and spending checks.

P1 is [closed without tuning](docs/ALIVE-03-P1-CLOSURE.md). P2 adds a
[controlled predictive-learning simulator](docs/ALIVE-03-P2.md), with matched replay,
value-only and predictive learners, explicit ablations and a read-only Cognition dashboard.
The [simulator qualification](archives/ALIVE-03-P2-SIM/README.md) preserves the initial result:
policies learn, but predictive losses have not demonstrated an advantage over value-only learning.
Runtime criticism defaults off; explicit experimental opt-in remains available.

The [P3 diagnostic](archives/ALIVE-03-P3/README.md) isolates history information, action effects,
matched prediction probes and three replay sizes using the unchanged P2 learners.
History-aware state helps both learners in the controlled setting; predictive regularization
still has no demonstrated advantage. The [next product handoff](docs/LIVE-DEMONSTRATION-NEXT.md)
prioritizes a visible, Governor-controlled experience loop over further learner optimization.

**ALIVE-04 — The Living Experience** adds a Living tab with real Chrome observations, Meta
evidence synthesis and a durable empirical policy. The qualified two-encounter journey
changes from monitoring to evidence retrieval after observed feedback and a backend restart.
See the [protocol](docs/ALIVE-04.md) and [live evidence](archives/ALIVE-04/README.md).

Open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose the repository's `extension` directory. Click the ALIVE toolbar icon to open its side panel. Configure the backend and local token, then click **Authorise this page**. Review and send an observation, or explicitly enable automatic sending. **Stop & revoke** disconnects the observer and clears its selected observation.

The extension uses `activeTab`, scripting, storage and the Side Panel API, with host permissions limited to the local backend. It excludes form values, hidden text and marked private subtrees. Arbitrary webpage observation requires a fresh toolbar grant; the test habitat is already covered by the narrow backend host grant.

## Verification

```powershell
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
uv run pytest -q
cd dashboard
npm test
npm run build
# With backend and dashboard running:
npm run test:e2e
cd ..
uv run python -m scripts.extension_smoke
```

The default unit suite uses temporary SQLite databases, labels substring search correctly and exercises real loopback ZeroMQ. PostgreSQL, Chrome, Pi and dashboard acceptance are verified separately; a mocked test is never treated as proof of live integration.

Read [architecture](docs/ARCHITECTURE.md), [development](docs/DEVELOPMENT.md), [security](SECURITY.md) and [provenance](docs/HACKATHON_PROVENANCE.md). Apache-2.0; the repository's original license is preserved.
