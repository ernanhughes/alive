"""Runtime governance: budgets, pricing, and content hashing.

This package owns the reusable runtime capabilities that were previously
reached through the ALIVE-03 research harness:

- token/USD pricing (rate-card estimates, never billing),
- Governor budget reservation and settlement,
- deterministic file hashing for freeze manifests.

Research harnesses under ``experiments/`` may depend on this package.
Nothing in this package may import ``alive.experiment`` or ``experiments``.
"""

from alive.governance.budgets import (
    charged_micro_usd,
    check_spend,
    settle_control,
    worst_micro_usd,
)
from alive.governance.hashing import file_hash
from alive.governance.pricing import price

__all__ = [
    "charged_micro_usd",
    "check_spend",
    "file_hash",
    "price",
    "settle_control",
    "worst_micro_usd",
]
