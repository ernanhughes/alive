"""Governor budget accounting: reservations, settlement, and spend guards.

Canonical runtime home for the resource-settlement logic previously owned by
the ALIVE-03 experimental runner (``Experiments._settle_control``) and the
spend-guard helpers in ``alive.experiment_budget``.

A reservation is taken before inference and settled exactly once afterwards:

- ``reserved`` tracks outstanding (unsettled) calls/tokens,
- ``spent`` accumulates completed ``session_*`` and ``experiment_*`` usage.

All helpers are pure accounting over the ``CognitiveControl`` row; they never
perform inference or touch experiment corpora.
"""

from decimal import ROUND_CEILING, Decimal

from alive.governance.pricing import price


def settle_control(control, reserved, charged):
    """Settle one Governor reservation against ``control``.

    ``reserved`` is the pre-inference token reservation; ``charged`` is the
    post-inference billed amount (both in tokens). Exactly one call is moved
    from ``reserved`` to ``spent`` for the ``session_`` and ``experiment_``
    budget prefixes.
    """
    control.reserved = control.reserved | {
        "calls": max(0, control.reserved.get("calls", 0) - 1),
        "tokens": max(0, control.reserved.get("tokens", 0) - reserved),
    }
    control.spent = (
        control.spent
        | {
            prefix + "calls": control.spent.get(prefix + "calls", 0) + 1
            for prefix in ["session_", "experiment_"]
        }
        | {
            prefix + "tokens": control.spent.get(prefix + "tokens", 0) + charged
            for prefix in ["session_", "experiment_"]
        }
    )


def worst_micro_usd(tokens):
    # $4.25/M is the highest pinned-model token rate. Integer rounding is upward.
    return (tokens * 17 + 3) // 4


def charged_micro_usd(ledger):
    total = 0
    for call in ledger:
        estimate = price(call.get("usage"))
        if call["status"] != "validated" or estimate is None:
            tokens = call.get("cost_liability_tokens", call["reserved_tokens"])
            total += worst_micro_usd(tokens)
        else:
            total += int(
                (Decimal(str(estimate)) * 1000000).to_integral_value(rounding=ROUND_CEILING)
            )
    return total


def check_spend(ledger, reserved_tokens, cap):
    charged = charged_micro_usd(ledger)
    reserved = worst_micro_usd(reserved_tokens)
    if charged + reserved > cap:
        raise ValueError("Application USD ceiling exhausted before inference")
    return {
        "charged_micro_usd": charged,
        "next_reserved_micro_usd": reserved,
        "ceiling_micro_usd": cap,
    }
