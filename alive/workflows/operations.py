"""Legacy descriptive operation view, derived from the startup capability catalogue.

`available` retains PI-02A's underlying-function meaning. `executable` means a
reviewed workflow adapter is installed; neither field grants execution authority.
"""

from alive.capabilities.registry import Operation as Operation
from alive.capabilities.registry import default_registry

OPERATIONS = default_registry().operations


def public_view(operation):
    return {
        "id": operation.id,
        "kind": operation.kind,
        "summary": operation.summary,
        "side_effects": operation.side_effects,
        "available": operation.available,
        "executable": operation.executable,
        "workflow_unavailable_reason": operation.workflow_unavailable_reason,
        "binding": operation.binding,
        "unavailable_reason": operation.unavailable_reason,
    }
