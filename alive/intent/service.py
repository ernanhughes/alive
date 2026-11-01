"""Compose and retain a recommendation from a completed interpretation. No model is called here."""

from sqlalchemy import select

from alive.admission.profiles import INTENT
from alive.admission.service import profile_of, row_for
from alive.bespoke.recipes import load_catalogue
from alive.cognitive_models import CognitiveMessage, ModelInvocation
from alive.intent.context import catalogue_sha256, project_catalogue
from alive.intent.contracts import ROLE
from alive.intent.models import IntentRecommendation
from alive.intent.recommend import assemble, eligibility
from alive.workflows.context import aware, digest, require
from alive.workflows.models import WorkflowRun, WorkflowStageRun
from alive.workflows.runner import result_event


def view(row):
    require(digest(row.record) == row.record_sha256, "recommendation_integrity")
    return {
        "id": row.id,
        "admission_id": row.admission_id,
        "created_at": aware(row.created_at).isoformat(),
        "record_sha256": row.record_sha256,
        "record": row.record,
    }


async def stored(session, kernel, admission_id):
    row = await session.scalar(
        select(IntentRecommendation).where(
            IntentRecommendation.admission_id == admission_id,
            IntentRecommendation.instance_id == kernel.instance_id,
        )
    )
    return row


async def get(kernel, admission_id):
    async with kernel.db.sessions() as session:
        await row_for(session, kernel, admission_id)  # instance scope and review integrity
        row = await stored(session, kernel, admission_id)
        require(row is not None, "recommendation_unavailable")
        return view(row)


async def compose(kernel, admission_id):
    """Idempotent. Reads the retained interpretation and re-asks the deterministic selector."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await row_for(session, kernel, admission_id, lock=True)
        require(
            profile_of(admission.terms).id == INTENT and admission.run_id, "not_an_interpretation"
        )
        existing = await stored(session, kernel, admission_id)
        if existing is not None:
            return view(existing)
        run = await session.get(WorkflowRun, admission.run_id)
        require(run is not None and run.status == "COMPLETED", "interpretation_not_completed")
        stages = {
            s.stage_id: s
            for s in (
                await session.scalars(
                    select(WorkflowStageRun).where(WorkflowStageRun.run_id == run.id)
                )
            ).all()
        }
        output = await result_event(session, stages["record"])
        message = await session.get(CognitiveMessage, stages["record"].id)
        require(
            message is not None
            and message.investigation_id == run.investigation_id
            and digest(message.content) == output["sha256"],
            "interpretation_integrity",
        )
        result = message.content["result"]
        terms = admission.terms
        goal = terms["objective"]["requested_outcome"]
        require(
            result["original_goal"] == goal
            and result["catalogue_sha256"] == terms["model_disclosure"]["catalogue_sha256"],
            "interpretation_scope",
        )
        recipes = getattr(kernel, "bespoke_recipes", None) or load_catalogue()
        rows = project_catalogue(recipes)
        # Proposals are resolved only against the catalogue the model actually saw.
        require(catalogue_sha256(rows) == result["catalogue_sha256"], "catalogue_changed")
        interpretation = result["interpretation"]
        kind = interpretation["intent_kind"] if result["goal_preserved"] else "unclear"
        paths = [f["path"] for f in terms["model_disclosure"]["files"]]
        resources = terms["source"]["resources"]
        eligible = await eligibility(
            session, kernel, recipes, goal, kind, resources["source_ref"], paths
        )
        call = await session.get(ModelInvocation, stages["interpret"].model_invocation_id)
        record = assemble(
            goal=goal,
            interpretation=interpretation,
            goal_preserved=result["goal_preserved"],
            rows=rows,
            eligible=eligible,
            source={
                "source_ref": resources["source_ref"],
                "content_sha256": resources["content_sha256"],
                "files_listed": len(paths),
                "content_sent": False,
            },
            meta={
                "catalogue_sha256": result["catalogue_sha256"],
                "interpreter": {
                    "role": ROLE,
                    "role_contract_sha256": terms["model_disclosure"]["role_contract_sha256"],
                    "model": call.model,
                    "provider": call.provider,
                    "endpoint": terms["model_disclosure"]["destination"]["endpoint"],
                    "admission_id": admission.id,
                    "review_sha256": admission.review_sha256,
                    "run_id": run.id,
                    "model_invocation_id": call.id,
                    "model_calls": 1,
                    "usage": call.usage,
                    "reserved_tokens": call.reserved_tokens,
                    "latency_ms": call.latency_ms,
                },
            },
        )
        row = IntentRecommendation(
            instance_id=kernel.instance_id,
            admission_id=admission.id,
            record_sha256=digest(record),
            record=record,
        )
        session.add(row)
        await session.flush()
        kernel.add_event(
            session,
            "intent.recommendation.recorded",
            {
                "recommendation_id": row.id,
                "admission_id": admission.id,
                "record_sha256": row.record_sha256,
                "status": record["status"],
            },
            source="intent",
            correlation=admission.id,
        )
        return view(row)
