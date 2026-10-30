"""Pre-inference spending guard around the unchanged frozen ALIVE-03 runner.

The owner authorized $1, 350 calls and 500,000 tokens. The experiment's corpus,
policy, evaluator, prompts and runner remain byte-for-byte unchanged. This overlay
only restricts execution. Its source identity is persisted before test unsealing.

ARCH-01: spend math lives in ``alive.governance.budgets`` (the runtime
canonical home). This module keeps the experiment-specific $1 guard and the
``BudgetedExperiments`` harness overlay; production runtime code must import
from ``alive.governance`` instead of this module.
"""

import json

from alive.cognitive_models import CognitiveControl
from alive.cognitive_schema import CognitiveConfiguration, RoleOutput
from alive.experiment.prompts import prompt
from alive.experiment.service import ExperimentAuthorization, ExperimentRun, Experiments
from alive.governance.budgets import (
    charged_micro_usd as _charged_micro_usd,
)
from alive.governance.budgets import (
    check_spend as _check_spend,
)
from alive.governance.budgets import (
    worst_micro_usd as _worst_micro_usd,
)
from alive.governance.hashing import file_hash

GUARD_SOURCE = "alive/experiment_budget.py"
MAX_MICRO_USD = 1000000


def worst_micro_usd(tokens):
    return _worst_micro_usd(tokens)


def charged_micro_usd(ledger):
    return _charged_micro_usd(ledger)


def check_spend(ledger, reserved_tokens, cap=MAX_MICRO_USD):
    return _check_spend(ledger, reserved_tokens, cap=cap)


class BudgetedExperiments(Experiments):
    async def authorize(self, data):
        if data.max_calls > 350 or data.max_tokens > 500000:
            raise ValueError("Owner authorization is limited to 350 calls and 500000 tokens")
        authorization = await super().authorize(data)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(ExperimentAuthorization, authorization["id"])
            row.limits = row.limits | {
                "max_usd": 1.0,
                "ceiling_micro_usd": MAX_MICRO_USD,
                "spending_guard_sha256": file_hash(GUARD_SOURCE),
                "spending_guard_source": GUARD_SOURCE,
                "pricing_source": "https://dev.meta.ai/docs/pricing-rate-limits",
                "pricing_usd_per_million": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
                "owner_instruction": "Authorized full 120-task evaluation capped at $1.00, "
                "350 calls and 500000 tokens; no automatic retries",
            }
            authorization["limits"] = row.limits
            self.k.add_event(
                session,
                "experiment.spending_guard_authorized",
                {
                    "authorization_id": row.id,
                    "limits": row.limits,
                },
            )
        return authorization

    async def call(self, run_id, task, role, context, arm):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(ExperimentRun, run_id)
            if run.phase == "full":
                authorization = await session.get(
                    ExperimentAuthorization, run.data["limits"]["authorization_id"]
                )
                if (
                    not authorization
                    or not authorization.consumed
                    or authorization.limits.get("spending_guard_sha256") != file_hash(GUARD_SOURCE)
                    or authorization.limits.get("ceiling_micro_usd") != MAX_MICRO_USD
                ):
                    raise ValueError("Missing or changed authorized spending guard")
                control = await session.get(CognitiveControl, self.k.instance_id)
                cfg = CognitiveConfiguration.model_validate(control.configuration)
                reserve = (
                    len(
                        json.dumps(
                            {
                                "instructions": prompt(role),
                                "input": context,
                                "schema": RoleOutput.model_json_schema(),
                            },
                            ensure_ascii=False,
                        ).encode()
                    )
                    + 1024
                    + cfg.output_tokens
                )
                checked = check_spend(run.data["ledger"], reserve)
                self.k.add_event(
                    session,
                    "experiment.usd_reservation_checked",
                    {
                        "run_id": run_id,
                        "task_id": task.id,
                        **checked,
                    },
                )
        # The frozen worker is strictly sequential. Its persisted reservation is
        # written before inference; this check includes any prior unknown usage.
        return await super().call(run_id, task, role, context, arm)
