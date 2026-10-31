"""Compare a gated fixed default with deterministic context selection on held-out fixtures."""

import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter

from alive.models import uid

ROOT = Path(__file__).resolve().parents[1]


def run_cases(client, request, *, repository):
    dataset = json.loads((ROOT / "docs/bespoke/evaluation/cases-v1.json").read_text())
    results = []
    for case in dataset["cases"]:
        if case["surface"] != ("repository" if repository else "sources"):
            continue
        body = request | case["override"] | {"idempotency_key": uid()}
        start = perf_counter()
        response = client.post("/api/v1/bespoke/recommend", json=body)
        elapsed = perf_counter() - start
        choice = fixed = None
        reasons, diversity, stable = [], 0, True
        explanation_consistent = provenance_correct = budget_compliant = True
        if response.status_code == 200:
            selection = response.json()["selection"]
            candidates = selection["candidates"]
            selected = next(
                (
                    c
                    for c in candidates
                    if c["recipe_sha256"] == selection["selected_recipe_sha256"]
                ),
                None,
            )
            choice = selected["recipe"]["id"] if selected else None
            default = next(
                (c for c in candidates if c["recipe"]["id"] == "controlled-comparison"), None
            )
            fixed = default["recipe"]["id"] if default and default["eligible"] else None
            reasons = sorted({r for c in candidates for r in c["reasons"]})
            diversity = selection["distinct_procedures"]
            replay = client.post(
                "/api/v1/bespoke/recommend", json=body | {"idempotency_key": uid()}
            )
            stable = replay.status_code == 200 and replay.json()["selection"] == selection
            explanation_consistent = all(
                c["suitability"] == sum(c["factors"].values())
                and c["eligible"] == (not c["reasons"])
                for c in candidates
            )
            provenance_correct = selection["context"]["source_ref"] == request["source_ref"]
            if selected:
                limits = selected["recipe"]["limits"]
                ceiling = selection["constraints"]
                budget_compliant = all(
                    limits[k] <= ceiling[k]
                    for k in ("max_model_calls", "max_wall_seconds", "max_output_tokens")
                )
        correct = response.status_code == case["status"] and choice == case["recipe"]
        correct &= "reason" not in case or case["reason"] in reasons
        result = {
            "id": case["id"],
            "split": case["split"],
            "status": response.status_code,
            "expected_recipe": case["recipe"],
            "selected": choice,
            "fixed_default": fixed,
            "correct": correct,
            "fixed_correct": fixed == case["recipe"],
            "unauthorized_selection": bool(choice and not case["recipe"]),
            "ranking_stable": stable,
            "diversity": diversity,
            "explanation_consistent": explanation_consistent,
            "provenance_correct": provenance_correct,
            "budget_compliant": budget_compliant,
            "seconds": elapsed,
            "model_calls": 0,
        }
        results.append(result)
        assert (
            correct
            and stable
            and explanation_consistent
            and provenance_correct
            and budget_compliant
        ), result
    return results


def main():
    from scripts.bespoke_check import scenario

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="alive-bespoke-evaluation-") as directory:
        results = []
        for repository in (False, True):
            receipt, _ = scenario(
                Path(directory) / str(repository), repository=repository, evaluate=True
            )
            results.extend(receipt["evaluation"])
    result = {
        "protocol": "bespoke-evaluation/v1",
        "cases": results,
        "deterministic_correct": sum(r["correct"] for r in results),
        "fixed_default_correct": sum(r["fixed_correct"] for r in results),
        "unauthorized_selections": sum(r["unauthorized_selection"] for r in results),
        "model_assisted": "not implemented or invoked",
        "task_quality": "not measured; suitability is not independently verified success",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}))


if __name__ == "__main__":
    main()
