"""Blind, provenance-aware owner ratings for the deferred relationship experiment."""

import hashlib
import hmac
import json
import random
import secrets
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from alive.models import now, record, uid
from alive.web_models import WebExperience

BLIND_RUN = "research_blind_run"
BLIND_ASSIGNMENT = "research_blind_assignment"
BLIND_OUTPUT = "research_blind_output"
BLIND_RATING = "research_blind_rating"
RUBRIC_VERSION = "alive14-r3-rubric-v1"
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
    seed: int = Field(ge=0, le=2_147_483_647)
    synthetic: bool = False
    tasks: list[BlindTask] = Field(min_length=1, max_length=30)


class BlindRatingRequest(Strict):
    output_id: str
    output_sha256: str = Field(min_length=64, max_length=64)
    capability: str = Field(min_length=20, max_length=200)
    rubric: BlindRubric
    synthetic: bool = False
    attestation: Literal["none", "human_reviewed"] = "none"


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def verify_commitment(commitment, salt, payload):
    """Recompute an assignment commitment from its published opening."""
    return hmac.compare_digest(_hash({"salt": salt, "payload": payload}), commitment)


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
        # A blind output/assignment ID must not enter the owner-facing event feed before
        # reveal. Only the run-level event is emitted; audit rows remain in the DB.
        if kind == BLIND_RUN:
            self.k.add_event(session, "research.blind_run", {"id": row.id})
        return row

    async def create_run(self, experiment_id, seed, tasks, synthetic=False):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            if any(
                row.data.get("experiment_id") == experiment_id
                for row in await self.rows(session, BLIND_RUN)
            ):
                raise ValueError("Experiment ID already exists")
            capability = secrets.token_urlsafe(32)
            run = self.add(
                session,
                BLIND_RUN,
                {
                    "experiment_id": experiment_id,
                    "seed": seed,
                    "synthetic": bool(synthetic),
                    "rubric_version": RUBRIC_VERSION,
                    "task_count": len(tasks),
                    "conditions": list(CONDITIONS),
                    "created_at": now().isoformat(),
                    "capability_hash": hashlib.sha256(capability.encode()).hexdigest(),
                    "rating_capability": capability,
                    "revealed_at": None,
                },
                None,
                "collecting",
            )
            await session.flush()
            assignment = {}
            assignment_payload = []
            order = 0
            for task in tasks:
                condition_order = list(CONDITIONS)
                random.Random(f"{seed}:{task.task_id}").shuffle(condition_order)
                for condition in condition_order:
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
                            "display_order": order,
                        },
                        run.id,
                        "immutable",
                    )
                    await session.flush()
                    assignment[row.id] = {
                        "task_id": task.task_id,
                        "condition": condition,
                        "output_sha256": digest,
                        "display_order": order,
                    }
                    assignment_payload.append(
                        {
                            "task_id": task.task_id,
                            "condition": condition,
                            "output_sha256": digest,
                        }
                    )
                    order += 1
            commitment_salt = secrets.token_urlsafe(32)
            commitment_payload = {
                "experiment_id": experiment_id,
                "seed": seed,
                "rubric_version": RUBRIC_VERSION,
                "tasks": sorted(
                    assignment_payload,
                    key=lambda item: (item["task_id"], item["condition"]),
                ),
            }
            assignment_commitment = _hash({"salt": commitment_salt, "payload": commitment_payload})
            assignment_row = self.add(
                session,
                BLIND_ASSIGNMENT,
                {
                    "blind_run_id": run.id,
                    "seed": seed,
                    "rubric_version": RUBRIC_VERSION,
                    "assignment": assignment,
                    "commitment_salt": commitment_salt,
                    "commitment_payload": commitment_payload,
                    "assignment_commitment": assignment_commitment,
                    "created_at": now().isoformat(),
                },
                run.id,
                "protected",
            )
            run.data = run.data | {
                "assignment_id": assignment_row.id,
                "assignment_commitment": assignment_commitment,
            }
            await session.flush()
            return record(run) | {
                "rating_capability": capability,
                "assignment_commitment": assignment_commitment,
            }

    async def collecting(self):
        async with self.k.db.sessions() as session:
            return any(row.status == "collecting" for row in await self.rows(session, BLIND_RUN))

    async def list_runs(self):
        async with self.k.db.sessions() as session:
            return {
                "runs": [
                    {
                        "id": row.id,
                        "experiment_id": row.data.get("experiment_id"),
                        "status": row.status,
                        "task_count": row.data.get("task_count"),
                        "rubric_version": row.data.get("rubric_version"),
                    }
                    for row in await self.rows(session, BLIND_RUN)
                ]
            }

    async def rating_view(self, run_id):
        async with self.k.db.sessions() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            outputs = [
                row
                for row in await self.rows(session, BLIND_OUTPUT)
                if row.data.get("blind_run_id") == run_id
            ]
            outputs.sort(key=lambda row: row.data.get("display_order", 0))
            ratings = [
                row
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id and row.data.get("rater_type") == "owner"
            ]
            return {
                "blind_run_id": run.id,
                "status": run.status,
                "rubric_version": run.data["rubric_version"],
                "rating_capability": self._capability(run) if run.status == "collecting" else None,
                "assignment_commitment": run.data.get("assignment_commitment"),
                "task_count": run.data["task_count"],
                "synthetic": bool(run.data.get("synthetic")),
                "rated_output_ids": sorted({row.data["output_id"] for row in ratings}),
                "owner_rating_count": len(ratings),
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

    def _capability(self, run):
        # The raw capability is only returned through the authenticated owner view;
        # for an existing run without one (legacy fixture), use a stable internal value.
        return run.data.get("rating_capability")

    async def rate(
        self,
        run_id,
        output_id,
        output_sha256,
        rubric,
        capability=None,
        rater_type="owner",
        synthetic=False,
        attestation="none",
    ):
        if rater_type not in ("owner", "scripted"):
            raise ValueError("Unknown rater type")
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            if run.status != "collecting":
                raise ValueError("Blind run is not collecting ratings")
            if synthetic and not run.data.get("synthetic"):
                raise PermissionError("Synthetic ratings are not allowed for this run")
            if rater_type == "owner":
                supplied = hashlib.sha256((capability or "").encode()).hexdigest()
                if not hmac.compare_digest(supplied, run.data.get("capability_hash", "")):
                    raise PermissionError("Owner rating capability is invalid")
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
                    "experiment_id": run.data["experiment_id"],
                    "provenance": (
                        "synthetic_owner_endpoint"
                        if rater_type == "owner" and synthetic
                        else "authenticated_owner_interface"
                        if rater_type == "owner"
                        else "scripted_internal_test"
                    ),
                    "synthetic": bool(synthetic),
                    "owner_attestation": attestation,
                    "reveal_status": "hidden",
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
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            if run.status != "collecting":
                raise ValueError("Blind run has already been revealed or closed")
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
            commitment_verified = verify_commitment(
                run.data["assignment_commitment"],
                assignment_row.data["commitment_salt"],
                assignment_row.data["commitment_payload"],
            )
            if not commitment_verified:
                raise ValueError("Assignment commitment opening does not verify")
            run.status = "revealed"
            run.data = run.data | {
                "revealed_at": now().isoformat(),
                "reveal_assignment_commitment": run.data["assignment_commitment"],
                "commitment_verified": True,
            }
            for row in ratings:
                row.data = row.data | {"reveal_status": "revealed"}
            self.k.add_event(
                session,
                "research.blind_revealed",
                {
                    "blind_run_id": run_id,
                    "assignment_commitment": run.data["assignment_commitment"],
                    "commitment_verified": True,
                    "revealed_at": run.data["revealed_at"],
                },
            )
            ordered = sorted(outputs.values(), key=lambda row: row.data.get("display_order", 0))
            payload = self._revealed_payload(
                run, assignment_row, ordered, ratings, commitment_verified
            )
            payload["scripted_ratings"] = [
                record(row)
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id
                and row.data.get("rater_type") == "scripted"
            ]
            return payload

    @staticmethod
    def _revealed_payload(run, assignment_row, outputs, ratings, commitment_verified):
        return {
            "blind_run_id": run.id,
            "experiment_id": run.data["experiment_id"],
            "seed": run.data["seed"],
            "rubric_version": run.data["rubric_version"],
            "status": run.status,
            "assignment_commitment": run.data["assignment_commitment"],
            "commitment_salt": assignment_row.data["commitment_salt"],
            "commitment_payload": assignment_row.data["commitment_payload"],
            "commitment_verified": commitment_verified,
            "revealed_at": run.data["revealed_at"],
            "archived_at": run.data.get("archived_at"),
            "outputs": [
                {
                    "output_id": output.id,
                    "task_id": output.data["task_id"],
                    "condition": assignment_row.data["assignment"][output.id]["condition"],
                    "display_order": output.data.get("display_order"),
                    "output_text": output.data["output_text"],
                    "output_sha256": output.data["output_sha256"],
                    "attempt_id": output.data.get("attempt_id"),
                    "metadata": output.data.get("metadata"),
                }
                for output in outputs
            ],
            "ratings": [record(row) for row in ratings],
            "scripted_ratings": [],
        }

    async def revealed_results(self, run_id):
        """Read-only retrieval of a completed evaluation after reveal."""
        async with self.k.db.sessions() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            if run.status not in ("revealed", "archived"):
                raise ValueError("Blind run has not been revealed")
            assignment_row = await self.web_get(
                session, run.data["assignment_id"], BLIND_ASSIGNMENT
            )
            outputs = sorted(
                [
                    row
                    for row in await self.rows(session, BLIND_OUTPUT)
                    if row.data.get("blind_run_id") == run_id
                ],
                key=lambda row: row.data.get("display_order", 0),
            )
            ratings = [
                row
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id and row.data.get("rater_type") == "owner"
            ]
            scripted = [
                row
                for row in await self.rows(session, BLIND_RATING)
                if row.data.get("blind_run_id") == run_id
                and row.data.get("rater_type") == "scripted"
            ]
            verified = verify_commitment(
                run.data["assignment_commitment"],
                assignment_row.data["commitment_salt"],
                assignment_row.data["commitment_payload"],
            )
            payload = self._revealed_payload(run, assignment_row, outputs, ratings, verified)
            payload["scripted_ratings"] = [record(row) for row in scripted]
            return payload

    async def archive(self, run_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await self.web_get(session, run_id, BLIND_RUN)
            if run.status != "revealed":
                raise ValueError("Only a revealed run can be archived")
            run.status = "archived"
            run.data = run.data | {"archived_at": now().isoformat()}
            return {
                "id": run.id,
                "status": run.status,
                "experiment_id": run.data["experiment_id"],
                "archived_at": run.data["archived_at"],
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
