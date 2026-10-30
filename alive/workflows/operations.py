"""The CLOSED set of operations a workflow stage may name (ALIVE-PI-02A).

Each entry points at EXISTING ALIVE functionality (`binding`, a `module:attribute` reference that a
test imports to prove it is real) or says plainly that no such operation exists yet. A workflow
cannot add to this set: there is no registration path from a definition, an API or a plugin.
Nothing here is called in PI-02A; `binding` is metadata for PI-02B's executor.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal


@dataclass(frozen=True)
class Operation:
    id: str
    kind: Literal["deterministic", "pi_agent", "validation", "approval_gate"]
    summary: str
    side_effects: Literal["none", "read", "write"]
    binding: str | None  # "module:Attribute.path" of the existing implementation, if any
    unavailable_reason: str | None = None

    @property
    def available(self):
        return self.binding is not None


_OPERATIONS = (
    Operation(
        "result.record",
        "deterministic",
        "Retain a validated workflow result as an owner-internal CognitiveMessage; "
        "never independent evidence or learning feedback.",
        "write",
        "alive.workflows.adapters:record",
    ),
    Operation(
        "context.prepare",
        "deterministic",
        "Assemble the bounded world state an investigation reasons over.",
        "read",
        "alive.cognition:Cognition.world_state",
    ),
    Operation(
        "memory.retrieve",
        "deterministic",
        "Retrieve stored memories matching a query.",
        "read",
        "alive.memory:MemoryService.retrieve",
    ),
    Operation(
        "cognition.role",
        "pi_agent",
        "One structured model call through the audited ModelGateway seam (PI-02B routes it "
        "through the approved Pi transport).",
        "none",
        "alive.model_gateway:gateway_for",
    ),
    Operation(
        "evidence.validate_references",
        "validation",
        "Check that every claim in a role output cites evidence that was actually supplied.",
        "none",
        "alive.society:validate_references",
    ),
    Operation(
        "evidence.evaluate",
        "validation",
        "Compare observed and proposed content against its sources.",
        "none",
        "alive.society:evaluate",
    ),
    Operation(
        "evidence.qualify",
        "validation",
        "Qualify a source as evidence for a claim.",
        "read",
        "alive.evidence_qualification:EvidenceQualifier.qualify",
    ),
    Operation(
        "evidence.record",
        "deterministic",
        "Persist an accepted result and its provenance as evidence.",
        "write",
        None,
        "No standalone evidence-recording operation exists: Cognition.finish() settles an "
        "Investigation and cannot be called on its own.",
    ),
    Operation(
        "approval.request",
        "approval_gate",
        "Block a run until the owner approves or refuses.",
        "none",
        None,
        "Approvals are experiment-specific (ExperimentApprovals); there is no general gate yet.",
    ),
)

OPERATIONS = MappingProxyType({operation.id: operation for operation in _OPERATIONS})


def public_view(operation):
    return {
        "id": operation.id,
        "kind": operation.kind,
        "summary": operation.summary,
        "side_effects": operation.side_effects,
        "available": operation.available,
        "binding": operation.binding,
        "unavailable_reason": operation.unavailable_reason,
    }
