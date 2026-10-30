"""Structured role-output validation through a caller-owned invocation capability."""

import math

from alive.cognitive_schema import RoleOutput
from alive.society import role_prompt

from .contracts import Claim, Context, Observation, ReasoningResult, digest
from .ports import AuthorizedInvocation, InvocationBinding, InvocationResponse


def payload(observation: Observation, context: Context):
    return {
        "observation": observation.model_dump(mode="json"),
        "context": context.model_dump(mode="json"),
    }


class Unavailable(ValueError):
    """Missing trusted capability or approved binding."""


class ModelReasoner:
    async def reason(
        self,
        observation: Observation,
        context: Context,
        capability: AuthorizedInvocation | None,
    ) -> ReasoningResult:
        if not isinstance(capability, AuthorizedInvocation):
            raise Unavailable("Authorized invocation unavailable")
        binding = InvocationBinding.model_validate(capability.binding)
        data = payload(observation, context)
        if binding.payload_hash != digest(data) or binding.approved_context != context.scope:
            raise Unavailable("Invocation is not bound to this payload and scope")
        if binding.summary.provenance == "fixture" and context.origin != "fixture":
            raise ValueError("Fixture invocation cannot interpret live or simulator context")
        # Lazy shape reuse only. Never instantiate a gateway or provider here.
        from alive.model_gateway import StructuredRequest

        request = StructuredRequest(
            operation=binding.summary.operation,
            instructions=role_prompt("observer"),
            data=data,
            schema=RoleOutput.model_json_schema(),
            model=binding.summary.model,
            max_output=1536,
            correlation=binding.summary.reservation_id,
        )
        try:
            output = await capability.invoke(request)
        except Unavailable as error:
            # Once a trusted adapter is entered, it owns whether a dispatch occurred.
            raise RuntimeError("Invocation adapter failed") from error
        output = InvocationResponse.model_validate(output)
        before, after = binding.summary, output.summary
        for key in (
            "invocation_id",
            "reservation_id",
            "operation",
            "provider",
            "model",
            "provenance",
        ):
            if getattr(before, key) != getattr(after, key):
                raise ValueError("Invocation identity mismatch")
        role = RoleOutput.model_validate_json(output.text)
        if not math.isfinite(role.confidence):
            raise ValueError("Nonfinite model confidence")
        if after.provenance == "fixture" and (
            after.prompt_tokens or after.completion_tokens or context.origin != "fixture"
        ):
            raise ValueError("Fixture provenance/usage mismatch")
        refs = {e.id for e in context.evidence}
        claims = []
        for claim in role.claims:
            if not claim.evidence_refs or not set(claim.evidence_refs) <= refs:
                raise ValueError("Unknown or absent citation")
            claims.append(
                Claim(
                    subject=claim.subject,
                    predicate=claim.predicate,
                    value=claim.value,
                    citations=tuple(claim.evidence_refs),
                )
            )
        # RoleOutput actions remain advisory and never become policy candidates.
        return ReasoningResult(
            invocation=after,
            summary=role.summary,
            claims=tuple(claims),
            limitations=tuple(role.uncertainties + role.criticisms),
            recommendation=role.recommendation,
        )
