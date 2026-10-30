# Experiments

Research harnesses live here. The architectural rule (ALIVE-ARCH-01):

- `experiments/` may depend on ALIVE (`alive.governance`, `alive.*`).
- ALIVE must never depend on `experiments/`, benchmark fixtures, or test utilities.
- Production installs must run without research-only corpora, frozen prompts,
  or experimental HTTP endpoints.

## Layout

- `alive03_p1/` — canonical home for the ALIVE-03-P1 selective-cognition study.
  The frozen implementation is still served from `alive/experiment/` because
  `benchmarks/alive03-p1/freeze-*.json` pins those exact source paths. Do not
  move those files without an explicit, owner-authorized re-seal that preserves
  historical freeze artifacts.
- `dev_app.py` — `create_experiment_app()` builds the API with the opt-in
  research router (`include_experiments=True`).

## Runtime governance

Reusable capabilities extracted from the harness live in `alive/governance/`:

- `pricing.price` — rate-card USD estimates (never billing).
- `budgets.settle_control` / `check_spend` / `charged_micro_usd` /
  `worst_micro_usd` — Governor reservation accounting.
- `hashing.file_hash` — deterministic UTF-8 file hashing.

Production services (`living`, `web_experience`, `research_relationships`,
`learning`) import from `alive.governance`, never from `alive.experiment`.
