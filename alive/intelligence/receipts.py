"""Read existing Pi/ModelInvocation receipts; never infer success from a process exit."""

from sqlalchemy import select

from alive.cognitive_models import Investigation, ModelInvocation
from alive.cognitive_schema import RoleOutput
from alive.model_gateway import StructuredRequest
from alive.pi.egress import approved_request_sha256, render_prompt
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runner import sha256_text

from .store import owned, require, workflow


def known_usage(usage):
    if not isinstance(usage, dict):
        return False
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    return (
        all(type(usage.get(key)) is int and usage[key] >= 0 for key in fields)
        and usage["prompt_tokens"] + usage["completion_tokens"] == usage["total_tokens"]
    )


async def resolve(kernel, stage_id, *, goal_id, approved_request_hash):
    """Only for an already qualified upstream invocation. Does not admit or dispatch one."""
    async with kernel.db.sessions() as session:
        stage, run = await workflow(session, kernel.instance_id, stage_id, goal_id)
        require(
            stage.pi_run_id is not None and stage.model_invocation_id is not None,
            "Reasoning receipt unavailable",
        )
        pi = await owned(session, PiRun, stage.pi_run_id, kernel.instance_id)
        call = await session.get(ModelInvocation, stage.model_invocation_id)
        require(call is not None, "Invocation unavailable")
        inquiry = await owned(session, Investigation, call.investigation_id, kernel.instance_id)
        # PI-01B stores an approved summary, not a reconstructible StructuredRequest.
        # Reconstruct the cognition.role request from its authoritative invocation ledger.
        try:
            request = StructuredRequest(
                operation="cognition.role",
                instructions=call.input_json["instructions"],
                data=call.input_json["context"],
                schema=RoleOutput.model_json_schema(),
                model=call.model,
                max_output=pi.approved_request_json["max_output"],
                correlation=call.id,
            )
            RoleOutput.model_validate(call.output_json)
            require(
                pi.approved_request_json
                == {
                    "operation": request.operation,
                    "model": request.model,
                    "max_output": request.max_output,
                    "schema_sha256": sha256_text(repr(sorted(request.schema.items()))),
                    "payload_sha256": sha256_text(render_prompt(request)),
                }
                and approved_request_sha256(request) == approved_request_hash,
                "Approved request/ledger integrity failure",
            )
        except (KeyError, TypeError, ValueError):
            from .store import Refused

            raise Refused("Approved request/ledger integrity failure") from None
        require(
            inquiry.goal_id == goal_id
            and run.investigation_id == inquiry.id
            and pi.reservation_ref == call.id
            and pi.operation == stage.operation == "cognition.role"
            and pi.approved_request_sha256 == approved_request_hash
            and pi.state == "SETTLED"
            and call.status == "validated"
            and stage.state == "COMPLETED"
            and stage.validation_status == "passed"
            and stage.uncertainty == "none",
            "Unsettled or incompatible reasoning receipt",
        )
        require(
            all(
                pi.result_json.get(key) is True
                for key in ("cleanup_confirmed", "pi_settled", "matches_egress_record")
            ),
            "Pi lifecycle/output consistency not verified",
        )
        requests = (
            await session.scalars(
                select(PiProviderRequest).where(PiProviderRequest.run_id == pi.id)
            )
        ).all()
        require(
            len(requests) == 1
            and requests[0].state == "settled"
            and known_usage(requests[0].usage_json)
            and all(call.usage.get(key) == value for key, value in requests[0].usage_json.items())
            and type(call.usage.get("charged_tokens")) is int
            and call.usage["charged_tokens"] == requests[0].usage_json["total_tokens"]
            and call.usage["charged_tokens"] <= call.reserved_tokens
            and requests[0].approved_request_sha256 == approved_request_hash
            and requests[0].response_sha256 is not None
            and requests[0].response_sha256 == pi.result_json.get("text_sha256"),
            "Ambiguous or unknown provider outcome",
        )
        return {
            "pi_run_id": pi.id,
            "model_invocation_id": call.id,
            "operation": pi.operation,
            "approved_request_sha256": approved_request_hash,
            "model_requested": requests[0].model_requested,
            "model_observed": requests[0].model_observed,
            "usage": requests[0].usage_json,
            "settlement": pi.state,
            "output_linkage": "upstream receipt hash; parsed ledger output separately validated",
        }
