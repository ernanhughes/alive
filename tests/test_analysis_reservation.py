"""Exercise reservation authority alone, with a successful control before every attack."""

from datetime import timedelta
from types import SimpleNamespace as NS

import pytest

from alive.admission.models import Admission
from alive.analysis.contracts import ROLE, AnalysisSpec
from alive.models import now
from alive.workflows import context
from alive.workflows.models import WorkflowExecution, WorkflowRun, WorkflowStageRun


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["outbound", "model", "role_contract"])
async def test_reservation_guard_independently_refuses_changed_authority(field, monkeypatch):
    analysis = AnalysisSpec(inputs={"source": "bounded"}, context_for=lambda inputs: inputs)
    stage = NS(
        id="stage",
        stage_id="analyze",
        run_id="run",
        state="RUNNING",
        operation="repository.analyze",
        model_invocation_id=None,
        input_sha256=context.digest(analysis.inputs),
    )
    rows = {
        Admission: NS(
            id="admission",
            instance_id="instance",
            terms={
                "model_disclosure": {
                    "destination": {"endpoint": "https://approved.example/completions"}
                }
            },
        ),
        WorkflowExecution: NS(
            owner="owner",
            cancel_requested=False,
            authorization_id="grant",
            authorization_sha256="hash",
            deadline=now() + timedelta(seconds=60),
        ),
        WorkflowRun: NS(
            id="run", instance_id="instance", status="RUNNING", investigation_id="inquiry"
        ),
        WorkflowStageRun: stage,
    }
    from alive.capabilities.bindings import digest as admission_digest

    rows[Admission].review_sha256 = admission_digest(rows[Admission].terms)

    class Session:
        async def get(self, kind, ident):
            return rows[kind]

    grant = NS(
        admission_ref="admission",
        outbound_approved=True,
        models={ROLE: "approved"},
        role_contracts={ROLE: analysis.contract},
        max_output_tokens=100,
        operations=[stage.operation],
        capabilities={
            "analyze": {
                "identity": {
                    "id": stage.operation,
                    "implementation_id": analysis.implementation_id,
                },
                "limits": {"max_model_calls": 1, "max_output_tokens": 100},
            }
        },
    )
    spec = NS(stages=[NS(id="analyze", limits=NS(max_output_tokens=100))])

    async def authorized(*args):
        return grant, spec, None, NS(id="inquiry"), None, None

    monkeypatch.setattr(context, "authorized", authorized)
    kernel = NS(instance_id="instance", settings=NS(alive_model_transport="pi"))

    async def reserve():
        return await context.model_claim(
            Session(),
            kernel,
            ("run", "stage", "owner"),
            ROLE,
            analysis.inputs,
            "approved",
            100,
            analysis=analysis,
        )

    claimed, destination = await reserve()
    assert claimed is stage
    assert destination.endpoint == "https://approved.example/completions"
    if field == "outbound":
        grant.outbound_approved = False
    elif field == "model":
        grant.models[ROLE] = "unapproved"
    else:
        grant.role_contracts[ROLE] = "0" * 64
    with pytest.raises(context.Refused, match="exact_model_authority_required"):
        await reserve()
