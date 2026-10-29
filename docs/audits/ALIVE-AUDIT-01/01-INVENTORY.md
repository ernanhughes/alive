# ALIVE-AUDIT-01 — Inventory and coverage

Audit date: 29 October 2026 (Europe/London). Independent, audit-first investigation; no application fixes or remote writes.

## Pinned baselines

| Surface | Exact commit | Status when inspected |
|---|---|---|
| Current main | `1b6da07b856e497b3a44a9e1b9794e94adff55ab` | PR #53 merge; release baseline |
| Original user checkout | `a060abea132a13f6ce8601a0d60c7402c6e74d35` | Behind main; untracked `.vscode/` preserved |
| PR #53 head | `621361c75ac183cd21861513d7321008830cab65` | Merged into main |
| PR #54 | `7bff18aab6db50e6b62a1c36529042d877af647f` | Open draft, Docker cold-start changes |
| PR #55 | `b0a77c11aeb94f8ca16072ee07c69323f570021a` | Open draft, dispatch hardening; newer than commissioning prompt |

Live PR state was obtained through the GitHub connector and CLI. See [open PR receipt](receipts/open-prs.json), [CI metadata](receipts/ci-run.json), and saved PR diffs. No PR was merged, closed, approved, or commented on.

## Inventory method and review limits

The pinned repository contains **1,409 tracked files, 210 Python modules, 533 Python test function definitions, and 104 route decorators**. Parameterization changes runtime test counts. The route count includes test/tool decorators and is not a count of authenticated production endpoints.

[repository-inventory.json](repository-inventory.json) includes file hashes, sizes, Python symbols with line locations, imports, loops, and broad exception-handler locations. [test-inventory.json](test-inventory.json) records every Python test definition, assertion/raises counts, and decorators. Counts alone say nothing about assertion quality. [api-surfaces.json](api-surfaces.json) records route declarations; authentication can be inherited through router dependencies.

[coverage.csv](coverage.csv) is the per-file review matrix. **AST parsing and file enumeration are not semantic review.** Detailed source review covers 16 files; selected critical-path review covers 22 files in the initial matrix. Additional focused inspections are described below, but are deliberately not promoted into a claim of exhaustive coverage. The requested line-by-line semantic examination of every production module and operational script is **not complete**. This dossier is evidence for a release stop and further review, not certification of the entire system. In particular, legacy experiment/native tooling and the scientific/statistical validity of all learning/evaluation code need separate review.

## Subsystems

