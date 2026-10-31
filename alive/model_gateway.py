"""Single audited dispatch seam for model invocations (ALIVE-PI-01A).

`DirectMetaGateway` preserves the exact `MetaProvider.structured` call previously
made inline by cognition roles. No behaviour change: same request body, same
headers, same reservation and accounting (those stay with the caller).

PI-01B adds a Pi-backed gateway (`alive.pi.gateway.PiGateway`) behind this same protocol, selected
by `ALIVE_MODEL_TRANSPORT=pi` (default `direct`); every other
`MetaProvider` construction site is enumerated in the ratchet allow-list in
`tests/test_model_gateway.py` and must not gain new siblings.
"""

from copy import deepcopy
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

    def __init__(self, settings, operation: str, transport=None):
        # Pin dispatch configuration before Pi starts. A settings mutation after the final
        # authority check must never substitute the destination of an already approved call.
        self.settings = deepcopy(settings)
        self.operation = operation
        # Test seam only: an httpx transport for the upstream call. None in
        # production, where the real Meta endpoint is used.
        self.transport = transport

    async def structured(self, req: StructuredRequest) -> Generation:
        if req.operation != self.operation:
            raise ValueError(
                f"Operation mismatch: gateway serves {self.operation!r}, "
                f"request claims {req.operation!r}; refusing dispatch"
            )
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
        if settings.alive_model_transport == "pi":
            # Imported lazily so the default (direct) path never loads any Pi code.
            from alive.pi.gateway import PiGateway

            return PiGateway(settings, operation)
        return DirectMetaGateway(settings, operation=operation)
    raise KeyError(f"No gateway registered for operation {operation!r}")
