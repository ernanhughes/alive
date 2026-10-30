"""Caller-owned trusted boundaries. Protocol conformance is not authentication."""

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import Field

from .contracts import (
    ID,
    Context,
    Contract,
    Digest,
    Evidence,
    InvocationSummary,
    Observation,
    OutcomeFeedback,
)

if TYPE_CHECKING:
    from alive.model_gateway import StructuredRequest


class EvidencePort(Protocol):
    async def admit(self, observation: Observation, context: Context) -> tuple[Evidence, ...]:
        """Return exact authorized evidence; caller enforces scope, identity and safe payload."""
        ...


class FeedbackVerifier(Protocol):
    def verify(self, feedback: OutcomeFeedback) -> bool:
        """Verify independently observed measurements against trusted external records."""
        ...


class InvocationBinding(Contract):
    """Audit metadata supplied by trusted caller; strings alone confer no authority."""

    summary: InvocationSummary
    payload_hash: Digest
    approved_context: ID


@runtime_checkable
class AuthorizedInvocation(Protocol):
    binding: InvocationBinding

    async def invoke(self, request: "StructuredRequest") -> "InvocationResponse":
        """Enforce reservation, exact request approval, one-use dispatch and settlement.

        This capability is supplied by a trusted integration, never built from model data.
        It owns timeout/cancellation accounting, consent, model choice and provider receipts.
        """
        ...


class InvocationResponse(Contract):
    text: str = Field(min_length=1, max_length=16000)
    summary: InvocationSummary


class CheckpointVerifier(Protocol):
    def qualified(self, checkpoint_hash: str) -> bool:
        """Trusted caller attests checkpoint origin and simulation-only qualification."""
        ...
