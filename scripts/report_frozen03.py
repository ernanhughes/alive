"""Archive the authorized full run without altering either qualification archive or policy."""

import asyncio
import csv
import hashlib
import io
import json
import shutil
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
from sqlalchemy import select

from alive.config import Settings, prepare_local
from alive.db import Database
from alive.experiment.corpus import load
from alive.experiment.freeze import file_hash, verify
from alive.experiment.service import ExperimentAuthorization
from alive.experiment_budget import charged_micro_usd
from alive.models import Event, record


def analyze(run):
    data = run["data"]
    rows = data["rows"]
    tasks = load("evaluation")
    completed_ids = {r["task_id"] for r in rows}
    incomplete = [
        {
            "task_id": t.id,
            "category": t.category,
            "reason": data.get("error") or "no completed outcome",
        }
        for t in tasks
        if t.id not in completed_ids
    ]
    categories = {}
    policies = {}
    for policy in ["always", "never", "selective"]:
        for category in sorted({t.category for t in tasks}):
            arms = [r["arms"][policy] for r in rows if r["category"] == category]
            categories.setdefault(category, {})[policy] = {
                "scheduled": 30,
                "completed": len(arms),
                "correct": sum(a["score"]["correct"] for a in arms),
                "correct_abstentions": sum(a["score"]["correct_abstention"] for a in arms),
                "unsupported_claim_acceptances": sum(
                    a["score"]["unsupported_acceptance"] for a in arms
                ),
                "critic_calls": sum(a["invoked"] for a in arms),
                "errors": sum(bool(a.get("error")) for a in arms),
            }
        arms = [r["arms"][policy] for r in rows]
        latencies = [a["end_to_end_latency_ms"] for a in arms]
        wrong_initial = sum(
            r.get("eligible", False) and not r["initial_score"]["correct"] for r in rows
        )
        correct_initial = sum(
            r.get("eligible", False) and r["initial_score"]["correct"] for r in rows
        )
        summary = data["summary"]["policies"][policy]
        policies[policy] = summary | {
            "scheduled_tasks": 120,
            "accuracy_over_scheduled_tasks": summary["correct"] / 120,
            "incomplete_tasks": len(incomplete),
            "unresolved_rate_over_scheduled_tasks": (summary["failures"] + len(incomplete)) / 120,
            "median_path_latency_ms": float(np.median(latencies)) if latencies else None,
            "p95_path_latency_ms": float(np.quantile(latencies, 0.95)) if latencies else None,
            "rescue_opportunities": wrong_initial,
            "rescue_rate": summary["critic_rescues"] / wrong_initial if wrong_initial else None,
            "regression_opportunities": correct_initial,
            "regression_rate": summary["critic_regressions"] / correct_initial
            if correct_initial
            else None,
        }
    changes = []
    for row in rows:
        for name, arm in row["arms"].items():
            if arm["score"]["correct"] != row["initial_score"]["correct"]:
                changes.append(
                    {
                        "task_id": row["task_id"],
                        "category": row["category"],
                        "policy": name,
                        "initial_correct": row["initial_score"]["correct"],
                        "final_correct": arm["score"]["correct"],
                        "critic_call_ref": arm.get("critic_call_ref"),
                        "error": arm.get("error"),
                    }
                )
    elapsed = (
        datetime.fromisoformat(data["completed_at"]) - datetime.fromisoformat(data["started_at"])
    ).total_seconds()
    return {
        "run_id": run["id"],
        "status": run["status"],
        "error": data.get("error"),
        "scheduled_tasks": 120,
        "completed_tasks": len(rows),
        "incomplete_tasks": incomplete,
        "policies": policies,
        "categories": categories,
        "rescues_and_regressions": changes,
        "paired_intervals": data["summary"]["paired_intervals"],
        "selection_errors": data["summary"]["selection_errors"],
        "physical_calls": data["physical_calls"],
        "charged_tokens": data["charged_tokens"],
        "reported_tokens": data["summary"]["reported_unique_tokens"],
        "estimated_usd": data["summary"]["estimated_unique_usd"],
        "conservatively_charged_usd": charged_micro_usd(data["ledger"]) / 1e6,
        "unknown_usage_calls": data["summary"]["unknown_usage_calls"],
        "run_deadline_timeouts": int(data.get("error") == "TimeoutError"),
        "run_wall_seconds": elapsed,
        "paired_task_wall_seconds": sum(r.get("paired_execution_wall_ms", 0) for r in rows) / 1000,
        "confirmed_provider_billing": None,
        "same_initial_is_not_independent_trials": True,
    }


