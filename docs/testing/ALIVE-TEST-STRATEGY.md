# ALIVE Test Strategy (ALIVE-TEST-INTEL-01)

## Objective

Faster feedback without losing essential evidence. Selective execution during
development; comprehensive qualification before merges and releases.

## Tiers

| Tier | Command | When | Scope |
| --- | --- | --- | --- |
| QUICK | `python scripts/test_run.py --mode quick` | Every change | Always-run smoke/config net + name-matched unit tests for the change. Bounded; target seconds. |
| AFFECTED | `python scripts/test_run.py --mode affected` | After completing a slice | QUICK + direct/indirect import dependents + risk-rule expansions. Conservative. |
| FULL | `python scripts/test_run.py --mode full` | Pre-merge / nightly | Entire pytest suite. Existing required merge gates stay intact. |
| DOCKER | `python scripts/test_run.py --mode docker [--dry-run]` | Deployment-sensitive | Container-relevant pytest subset + compose build, fresh migrations, smoke, isolated E2E. |

## Selection principles

1. **Explainable.** Every selected test carries reasons (`--explain`). No silent skipping:
   non-full runs print "subset selection is not equivalent to a full-suite pass".
2. **Conservative fallback.** Core (`alive/app.py`, `config.py`, `db.py`, `models.py`,
   `tests/conftest.py`, `pyproject.toml`, `alembic.ini`), CI workflow, unknown file
   types, or >20 changed files select the full suite in `affected` mode. `quick`
   stays bounded smoke and says full qualification is still required.
3. **Risk triggers.**
   - `migrations/*`, `alive/models.py`, `alive/db.py` -> migration + persistence
     tests, docker flag.
   - `Dockerfile`, `compose*`, `docker/`, lockfiles -> config tests, docker flag.
   - `evaluations/*`, `scripts/alive_eval01*`, `scripts/notebook*` -> eval integrity.
   - Safety/auth/policy/claim code -> safety + adversarial suites, broadened.
   - `dashboard/`, `extension/`, `site/` -> UI smoke + provenance; full node/vitest
     suites stay in FULL/DOCKER/CI.
   - Docs-only (`.md`, `docs/`) -> minimal smoke net.
4. **Import graph, one hop.** `test_select.py` parses `tests/test_*.py` imports of
   `alive.*`/`scripts.*` plus intra-`alive` imports, so a change to `alive/foo.py`
   also selects tests of modules that import `foo`. QUICK uses basename-token
   matching only, to stay in seconds.
5. **No duplication within a run.** A test selected by several rules runs once.

## Policy (non-negotiable)

- Do not delete tests or weaken assertions/integrity checks to gain speed.
- Do not modify frozen evaluation scenarios, protocols, or expected outputs.
- Do not present a selective result as equivalent to a full-suite pass.
- `affected`/`quick` never replace required pre-merge checks (see `.github/workflows/ci.yml`).
- Docker isolation guarantees hold; no developer databases for destructive tests.
- No new heavy infrastructure: stdlib Python + pytest + git only.

## Receipt

Every `test_run.py` run prints a decision receipt (selected / not selected /
elapsed / tier / what remains unverified) and can write it with `--report`.

## Scheduled qualification

- Fast jobs first; affected integration per change impact.
- FULL remains the mandatory pre-merge gate per current project policy.
- DOCKER runs on deployment-sensitive changes and at release qualification.
- Scheduled full/container regressions may supplement, never replace, merge gates.
