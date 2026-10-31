"""Provider-neutral data contracts shared by governance and model transport.

This module must not resolve destinations, authorize execution, or import provider clients.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedModelDestination:
    """Immutable owner-admission identity carried by trusted execution, never model output."""

    admission_id: str
    review_sha256: str
    endpoint: str