async def audit_events(settings, plan):
    db = Database(settings.database_url)
    async with db.sessions() as session:
        authorization = await session.get(ExperimentAuthorization, plan["authorization"]["id"])
        events = (
            await session.scalars(
                select(Event)
                .where(Event.event_type.like("experiment.%"))
                .order_by(Event.sequence_number)
            )
        ).all()
        selected = [
            record(e)
            for e in events
            if e.payload.get("run_id") == plan["run_id"]
            or e.payload.get("authorization_id") == authorization.id
        ]
        result = {"authorization": record(authorization), "events": selected}
    await db.engine.dispose()
    return result


def main():
    root = Path("archives/ALIVE-03-P1-FULL")
    if root.exists():
        raise SystemExit("Full-run archive already exists; refusing overwrite")
    plan = json.loads(Path(".alive/full-evaluation-plan.json").read_text())
    settings = Settings()
    c = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=30,
        headers={"Authorization": "Bearer " + prepare_local(settings)},
    )
    response = c.get("/experiments/runs/" + plan["run_id"])
    response.raise_for_status()
    run = response.json()
    assert run["status"] != "running", "Wait for the run to finish before analysis"
    verify(plan["freeze_id"])
    for path, expected in plan["execution_overlay"].items():
        assert file_hash(path) == expected, "Execution overlay changed"
    analysis = analyze(run)
    assert analysis["physical_calls"] <= 350 and analysis["charged_tokens"] <= 500000
    assert analysis["conservatively_charged_usd"] <= 1
    audit = asyncio.run(audit_events(settings, plan))
    checks = [e for e in audit["events"] if e["event_type"] == "experiment.usd_reservation_checked"]
    assert len(checks) == analysis["physical_calls"]
    assert all(
        e["payload"]["charged_micro_usd"] + e["payload"]["next_reserved_micro_usd"] <= 1000000
        for e in checks
    )
    budget_response = c.get("/cognition")
    budget_response.raise_for_status()
    control = budget_response.json()["control"]
    root.mkdir(parents=True)

    def redact(value):
        if isinstance(value, dict):
            return {
                k: redact(v)
                for k, v in value.items()
                if k not in {"instance_id", "topics", "origins", "preferred_action"}
            }
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    def write(name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(redact(value), indent=2, default=str) + "\n"
        assert settings.alive_meta_api_key not in text
        path.write_bytes(text.encode())

    write("execution-plan.json", plan)
    write("results.json", run)
    write("analysis.json", analysis)
    write("authorization-and-budget-audit.json", audit)
    write("redacted-usage-ledger.json", run["data"]["ledger"])
    write("governor-after.json", {k: control[k] for k in ["configuration", "spent", "reserved"]})
    write(
        "unchanged-freeze.json",
        json.loads(Path("benchmarks/alive03-p1/freeze-final.json").read_text()),
    )
    table = io.StringIO(newline="")
    writer = csv.writer(table)
    writer.writerow(
        [
            "task_id",
            "category",
            "family",
            "policy",
            "initial_correct",
            "correct",
            "correct_abstention",
            "unsupported_claim_acceptance",
            "critic_invoked",
            "allocated_tokens",
            "estimated_path_usd",
            "path_latency_ms",
            "error",
            "score_reason",
            "selection_reason",
            "critic_call_ref",
        ]
    )
    for row in run["data"]["rows"]:
        for name, arm in row["arms"].items():
            writer.writerow(
                [
                    row["task_id"],
                    row["category"],
                    row["family"],
                    name,
                    row["initial_score"]["correct"],
                    arm["score"]["correct"],
                    arm["score"]["correct_abstention"],
                    arm["score"]["unsupported_acceptance"],
                    arm["invoked"],
                    arm["allocated_tokens"],
                    arm["estimated_usd"],
                    arm["end_to_end_latency_ms"],
                    arm.get("error"),
                    arm["score"]["reason"],
                    arm["choice"]["reason"],
                    arm.get("critic_call_ref"),
                ]
            )
    (root / "paired-outcomes.csv").write_bytes(table.getvalue().encode())
    shutil.copyfile(".alive/full-evaluation-tests.txt", root / "backend-tests.txt")
    shutil.copyfile(".alive/full-report-tests.txt", root / "report-tests.txt")
    if Path(".alive/full-evaluation-acceptance.png").exists():
        shutil.copyfile(".alive/full-evaluation-acceptance.png", root / "acceptance.png")
    if Path(".alive/full-evaluation-browser-tests.txt").exists():
        shutil.copyfile(".alive/full-evaluation-browser-tests.txt", root / "browser-tests.txt")
    policy_lines = []

    def money(value):
        return "unknown" if value is None else f"${value:.6f}"

    for name, p in analysis["policies"].items():
        policy_lines.append(
            f"| {name} | {p['correct']}/120 | {p['correct_abstentions']} | "
            f"{p['critic_calls']} | {p['allocated_tokens']:,} | "
            f"{money(p['estimated_usd'])} | "
            f"{p['mean_end_to_end_latency_ms'] / 1000:.3f} |"
        )
    category_lines = []
    for category, items in analysis["categories"].items():
        category_lines.append(
            "| "
            + category
            + " | "
            + " | ".join(f"{items[p]['correct']}/30" for p in ["always", "never", "selective"])
            + " |"
        )
    spent = control["spent"]
    budget = control["configuration"]
    remaining_calls = budget["experiment_calls"] - spent.get("experiment_calls", 0)
    remaining_tokens = budget["experiment_tokens"] - spent.get("experiment_tokens", 0)
    all_tied = len({p["correct"] for p in analysis["policies"].values()}) == 1
    verdict = (
        "All policies tie on correctness; no adaptive-selection advantage demonstrated."
        if all_tied
        else "Correctness differs; inspect the paired outcomes and intervals."
    )
    report = f"""# ALIVE-03-P1 — Authorized full evaluation

**{verdict}**

Run `{run["id"]}`: **{run["status"]}**, {analysis["completed_tasks"]}/120 completed tasks.
Run error: `{analysis["error"]}`. Incomplete tasks: {len(analysis["incomplete_tasks"])}.
Execution commit: `{plan["execution_commit"]}` on `codex/alive-03-p1-selective-cognition`.
No push, merge, deployment, main changes or predictive-policy training.

## Frozen experiment and execution controls

Original freeze `{plan["freeze_id"]}` is unchanged from the qualification archive.
Corpus (120 held-out tasks, 30/category), schema, policy threshold 1.1, scorer, prompts,
model `muse-spark-1.3` and frozen runner were not changed. No policy tuning followed
pilot or evaluation outcomes. The dollar guard is a separately hashed execution overlay,
committed and tested before the first held-out inference. It only restricts calls.

Owner explicitly authorized **$1.00, 350 calls, 500,000 tokens**. The larger account balance
was not treated as permission to bypass these experiment limits. Authorization was persisted
and consumed once. Calls were sequential, with zero automatic retries and the original
90-second paired-task deadline. Two planned 60-task sessions preserved cumulative counters.

Every physical call has a persisted pre-inference USD reservation check; {len(checks)} checks
verified within the ceiling. Known usage uses the published rates; unknown/failed usage is
charged conservatively at the maximum rate against reserved tokens. Reservations and upward
rounding can stop a run below $1.00. This is an application rate-card guard, not account billing.

## Outcomes

| Policy | Correct | Abstentions | Critic calls | Path tokens | Path USD (est.) | Mean seconds |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(policy_lines)}

| Category | Always | Never | Selective |
|---|---:|---:|---:|
{chr(10).join(category_lines)}

The full machine-readable analysis includes unsupported claim acceptance, citation validity,
abstention precision/recall, failure and timeout rates, rescue/regression rates and opportunities,
median/p95 latency, selection errors and paired uncertainty intervals. `paired-outcomes.csv`
preserves each arm's score, invocation reason, cost, latency and error. A null rescue rate
means no incorrect initial decisions supplied rescue opportunities; it does not mean measured
rescue probability is zero.

Correctness transitions after criticism: **{len(analysis["rescues_and_regressions"])}**;
see `analysis.json` for task IDs and outcomes. Selection errors are observed Always-arm proxies,
not guaranteed counterfactuals for an independently sampled Selective Critic.

## Actual usage, cost and latency

- Physical calls: **{analysis["physical_calls"]} / 350**.
- Provider-reported tokens: **{analysis["reported_tokens"]:,}**;
  Governor-charged tokens: **{analysis["charged_tokens"]:,} / 500,000**.
- Estimated unique physical cost: **{money(analysis["estimated_usd"])}**;
  conservative spending-guard charge: **${analysis["conservatively_charged_usd"]:.6f} / $1.00**.
- Unknown-usage calls: **{analysis["unknown_usage_calls"]}**.
- Wall time including database accounting and scheduling: **{analysis["run_wall_seconds"]:.1f}s**;
  summed paired-task wall time: **{analysis["paired_task_wall_seconds"]:.1f}s**.
- Remaining cumulative Governor budget: **{remaining_calls} calls, {remaining_tokens:,} tokens**.

Rate-card estimates use [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), rechecked
before execution: $1.25/M input, $0.15/M cached input and $4.25/M output. Reasoning tokens are
included in completion tokens. **Confirmed provider billing is unavailable.**

One initial decision is shared across all three arms; it is paid once physically but included
in each path comparison. Do not add policy path costs to estimate billing. Policy latency
includes its own initial/review and Governor I/O, excluding competing-arm queue time; paired
task wall time includes both arms. These are not independently timed deployments.

## Interpretation and limits

The calibrated threshold is 1.1, so Selective behaves exactly like Never on every possible
feature vector. Their shared-artifact outcomes are mechanically identical, not independent
replication. This experiment can measure the incremental value of the Always Critic and
the consequence of calibration choosing no criticism; it cannot demonstrate adaptive routing
across situations when the selected policy never invokes its Critic.

The numerical corpus is narrow, with explicit source-authority rules and synthetic adversarial
annotations. Disjoint operation families and lexical audits reduce contamination but do not
prove semantic independence. The evaluation file was procedurally sealed plaintext, not blind
to generator authors. Only six task families limit uncertainty estimation. Wilson intervals
are descriptive; paired intervals use the predeclared 2,000 family-cluster bootstrap resamples.
Degenerate zero-difference intervals are conditional on this corpus, not guarantees of
equivalence on new distributions. Calibration used only eight development pairs.

Failure rows and incomplete tasks are preserved; scheduled-task accuracy and unresolved rates
use 120 as the denominator. Other arm rates describe completed rows. No failure was retried
to replace an unfavorable outcome. Negative or tied
findings do not establish that criticism is generally useless. Further research should test
an independently developed evidence-backed criticism mechanism or a harder, newly frozen
corpus before adding policy learning. No P2 work was started automatically.

## Evidence

`results.json` contains all recorded decisions and per-call data. `redacted-usage-ledger.json`
retains synthetic inputs, structured outputs, prompts, correlation IDs, usage and latency.
`authorization-and-budget-audit.json` records the one-use authorization, all USD checks,
Governor reservations/settlements, session boundary and completion. Credentials, request
headers, runtime identity and personal browser data are excluded. `execution-plan.json`
contains the pre-unsealing overlay hashes and budget settings. The original qualification
archive remains intact. Pre-execution backend suite: 58 passing (55 prior + 3 spending tests).
Two additional postprocessing tests pass, checking retained failures, unknown costs and
scheduled-task denominators. They do not change the experiment or its inference decisions.

`manifest.json` hashes every evidence payload except itself. The evidence commit follows the
execution commit; use `git log` for final HEAD. The pre-existing untracked `models.txt` remains
outside the commits.
"""
    (root / "README.md").write_bytes(report.encode())
    (root / ".gitattributes").write_bytes(b"* -text whitespace=cr-at-eol\n")
    manifest = {
        p.relative_to(root).as_posix(): {
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
    write(
        "manifest.json",
        {
            "run_id": run["id"],
            "freeze_id": plan["freeze_id"],
            "execution_commit": plan["execution_commit"],
            "files": manifest,
        },
    )
    print(
        json.dumps(
            {
                k: analysis[k]
                for k in [
                    "status",
                    "completed_tasks",
                    "physical_calls",
                    "reported_tokens",
                    "estimated_usd",
                ]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
