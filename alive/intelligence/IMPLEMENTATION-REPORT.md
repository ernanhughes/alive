# ALIVE-INTELLIGENCE-01 implementation report

Date: 2026-10-30 (Europe/London).

## Checkout and delivery identity

- Original checkout: `C:/Projects/alive`, branch `main`.
- Inspected base HEAD: `2d82e7eb3b9308bae961a287a9c5f0dcd67880f7`.
- Preflight `git status --short`: empty. No pre-existing unrelated dirt was present.
- Isolated worktree: `C:/Projects/alive-intelligence-01`.
- Feature branch: `codex/alive-intelligence-01`.
- Implementation, tests and design commit:
  `ad8791a38a5f1a25528f0ff1861c6b46c87acce3`.
- This report is delivered in a subsequent documentation-only commit. Its exact
  delivery SHA is available with `git log -1 --format=%H -- alive/intelligence/IMPLEMENTATION-REPORT.md`
  and in the final delivery message; a file cannot contain its own commit hash.
- No push, PR, merge, rebase, deployment or remote Git request was performed.
  The brief prohibits network calls; CONTRIBUTING also restricts publication.

## Gate A: confirmed grounding

Commands included `git status --short`, `git branch --show-current`,
`git rev-parse HEAD`, `git worktree list`, `python --version`, direct source reads
and `rg` searches of the actual checkout. No applicable `AGENTS.md` was present
in the project/ancestor directories. `CONTRIBUTING.md` was read.

Created isolation with:

```powershell
git worktree add -b codex/alive-intelligence-01 C:/Projects/alive-intelligence-01 HEAD
```

Confirmed from current code and callers:

- `ModelGateway`/`StructuredRequest` and Cognition's existing pre-dispatch
  reservation, accounting, usage validation and settlement boundaries. Only
  `cognition.role` is currently registered. Gateway transport selects direct or
  Pi from approved settings; this package neither selects nor starts transport.
- Existing `RoleOutput` strict schema, observer instructions and evidence rules.
- Existing Living independently observes browser feedback and owns persisted
  empirical policy updates; its code was not cloned or changed.
- `living_policy` knows exactly `monitor`/`retrieve`, its controlled Aster context,
  observed means, zero priors, monitor-first ties and `[-1.15, 1]` reward bounds.
- Controller expects the exact 18-feature/six-action synthetic environment ordering;
  `q`, `choose`, `predict`, `update`, `save` and `restore` have different roles.
  The new adapter calls only `q`, `choose` and `predict` on a verified snapshot.
- Memory uses provenance-aware retrieval; research memory and relationships retain
  goal, anchoring, source and outbound-consent boundaries. None are bypassed.
- Historical experiment freeze/scoring organization and the distinction between
  the older `agents.PiRunner` and governed `alive.pi` runtime were inspected.
- Host `python --version`: 3.13.15. Actual existing repository virtual environment
  used for tests: Python 3.13.3, Pydantic 2.14.1, pytest 9.1.1, NumPy 2.5.4.
  No package installation, upgrade, lockfile change or download was performed.

Not assumed/qualified: deployed transport settings, real source consent, real
Governor reservation availability, a qualified research checkpoint, live semantic
state representation or any empirical/predictive advantage.

## Gates B-D: implemented behavior and exact changed paths

All changes are additions under `alive/intelligence/`:

```text
.gitignore
__init__.py
contracts.py
ports.py
reasoning.py
decision.py
experience.py
engine.py
example.py
policies/__init__.py
policies/empirical.py
policies/predictive.py
tests/__init__.py
tests/conftest.py
tests/test_contracts.py
tests/test_engine.py
tests/test_policies.py
tests/test_adversarial.py
README.md
DESIGN.md
INTEGRATION-BACKLOG.md
IMPLEMENTATION-REPORT.md
```

Functional slice: frozen versioned bounded contracts; exact evidence admission;
caller-owned, payload/scope-bound invocation seam; existing role-schema validation;
admitted citations retained as model opinion; masked empirical proposals; external
Governor authorization required and `executed=False`; independently verified
training feedback; local idempotency and pure-policy replacement; immutable
experience transitions; saved-estimate errors; related-episode revisit and frozen
policy comparison. Failures, cancellation and unavailable reasoning are explicit.

