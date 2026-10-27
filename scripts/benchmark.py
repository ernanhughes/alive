"""Bounded A/B/C + no-Critic benchmark. Paid bulk inference requires --allow-paid."""

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

from filelock import FileLock

from alive.attention import attention
from alive.cognitive_schema import RoleOutput
from alive.config import Settings
from alive.providers import MetaProvider
from alive.society import ROLE_SPEC_VERSION, evaluate, mock_role, role_prompt, validate_references


class BenchmarkBudget:
    def __init__(self, path, max_calls, max_tokens):
        if not 1 <= max_calls <= 100 or not 1 <= max_tokens <= 2000000:
            raise ValueError("Experimental ceiling must be 1–100 calls and 1–2,000,000 tokens")
        self.path, self.max_calls, self.max_tokens = Path(path), max_calls, max_tokens
        self.data = (
            json.loads(self.path.read_text())
            if self.path.exists()
            else {"calls": 0, "tokens": 0, "invocations": []}
        )

    def reserve(self, tokens, role, model):
        if (
            self.data["calls"] + 1 > self.max_calls
            or self.data["tokens"] + tokens > self.max_tokens
        ):
            raise RuntimeError("Persistent experimental budget exhausted before model request")
        self.data["calls"] += 1
        self.data["tokens"] += tokens
        call = {"role": role, "model": model, "status": "reserved", "reserved_tokens": tokens}
        self.data["invocations"].append(call)
        self.save()
        return call

    def settle(self, call, usage, latency, output):
        actual = usage.get("total_tokens")
        if not isinstance(actual, int) or actual < 0:
            actual = call["reserved_tokens"]
        self.data["tokens"] += actual - call["reserved_tokens"]
        call.update(
            {
                "status": "validated",
                "usage": usage,
                "latency_ms": latency,
                "output": output,
                "charged_tokens": actual,
            }
        )
        self.save()
        if actual > call["reserved_tokens"]:
            raise RuntimeError("Provider exceeded token reservation")

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2))


