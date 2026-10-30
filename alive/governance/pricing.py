"""Rate-card USD estimates for metered model usage.

Canonical runtime home for the pricing helper historically reached via
``alive.experiment.metrics.price``. The frozen research copy is left
byte-identical for reproducibility; new production code must import from here.

Values are estimates only, never confirmed billing.
"""


def price(usage):
    if not usage or "prompt_tokens" not in usage or "completion_tokens" not in usage:
        return None
    cached = min(
        usage["prompt_tokens"], usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    )
    return (
        (usage["prompt_tokens"] - cached) * 1.25 + cached * 0.15 + usage["completion_tokens"] * 4.25
    ) / 1e6