The empirical adapter actually calls existing `living_policy.choose/update`, and
refuses unsupported vocabulary. No algorithm replacement or substantive existing
logic was copied. Live and fixture states use distinct origin/context identities;
simulator and evaluation/development data cannot update this empirical bridge.

The optional predictor checks an explicitly supplied Controller's canonical online
and target parameter hash/dimensions and a trusted qualification verifier, then
uses a private snapshot. It requires exact feature/action ordering and mask. Its
output is separate, read-only and simulation-only. No qualified saved checkpoint
was supplied, so positive artifact-backed behavior is **not qualified or claimed
as tested**. No trained weights were fabricated. The test that constructs a random
Controller explicitly asserts that it remains unqualified and unavailable.

## Gate E: actual commands and results

All commands below ran from `C:/Projects/alive-intelligence-01`. `$py` below is
the exact executable `C:/Projects/alive/.venv/Scripts/python.exe`. Bytecode was
disabled with `-B`; existing-suite children also inherited
`PYTHONDONTWRITEBYTECODE=1`. No root tests were edited.

| Command | Result |
| --- | --- |
| `& $py -B -m pytest -q alive/intelligence/tests -p no:cacheprovider --confcutdir=alive/intelligence/tests` | **65 passed**, final run 0.65 seconds. |
| `& $py -B -m pytest -q tests/test_model_gateway.py tests/test_learning.py tests/test_living.py tests/test_cognition.py -p no:cacheprovider --basetemp=alive/intelligence/.test-tmp -o tmp_path_retention_policy=failed` | **67 passed**, 38.15 seconds, 34 existing Windows Proactor/ZeroMQ selector warnings. |
| `& $py -B -m ruff check --no-cache alive/intelligence` | **Passed**. |
| `& $py -B -m ruff format --no-cache --check alive/intelligence` | **Passed**; later final formatting pass also reported all files unchanged. |
| `& $py -B -m alive.intelligence.example` | **Passed**, complete controlled two-episode fixture JSON; separately parsed/asserted its accepted transition and current/frozen actions. |
| `git diff --check` and `git diff --cached --check` | **Passed**. |
| `git ls-files --others --exclude-standard`, `git diff --name-only HEAD` and Python prefix assertion | **Passed** before commit: every new path under `alive/intelligence/`, zero changed tracked paths elsewhere. |
| `git -C C:/Projects/alive status --short` | **Empty** after implementation and tests; original checkout unchanged. |
| Source review/search for provider construction, gateway dispatch, Pi imports, executors, arbitrary code execution, reverse Intelligence imports and generated assets | No new production dispatch/provider/executor/reverse imports or generated assets. Empirical update reuse and test harness subprocess are intentional. |

Initial failures and their resolution are recorded rather than hidden:

1. The fresh-import sentinel originally replaced the `Popen` class itself, breaking
   Windows asyncio's subclass definition before any side effect could occur. The
   sentinel now blocks its constructor, preserving Python's class hierarchy.
2. The first existing-suite run was **66 passed / 1 failed**: the unchanged gateway
   credential ratchet recursively scanned intentionally malformed/credential-shaped
   adversarial test fixtures retained inside this task's `.test-tmp`. Keeping
   temporary files inside the permitted package was necessary for the path boundary.
   The final command uses pytest's `tmp_path_retention_policy=failed`, so passing
   fixtures are removed before repository scanning. The scanner and all existing
   expectations remain unchanged. The full same four suites then passed.
3. The new network-denial fixture initially blocked Windows asyncio's internal
   loopback socketpair during event-loop creation (51 setup errors, 12 passes).
   Making it an async fixture initializes the harness loop first; all subsequent
   test connection attempts remain blocked. This was a harness issue, not a live
   network/provider invocation. Final isolated tests pass with that guard active.
4. Ruff identified formatting/import/line-length issues during implementation;
   all were corrected inside the package. No baseline expectations were weakened.

Coverage includes fresh-import side effects; exact request shape/binding;
unauthorized invocation; malformed/extra/nonfinite model output; citation identity;
suspicious instruction text; unsupported actions; empty/singleton/affordability
masks; duplicate/conflicting/untrusted/unqualified evidence; fixture/live and
history/split boundaries; deterministic decisions; replayed/mismatched/incomplete/
unverified outcomes; verifier failure without partial update; stale policies;
unknown versus saved-mean prediction errors; cancellation/timeout without pending
tasks; unavailable/malformed/unqualified predictive inputs; matching/conflicting
shadow separation; and the actual two-episode interpretation/feedback/revisit path.