| Subsystem / purpose | Entry points / important files | Invariants and dependencies | Tests / observed review coverage |
|---|---|---|---|
| API and local authority | `alive.app:create_app`, `alive/cognitive_api.py`, `alive/schemas.py` | Bearer token; origin checks; DB readiness; router dependencies. FastAPI/Pydantic | `test_runtime`, `test_cognition`; Docker HTTP and independent negative tests. Detailed API/auth review; F-001 |
| Kernel, identity, persistence, event recovery | `kernel.py`, `db.py`, `models.py`, `transport.py`, `provenance.py` | Single scheduler ownership (PostgreSQL advisory lease / SQLite file lock); atomic state/event commits; durable sequence cursor; ephemeral PUB/SUB does not establish delivery | `test_runtime`, `test_transport`, `test_migrations`; fresh PostgreSQL migrations, dependency interruption. Detailed core review |
| Cognition and Governor | `cognition.py`, `cognitive_models.py`, `cognitive_schema.py`, `workflow_defaults.py`, `attention.py`, `society.py` | Reserve before dispatch; bounded tools/tokens/calls; validate role output/references; terminal experience once; human approval for class B; class C unsupported | `test_cognition`, `test_recovery_budgets`, `test_model_gateway`. Selected lifecycle/dispatch paths and deterministic cancellation reproduction; F-002 |
| Model providers / gateway | `providers.py`, `model_gateway.py`; direct dispatch also in living/experiments/web/relationships | Operation routing; model/output limit/correlation parity; bounded transport; typed provider failure. HTTPX | 9 main gateway tests; 32 PR55 tests; 20 independent parameterized cases overall. Detailed provider/gateway review; F-004/006/007 |
| Agent subprocesses | `agents.py:PiRunner`, `Agents.start/execute/cancel` | Explicit objective; no tools/extensions/MCP/context discovery; bounded runtime; one active task; subprocess termination | `test_agents`, Docker mock-agent smoke. Source reviewed; real Pi execution NOT EXECUTED |
| Managed Chrome | `browser.py:Browsers` | Exact-origin routing; no downloads/service workers; exclude private DOM; restrict interactions to opted-in elements; observe again after action | `test_browser_provenance`, native scripts. Source reviewed; real extension test is separate from managed-browser runtime |
| Web companion / consent / policy feedback | `web_experience.py`, `web_models.py`, `relevance.py` | Exact URL/hash grant; consent expires/revokes; distinguish source from model interpretation; feedback never grants authority | `test_web_experience`, `test_web_policy_recovery`, `test_relevance*`; selected snapshot/dispatch/revocation paths and language policy review |
| Research memory / retrieval | `research_memory.py`, `memory.py`, `research_relationships.py` | Instance/goal identity; bounded retained excerpts; anchors/revisions; pre-dispatch source/request hashes; source withdrawal atomically invalidates derived content; unknown calls not retried | `test_research_memory`, `test_meta_memory`, `test_research*`, `test_claim_runtime`; selected save/withdraw/connect and relationship reservation/settlement/restart paths |
| Evidence and claim qualification | `evidence_qualification.py`, `claim_comparison.py`, `claim_fixtures.py`, `demo_live_01.py` | Hash consistency is not truth; exact quotes, occurrence and subject binding; conservative abstention; pinned mirror bytes; fixture results labelled | `test_evidence_qualification`, `test_claim_validator_v2*`, `test_demo_live_01*`; source inspected plus full fixture browser lifecycle |
| ALIVE-14 experiment approvals / recovery / blinding | `experiment_approval.py`, `research_blind.py`, `scripts/alive14r5_experiment.py` | Immutable campaign and exact request binding; durable fatal barrier; ordered call indices; no replay; capability-scoped rating; reveal after ratings | `test_alive14r5_safety`, `test_alive14r5_r1`, related R2–R5 suites. Selected source paths; baseline suite passes, not independent mutation coverage for every historical protection |
| Frozen ALIVE-03 selective experiments | `experiment/{service,corpus,freeze,scoring,policy,prompts,metrics,schema,api}.py`, `experiment_budget.py` | Frozen hashes, corpus split isolation, explicit evaluation authorization, finite numerical answer/citation checks, conservative spend estimate | `test_experiment03`, `test_experiment_budget`, `test_experiment03`; selected call/scoring/freeze/corpus paths. No frozen artifacts changed or live inference run |
| Learning / simulation / diagnostics | `learning/{controller,environment,experiment,history_diagnostic,api}.py`, `experience_lab.py`, `living_policy.py`, `living_evaluation.py`, `living.py` | Simulator truth separated from observed inputs; train-only transitions; matched experiments; live permissions independent of learned preferences | `test_learning`, `test_history_diagnostic`, `test_experience_lab`, `test_living`; selected source inspection, full suite execution. Statistical/scientific assurance remains incomplete |
| Eval custody / trust | `scripts/alive_eval0{1,2}*.py`, notebook protocol tools; `evaluations/` | Pinned roots; package/gold/output identity; receipts bound to run; qualified progression fails closed without verified custody | `test_alive_eval01`, `test_alive_eval02*`, `test_notebook*`; selected pinned-root and receipt paths. Signature backend deliberately unavailable: intended refusal, not a bug |
| Skill Forge / exploration | `skill_forge/{__init__,runtime}.py`, `exploration_api.py`, declarative `extensions/` | Owner request + approved/enabled skill; constrained operation set; host supplies handlers; projection reflects active research memories | `test_skill_forge_p0`, `test_exploration_api`; selected registry/dispatch/projection review |
| Extension, dashboard, notebook | `extension/{manifest,config,background,capture,observer,panel,live-companion}`, `dashboard/src`, `site/` | Explicit capture/review; sender/page/backend binding; fixture/interpretation labels; no raw HTML rendering as model authority | 38 Node tests, 7 dashboard tests, build; Chrome 156 docked side panel against PR54. Selected JS/API/config inspection; full UI implementation not semantically reviewed |
| Deployment / CI / operations | Dockerfile, compose files, `docker/`, `scripts/{dev,stop,first_contact,docker-*}`, `.github/workflows` | Loopback host binding; no paid inference by default; migrations before readiness; smoke checks not full browser proof | Main image build/fresh volumes, HTTP groups, PR54 Chrome/restart/demo-off; CI logs independently retrieved. Selected operational source review |

## Created resources

All intentional audit source/report additions are under `docs/audits/ALIVE-AUDIT-01/` on local branch `codex/alive-audit-01` in `C:/Projects/alive-audit-01`. Detached worktrees: `C:/Projects/alive-audit-01-pr54`, `C:/Projects/alive-audit-01-pr55`. A local `.venv`, npm installation/build, test caches, temporary fixtures, and isolated Chrome profile were created; none is production evidence or a committed secret. The Chrome profile is ignored under the audit worktree's `.alive/`.

Docker projects: `alive-audit01-main` (host 18081 through an explicit audit-only port override), `alive-audit01-pr54` (host 8000). Fake local token and empty model credential only. Existing projects `alive-pi-01a-r2` and `devcontainer` were not modified. Audit containers are stopped at closeout; named audit volumes remain for inspection. See resource receipts and `06-DEMO-READINESS.md`.

## Reproduction convention

Run commands from the pinned audit worktree. For audit tests use:

```powershell
uv run python -m pytest -q docs/audits/ALIVE-AUDIT-01/test_adversarial.py --tb=short
```

These intentionally red regression assertions reproduce defects. Do not add them to release CI as expected passes until the corresponding corrections exist. No tests or production assertions were weakened.
