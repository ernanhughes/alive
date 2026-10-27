from types import SimpleNamespace

import pytest

from alive.experiment.metrics import summarize
from scripts import report_frozen03 as report


@pytest.mark.parametrize("valid", [False, True])
def test_full_report_retains_failures_unknown_cost_and_scheduled_denominators(monkeypatch, valid):
    tasks = [
        SimpleNamespace(
            id=str(i),
            category=["straightforward", "ambiguous", "contradictory", "adversarial"][i // 30],
        )
        for i in range(120)
    ]
    monkeypatch.setattr(report, "load", lambda split: tasks)
    score = {
        "correct": valid,
        "correct_abstention": False,
        "abstained": False,
        "unsupported_acceptance": False,
        "expected_status": "ANSWER",
        "citation_validity": 1 if valid else None,
    }
    arms = {
        p: {
            "score": score,
            "invoked": p == "always" and valid,
            "error": None if valid else "invalid_response",
            "allocated_tokens": 0,
            "estimated_usd": 0 if valid else None,
            "path_latency_ms": 1,
            "end_to_end_latency_ms": 2,
        }
        for p in ["always", "never", "selective"]
    }
    rows = [
        {
            "task_id": "0",
            "category": "straightforward",
            "family": "fixture",
            "eligible": valid,
            "initial_score": {"correct": valid},
            "arms": arms,
        }
    ]
    ledger = [{"status": "failed", "reserved_tokens": 2000, "usage": None}]
    data = {
        "rows": rows,
        "ledger": ledger,
        "summary": summarize(rows, ledger),
        "started_at": "2026-10-26T00:00:00+00:00",
        "completed_at": "2026-10-26T00:00:01+00:00",
        "physical_calls": 1,
        "charged_tokens": 2000,
        "error": "TimeoutError",
    }
    result = report.analyze({"id": "fixture", "status": "failed", "data": data})
    assert len(result["incomplete_tasks"]) == 119
    assert result["run_deadline_timeouts"] == 1
    assert result["estimated_usd"] is None and result["unknown_usage_calls"] == 1
    assert result["conservatively_charged_usd"] == 0.0085
    for p in result["policies"].values():
        assert p["accuracy_over_scheduled_tasks"] == int(valid) / 120
        assert p["rescue_opportunities"] == 0
        assert p["unresolved_rate_over_scheduled_tasks"] == (119 if valid else 120) / 120