async def run_benchmark(
    provider="mock",
    allow_paid=False,
    max_calls=30,
    max_tokens=100000,
    evidence_access="shared",
    output=".alive/benchmark.json",
    ledger=".alive/benchmark-ledger.json",
    dataset_path="benchmarks/cases.json",
):
    if provider == "meta" and not allow_paid:
        raise ValueError("Paid bulk experiment requires explicit --allow-paid opt-in")
    settings = Settings()
    document = Path(dataset_path).read_text()
    dataset = json.loads(document)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    budget = BenchmarkBudget(ledger, max_calls, max_tokens) if provider == "meta" else None
    if provider == "meta":
        catalog = await MetaProvider(settings).discover()
        if settings.alive_meta_model not in catalog.get("models", []):
            raise ValueError("Pinned Meta benchmark model is not available")
    results = []

    async def invoke(role, context):
        request_context = dict(context)
        if evidence_access == "critic_only" and role != "critic":
            request_context["sources"] = []
        if evidence_access == "proposer_only" and role != "proposer":
            request_context["sources"] = []
        started = time.monotonic()
        prompt = role_prompt(role)
        if provider == "mock":
            result = mock_role(role, request_context)
            return result, {
                "provider": "mock",
                "model": "controlled-role-fixture-v1",
                "role": role,
                "latency_ms": (time.monotonic() - started) * 1000,
                "usage": {"total_tokens": 0},
                "output": result.model_dump(),
            }
        reserved = (
            len(
                json.dumps(
                    {
                        "instructions": prompt,
                        "context": request_context,
                        "schema": RoleOutput.model_json_schema(),
                    }
                ).encode()
            )
            + 1024
            + settings.alive_meta_max_output
        )
        call = budget.reserve(reserved, role, settings.alive_meta_model)
        call["input"] = {
            "role_spec_version": ROLE_SPEC_VERSION,
            "instructions": prompt,
            "context": request_context,
        }
        budget.save()
        try:
            generation = await MetaProvider(settings).structured(
                prompt,
                request_context,
                RoleOutput.model_json_schema(),
                max_output=settings.alive_meta_max_output,
            )
            result = RoleOutput.model_validate_json(generation.text)
            validate_references(result, request_context)
            budget.settle(call, generation.usage, generation.latency_ms, result.model_dump())
            return result, dict(call) | {"provider": "meta"}
        except Exception as exc:
            call.update(
                {
                    "status": "failed",
                    "error": type(exc).__name__,
                    "latency_ms": (time.monotonic() - started) * 1000,
                }
            )
            call["usage"] = getattr(exc, "usage", {})
            budget.save()
            raise

    for arm in ["A_direct", "B_fixed", "C_adaptive", "C_without_critic"]:
        for case in dataset["cases"]:
            started = time.monotonic()
            calls = []
            error = None
            proposal = None
            context = {key: case[key] for key in ["observation", "claims", "sources"]} | {
                "memories": [],
                "source_event_ids": [],
            }
            bid = attention(case["observation"], ["battery endurance", "coolant temperature"])
            selected = (
                arm in ("A_direct", "B_fixed") or bid["relevance"] > 0 and bid["score"] >= 0.45
            )
            try:
                if selected:
                    roles = (
                        ["proposer"]
                        if arm == "A_direct"
                        else ["observer", "proposer"]
                        + ([] if arm == "C_without_critic" else ["critic"])
                        + (["evaluator"] if arm == "B_fixed" else [])
                    )
                    for role in roles:
                        output_role, call = await invoke(role, context)
                        calls.append(call)
                        context[role] = output_role.model_dump()
                        if role == "proposer":
                            proposal = output_role
                result = evaluate(
                    case["claims"],
                    [c.model_dump() for c in proposal.claims] if proposal else [],
                    case["sources"],
                )
                detected = bool(
                    selected
                    and proposal
                    and proposal.claims
                    and proposal.actions
                    and proposal.recommendation != "abstain"
                    and context.get("critic", {}).get("recommendation") != "abstain"
                )
                correct = (
                    (not detected)
                    if not case["relevant"]
                    else detected and result["conclusion_status"] == "VERIFIED"
                )
            except Exception as exc:
                result = {"status": "FAILED", "conclusion_status": "FAILED"}
                detected = selected
                correct = False
                error = str(exc)
            results.append(
                {
                    "arm": arm,
                    "case_id": case["id"],
                    "split": dataset["split"],
                    "selected": selected,
                    "detected": detected,
                    "relevant": case["relevant"],
                    "decision_correct": correct,
                    "grounded_evaluation": result,
                    "expected_observation_status": case["expected_status"],
                    "calls": calls,
                    "logical_model_calls": len(calls),
                    "reported_tokens": sum(
                        c.get("usage", {}).get("total_tokens", 0) for c in calls
                    ),
                    "unnecessary_escalations": len(calls) if not case["relevant"] else 0,
                    "latency_ms": (time.monotonic() - started) * 1000,
                    "error": error,
                    "attention": bid,
                    "unauthorised_actions": 0,
                    "actions_executed": False,
                    "authority_note": "Benchmark decisions do not execute actions; "
                    "Governor enforcement is tested separately",
                }
            )
            print(
                arm, case["id"], "correct=" + str(correct), "calls=" + str(len(calls)), flush=True
            )
    metrics = {}
    for arm in sorted({r["arm"] for r in results}):
        rows = [r for r in results if r["arm"] == arm]
        tp = sum(r["detected"] and r["relevant"] for r in rows)
        fp = sum(r["detected"] and not r["relevant"] for r in rows)
        fn = sum(not r["detected"] and r["relevant"] for r in rows)
        success = sum(r["decision_correct"] for r in rows)
        tokens = sum(r["reported_tokens"] for r in rows)
        metrics[arm] = {
            "cases": len(rows),
            "detection_precision": tp / (tp + fp) if tp + fp else None,
            "detection_recall": tp / (tp + fn) if tp + fn else None,
            "decision_correctness": success / len(rows),
            "goal_usefulness_proxy": "Relevant event detected with source-verified proposed claims",
            "useful_goals": sum(r["decision_correct"] and r["relevant"] for r in rows),
            "unnecessary_escalations": sum(r["unnecessary_escalations"] for r in rows),
            "reported_tokens": tokens,
            "tokens_per_success": tokens / success if success else None,
            "cost_usd_per_success": None,
            "latency_ms": sum(r["latency_ms"] for r in rows),
            "failures": sum(bool(r["error"]) for r in rows),
            "abstentions": sum(not r["detected"] for r in rows),
        }
    report = {
        "schema_version": 1,
        "provider": provider,
        "model": settings.alive_meta_model if provider == "meta" else "controlled-role-fixture-v1",
        "dataset_version": dataset["dataset_version"],
        "dataset_path": dataset_path,
        "role_spec_version": ROLE_SPEC_VERSION,
        "role_prompts": {
            role: role_prompt(role) for role in ["observer", "proposer", "critic", "evaluator"]
        },
        "dataset_sha256": hashlib.sha256(document.encode()).hexdigest(),
        "split": dataset["split"],
        "evidence_access": evidence_access,
        "metrics": metrics,
        "results": results,
        "limitations": [
            "Three synthetic cases cannot establish general model quality "
            "or statistical significance.",
            "Same deterministic evaluator and pinned model across arms; "
            "no stochastic replay claim.",
            "Dollar costs unknown without provider billing; token cost is recorded.",
            "Failure recovery and actual action enforcement are qualified separately "
            "by acceptance/tests.",
        ],
        "persistent_budget": budget.data if budget else None,
    }
    Path(output).write_text(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "meta"], default="mock")
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--max-calls", type=int, default=30)
    parser.add_argument("--max-tokens", type=int, default=100000)
    parser.add_argument("--dataset-path", default="benchmarks/cases.json")
    parser.add_argument("--output", default=".alive/benchmark.json")
    parser.add_argument("--ledger", default=".alive/benchmark-ledger.json")
    parser.add_argument(
        "--evidence-access", choices=["shared", "critic_only", "proposer_only"], default="shared"
    )
    args = parser.parse_args()
    Path(".alive").mkdir(exist_ok=True)
    with FileLock(".alive/benchmark.lock", timeout=0):
        asyncio.run(run_benchmark(**vars(args)))


if __name__ == "__main__":
    main()