The fresh interpreter test blocks subprocess construction, connection attempts,
SQLite connection and filesystem mutation, and asserts that Pi, gateway/provider,
DB and Controller modules were not imported by `import alive.intelligence`.
The normal isolated tests deny network connections after harness initialization.
Existing targeted integration tests use their pre-existing local fixtures/mocks,
temporary SQLite databases and fake HTTP transports, never a real provider.

The full repository/UI/live acceptance suites were not run: this is a standalone
Python package with no UI, deployment or production registration changes. Actual
provider, browser and qualified checkpoint integration remain deliberately absent.

## Concrete two-episode trace

| Stage | Recorded behavior |
| --- | --- |
| Episode 1 input | Controlled Aster claim `32`, source replaced, admitted current fixture reference, train split. |
| Interpretation | One-use `controlled-role-fixture-v1`, cited opinion, uncertainty that the claim is not verified, 0 prompt/completion tokens. |
| Proposal | `monitor`, sample count 0, unknown/zero prior estimate, external authorization required, `executed=False`. |
| Independent feedback | Separate fixture instrument record reports value 20 and unresolved utility `-0.5`, completed reported fixture action; trusted fixture verifier matches the exact external record. No engine executor exists. |
| Learning | Monitor cell `n: 0 -> 1`, sum `0 -> -0.5`; policy revision `0 -> 1`; unknown prior prediction error stays `None`. |
| Episode 2 | New episode/time, earlier outcome explicitly historical, another zero-token cited fixture interpretation; current policy proposes `retrieve`, sample count 0. |
| Frozen comparison | Earlier policy still chooses `monitor` under the same current candidates/resources. This shows changed policy behavior, not improved generalization. |

Before-policy hash:
`651be659ba574c02f2e86c3f101d68aae69b8a065db18db6c5907f089e704327`.
After-policy hash:
`7e3fad8775eadb09c4fc27288cb63027c8e7322a5312f36bf115a7c6d0bfe2a4`.
These are audit pointers, not proof of semantic truth or source authenticity.

## Authority, review findings and remaining gaps

- **Implemented/tested:** isolated typed proposal, fixture interpretation validation,
  real existing empirical-policy behavior, independently verified session feedback,
  idempotency, errors/cancellation and revisit. No execution endpoint exists.
- **Not integrated:** Cognition/Living registration, Governor reservations, invocation
  ledger/receipt wrapping, memory retrieval/consent adapters, model trace UI and
  durable outcome/policy persistence. Required future edits are listed in the backlog;
  none were performed.
- **Research-only/not qualified:** predictive shadow positive path requires a real
  verified qualified artifact and exact synthetic input. No semantic web encoder,
  live MR.Q transfer, predictive advantage, held-out superiority or autonomous
  self-improvement is claimed. Historical negative/null findings remain intact.
- **Trust boundary:** protocol conformance, strings and hashes are not authorization.
  Only a trusted host may supply capability/verifier objects. It must enforce exact
  request approval, true provenance and existing Governor/consent/accounting. The
  fixture objects in `example.py` must not be used as production authorization.
- **Local-state limitation:** one event loop, up to 256 issued episodes, no durable
  exactly-once guarantee or cross-process/thread transaction. New engines reset the
  idempotency domain. A service-owned atomic transaction is future work.
- **Model limitation:** admitted citations are identity checks. Model outputs remain
  opinions and untrusted text; no semantic truth, quotation or permission certificate
  is inferred. Caller input must already be nonsecret and outbound-approved.
- **Failure limitation:** injected adapters must cooperate with cancellation. The
  capability retains settlement responsibility; the engine creates no detached work.

No external network searches, external network requests, real provider/model calls,
model downloads, paid inference, spend, browser actions or physical execution were
performed. Windows event-loop internal socketpairs and existing in-process test
fixtures are not external dispatch. Fixture usage is explicitly zero. No credentials,
private chats, raw model traces, checkpoints, caches or bytecode are committed.

Only `alive/intelligence/` source paths were added. Existing Pi, learning,
experiments, core modules, schemas, tests, config, lockfiles and workflows are
untouched. Git's administrative metadata records the explicitly requested feature
branch/worktree and local commits; the original `main` worktree remains unchanged.
Work stops at delivery, with no subsequent integration phase started.
