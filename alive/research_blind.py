"""Blind, provenance-aware owner ratings for the deferred relationship experiment."""

import hashlib
import json
import random
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from alive.models import now, record, uid
from alive.web_models import WebExperience

BLIND_RUN = "research_blind_run"
BLIND_ASSIGNMENT = "research_blind_assignment"
BLIND_OUTPUT = "research_blind_output"
BLIND_RATING = "research_blind_rating"
RUBRIC_VERSION = "alive14-r2-rubric-v1"
CONDITIONS = (
    "A_current_only",
    "B_current_plus_history",
    "C_history_without_synthesis",
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BlindRubric(Strict):
    factually_supported: Literal["yes", "no", "uncertain"]
    relevant_to_goal: Literal["yes", "no", "uncertain"]
    revealed_new: Literal["yes", "no", "uncertain"]
    already_obvious: Literal["yes", "no", "uncertain"]
    would_act: Literal["yes", "no", "uncertain"]
    misleading: Literal["yes", "no", "uncertain"]
    uncertain: Literal["yes", "no"]


class BlindTask(Strict):
    task_id: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=1000)
    current_excerpt: str = Field(min_length=1, max_length=3000)
    historical_excerpt: str = Field(min_length=1, max_length=2000)
    current_url: str = Field(max_length=2048)
    historical_url: str = Field(max_length=2048)
    current_sha256: str = Field(min_length=64, max_length=64)
    historical_sha256: str = Field(min_length=64, max_length=64)
    outputs: dict[str, str]
    attempt_ids: dict[str, str] = Field(default_factory=dict)
    output_metadata: dict[str, dict] = Field(default_factory=dict)


class BlindRunRequest(Strict):
    experiment_id: str = Field(min_length=1, max_length=100)
    seed: int = Field(ge=0, le=1_000_000)
    tasks: list[BlindTask] = Field(min_length=1, max_length=30)


