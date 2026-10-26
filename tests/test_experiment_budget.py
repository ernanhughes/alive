import pytest

from alive.experiment_budget import charged_micro_usd, check_spend, worst_micro_usd


def test_spending_ceiling_prevents_call_and_rounds_up():
    assert worst_micro_usd(1) == 5
    assert worst_micro_usd(4000) == 17000
    assert check_spend([], 4000, cap=17000)["next_reserved_micro_usd"] == 17000
    with pytest.raises(ValueError, match="USD ceiling"):
        check_spend([], 4000, cap=16999)


def test_unknown_and_failed_usage_charged_conservatively():
    ledger = [
        {"status": "reserved", "reserved_tokens": 4000, "usage": None},
        {
            "status": "failed",
            "reserved_tokens": 4000,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    ]
    assert charged_micro_usd(ledger) == 34000
    with pytest.raises(ValueError):
        check_spend(ledger, 4000, cap=50999)


def test_completed_usage_counts_cached_and_completion_once():
    ledger = [
        {
            "status": "validated",
            "reserved_tokens": 999999,
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "prompt_tokens_details": {"cached_tokens": 500},
            },
        }
    ]
    assert charged_micro_usd(ledger) == 1125
    with pytest.raises(ValueError):
        check_spend(ledger, 1, cap=1129)
