"""Single audited dispatch seam for model invocations (ALIVE-PI-01A).

`DirectMetaGateway` preserves the exact `MetaProvider.structured` call previously
made inline by cognition roles. No behaviour change: same request body, same
headers, same reservation and accounting (those stay with the caller).

PI-01B will add a Pi-backed gateway behind this same protocol; every other
`MetaProvider` construction site is enumerated in the ratchet allow-list in
`tests/test_model_gateway.py` and must not gain new siblings.
"""

from dataclasses import dataclass
from typing import Protocol

from alive.providers import Generation, MetaProvider


@dataclass(frozen=True)
class StructuredRequest:
    operation: str
    instructions: str
    data: dict
    schema: dict
    model: str
    max_output: int
    correlation: str | None = None


class ModelGateway(Protocol):
    async def structured(self, req: StructuredRequest) -> Generation: ...


class DirectMetaGateway:
    """Production gateway: unchanged MetaProvider dispatch."""

    def __init__(self, settings, transport=None):
        self.settings = settings
        # Test seam only: an httpx transport for the upstream call. None in
        # production, where the real Meta endpoint is used.
        self.transport = transport

    async def structured(self, req: StructuredRequest) -> Generation:
        return await MetaProvider(self.settings).structured(
            req.instructions,
            req.data,
            req.schema,
            model=req.model,
            max_output=req.max_output,
            correlation=req.correlation,
            transport=self.transport,
        )


def gateway_for(settings, operation: str) -> ModelGateway:
    """Return the gateway for an operation. Unknown operations fail closed."""
    if operation == "cognition.role":
        return DirectMetaGateway(settings)
    raise KeyError(f"No gateway registered for operation {operation!r}")