class BlindRatingRequest(Strict):
    output_id: str
    output_sha256: str = Field(min_length=64, max_length=64)
    rubric: BlindRubric


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class ResearchBlind:
    def __init__(self, kernel):
        self.k = kernel

    def add(self, session, kind, data, parent=None, status="recorded"):
        row = WebExperience(
            id=uid(),
            instance_id=self.k.instance_id,
            kind=kind,
            parent_id=parent,
            data=data,
            status=status,
        )
        session.add(row)
        self.k.add_event(session, "research.blind_" + kind, {"id": row.id})
        return row

    async def create_run(self, experiment_id, seed, tasks):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = self.add(
                session,
                BLIND_RUN,
                {
                    "experiment_id": experiment_id,
                    "seed": seed,
                    "rubric_version": RUBRIC_VERSION,
                    "task_count": len(tasks),
                    "conditions": list(CONDITIONS),
                    "created_at": now().isoformat(),
                },
                None,
                "open",
            )
            await session.flush()
            assignment = {}
            output_ids = []
            order = 0
            for task in tasks:
                task_outputs = []
                for condition in CONDITIONS:
                    text = task.outputs.get(condition)
                    if not text:
                        raise ValueError("Every task requires all three conditions")
                    digest = hashlib.sha256(text.encode()).hexdigest()
                    row = self.add(
                        session,
                        BLIND_OUTPUT,
                        {
                            "blind_run_id": run.id,
                            "task_id": task.task_id,
                            "question": task.question,
                            "condition": condition,
                            "output_text": text,
                            "output_sha256": digest,
                            "attempt_id": task.attempt_ids.get(condition),
                            "metadata": task.output_metadata.get(condition, {}),
                            "usage": None,
                            "estimated_usd": None,
                        },
                        run.id,
                        "immutable",
                    )
                    await session.flush()
                    task_outputs.append((row.id, condition, digest))
                    output_ids.append(row.id)
                random.Random(f"{seed}:{task.task_id}").shuffle(task_outputs)
                for output_id, condition, digest in task_outputs:
                    assignment[output_id] = {
                        "task_id": task.task_id,
                        "condition": condition,
                        "output_sha256": digest,
                        "display_order": order,
                    }
                    output = await session.get(WebExperience, output_id)
                    output.data = output.data | {"display_order": order}
                    order += 1
            assignment_row = self.add(
                session,
                BLIND_ASSIGNMENT,
                {
                    "blind_run_id": run.id,
                    "seed": seed,
                    "rubric_version": RUBRIC_VERSION,
                    "assignment": assignment,
                    "created_at": now().isoformat(),
                },
                run.id,
                "protected",
            )
            run.data = run.data | {
                "output_ids": output_ids,
                "assignment_id": assignment_row.id,
            }
            await session.flush()
            return record(run)

    async def rating_view(self, run_id):
        async with self.k.db.sessions() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            outputs = [
                row
                for row in await self.rows(session, BLIND_OUTPUT)
                if row.data.get("blind_run_id") == run_id
            ]
            outputs.sort(key=lambda row: row.data.get("display_order", 0))
            return {
                "blind_run_id": run.id,
                "status": run.status,
                "rubric_version": run.data["rubric_version"],
                "task_count": run.data["task_count"],
                "outputs": [
                    {
                        "output_id": row.id,
                        "task_id": row.data["task_id"],
                        "question": row.data["question"],
                        "display_order": row.data.get("display_order", 0),
                        "output_text": row.data["output_text"],
                        "output_sha256": row.data["output_sha256"],
                    }
                    for row in outputs
                ],
                "presentation": (
                    "Equal text-only format. Provider, model, condition, tokens and cost are "
                    "hidden until all ratings are complete."
                ),
            }

    async def rate(self, run_id, output_id, output_sha256, rubric, rater_type="owner"):
        if rater_type not in ("owner", "scripted"):
            raise ValueError("Unknown rater type")
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            if run.status != "open":
                raise ValueError("Blind run is not open for ratings")
            output = await self.web_get(session, output_id, BLIND_OUTPUT)
            if output.data.get("blind_run_id") != run_id:
                raise ValueError("Output does not belong to this blind run")
            if output.data["output_sha256"] != output_sha256:
                raise PermissionError("The displayed output changed; refresh before rating")
            prior = [
                row
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id
                and row.data.get("output_id") == output_id
                and row.data.get("rater_type") == rater_type
            ]
            revision = len(prior) + 1
            row = self.add(
                session,
                BLIND_RATING,
                {
                    "blind_run_id": run_id,
                    "task_id": output.data["task_id"],
                    "output_id": output_id,
                    "output_sha256": output_sha256,
                    "rater_type": rater_type,
                    "rating_id": uid(),
                    "rubric": rubric.model_dump() if hasattr(rubric, "model_dump") else rubric,
                    "rubric_version": RUBRIC_VERSION,
                    "revision": revision,
                    "rated_at": now().isoformat(),
                },
                output_id,
                "recorded",
            )
            await session.flush()
            return record(row)

    async def reveal(self, run_id):
        async with self.k.db.sessions() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            assignment_row = await self.web_get(
                session, run.data["assignment_id"], BLIND_ASSIGNMENT
            )
            outputs = {
                row.id: row
                for row in await self.rows(session, BLIND_OUTPUT)
                if row.data.get("blind_run_id") == run_id
            }
            ratings = [
                row
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id and row.data.get("rater_type") == "owner"
            ]
            rated = {row.data["output_id"] for row in ratings}
            if set(outputs) - rated:
                raise ValueError("All outputs must be owner-rated before unblinding")
            return {
                "blind_run_id": run_id,
                "experiment_id": run.data["experiment_id"],
                "seed": run.data["seed"],
                "rubric_version": run.data["rubric_version"],
                "outputs": [
                    {
                        "output_id": output_id,
                        "task_id": output.data["task_id"],
                        "condition": assignment_row.data["assignment"][output_id]["condition"],
                        "display_order": output.data.get("display_order"),
                        "output_text": output.data["output_text"],
                        "output_sha256": output.data["output_sha256"],
                        "attempt_id": output.data.get("attempt_id"),
                        "metadata": output.data.get("metadata"),
                    }
                    for output_id, output in outputs.items()
                ],
                "ratings": [record(row) for row in ratings],
                "scripted_ratings": [
                    record(row)
                    for row in await self.rows(session, BLIND_RATING)
                    if row.data.get("blind_run_id") == run_id
                    and row.data.get("rater_type") == "scripted"
                ],
            }

    async def web_get(self, session, row_id, kind):
        row = await session.get(WebExperience, row_id)
        if not row or row.instance_id != self.k.instance_id or row.kind != kind:
            raise KeyError("Unknown " + kind)
        return row

    async def rows(self, session, kind):
        from sqlalchemy import select

        return (
            await session.scalars(
                select(WebExperience).where(
                    WebExperience.instance_id == self.k.instance_id,
                    WebExperience.kind == kind,
                )
            )
        ).all()
