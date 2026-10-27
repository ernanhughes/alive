"""Persistent single-owner cognition. The Governor, never a model, owns every transition."""

import asyncio
import contextlib
import hashlib
import json
import time
from datetime import UTC
from urllib.parse import urlsplit

from sqlalchemy import func, select

from alive.attention import attention, claims_from_text, fingerprint, rank, redact
from alive.cognitive_models import (
    ActionProposal,
    CognitiveControl,
    CognitiveMessage,
    CognitiveObservation,
    Experience,
    Investigation,
    Laboratory,
    ModelInvocation,
)
from alive.cognitive_schema import (
    TERMINAL,
    TRANSITIONS,
    CognitiveConfiguration,
    CognitiveEnvelope,
    ExperienceRecord,
    RoleOutput,
)
from alive.models import Event, Goal, Memory, now, record, uid
from alive.providers import MetaProvider, ProviderError
from alive.society import ROLE_SPEC_VERSION, evaluate, mock_role, role_prompt, validate_references


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class BudgetExhausted(RuntimeError):
    pass


class Cognition:
    def __init__(self, kernel, memory):
        self.k, self.memory = kernel, memory
        self.task = None
        self.worker = None
        self.mode = "stopped"
        self.command_lock = asyncio.Lock()

    async def initialize(self):
        k = self.k
        async with k.lock, k.db.sessions.begin() as session:
            control = await session.get(CognitiveControl, k.instance_id)
            if not control:
                control = CognitiveControl(
                    instance_id=k.instance_id,
                    cursor=await session.scalar(select(func.max(Event.sequence_number))) or 0,
                    configuration=CognitiveConfiguration(use_critic=False).model_dump(),
                    provider=k.settings.alive_cognitive_provider,
                )
                session.add(control)
                await session.flush()
            # Never resume a previously authorized side effect after a crash without review.
            if control.mode == "running":
                control.mode = "paused"
            self.mode = control.mode
            for row in (
                await session.scalars(
                    select(Investigation).where(
                        ~Investigation.state.in_(TERMINAL),
                        Investigation.state != "AWAITING_APPROVAL",
                    )
                )
            ).all():
                row.error = "Interrupted by backend restart; inference is not replayed"
                goal = await session.get(Goal, row.goal_id)
                if goal and goal.status == "active":
                    goal.status = "proposed"
                self._transition(session, row, "CANCELLED")
                self._experience(
                    session, row, control, {"effect": "none", "reason": "restart"}, truncated=True
                )
            for call in (
                await session.scalars(
                    select(ModelInvocation).where(ModelInvocation.status == "reserved")
                )
            ).all():
                call.status, call.error = (
                    "interrupted",
                    "Unknown provider completion; charged reserved tokens",
                )
        k.cognition_enabled = self.mode == "running"
        self.task = asyncio.create_task(self.loop())
        self.task.add_done_callback(k.background_completed)

    async def command(self, data):
        async with self.command_lock:
            k = self.k
            if data.command == "start" and data.provider == "meta":
                provider = MetaProvider(k.settings)
                catalog = await provider.discover()
                required = {k.settings.alive_meta_model, *k.settings.alive_role_models.values()}
                if catalog["status"] != "available" or not required.issubset(
                    set(catalog["models"])
                ):
                    raise ValueError(
                        "Meta model access is not confirmed; probe provider configuration"
                    )
            if data.command != "start":
                self.mode = "paused" if data.command == "pause" else "stopped"
                k.cognition_enabled = False
                if self.worker and not self.worker.done():
                    self.worker.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await self.worker
            async with k.lock, k.db.sessions.begin() as session:
                control = await session.get(CognitiveControl, k.instance_id)
                if data.command == "new_session":
                    control.session_id = uid()
                    control.spent = {
                        key: value
                        for key, value in control.spent.items()
                        if key.startswith("experiment_")
                    }
                elif data.command == "start":
                    control.provider = data.provider
                    self.mode = "running"
                    control.cursor = (
                        await session.scalar(select(func.max(Event.sequence_number))) or 0
                    )
                control.mode = self.mode
                control.updated_at = now()
                if self.mode != "running":
                    for observation in (
                        await session.scalars(
                            select(CognitiveObservation).where(
                                CognitiveObservation.status == "TRIAGED"
                            )
                        )
                    ).all():
                        observation.status = "CANCELLED"
                    for row in (
                        await session.scalars(
                            select(Investigation).where(~Investigation.state.in_(TERMINAL))
                        )
                    ).all():
                        self._transition(session, row, "CANCELLED")
                        goal = await session.get(Goal, row.goal_id)
                        if goal and goal.status == "active":
                            goal.status = "proposed"
                        self._experience(
                            session,
                            row,
                            control,
                            {"effect": "none", "reason": data.command},
                            truncated=True,
                        )
                        action = await session.scalar(
                            select(ActionProposal).where(ActionProposal.investigation_id == row.id)
                        )
                        if action and action.status != "executed":
                            action.status = "cancelled"
                k.add_event(
                    session,
                    "cognition." + data.command,
                    {"provider": control.provider, "session_id": control.session_id},
                )
            k.cognition_enabled = self.mode == "running"
            if self.mode == "running":
                await k.set_running(True)
            return await self.status()

    async def configure(self, configuration):
        async with self.command_lock, self.k.lock, self.k.db.sessions.begin() as session:
            if self.mode == "running":
                raise ValueError("Pause autonomy before changing its budgets or permissions")
            control = await session.get(CognitiveControl, self.k.instance_id)
            for origin in configuration.origins:
                if origin not in self.k.settings.alive_browser_origins:
                    raise ValueError("Cognitive origins must also be authorised browser origins")
            control.configuration = configuration.model_dump()
            self.k.add_event(session, "cognition.configuration_changed", {"policy": "attention-v1"})
        return await self.status()

    async def status(self):
        async with self.k.db.sessions() as session:
            control = await session.get(CognitiveControl, self.k.instance_id)
            active = await session.scalar(
                select(Investigation)
                .where(~Investigation.state.in_(TERMINAL))
                .order_by(Investigation.created_at)
            )
            latest = await session.scalar(
                select(CognitiveObservation).order_by(CognitiveObservation.created_at.desc())
            )
            active_role = await session.scalar(
                select(ModelInvocation.role)
                .where(ModelInvocation.status == "reserved")
                .order_by(ModelInvocation.created_at.desc())
                .limit(1)
            )
            objective = await session.get(Goal, active.goal_id) if active else None
            recent_message = await session.scalar(
                select(CognitiveMessage)
                .where(CognitiveMessage.sender.in_(["observer", "proposer", "critic"]))
                .order_by(CognitiveMessage.created_at.desc())
                .limit(1)
            )
            return {
                "control": record(control),
                "active": record(active) if active else None,
                "active_objective": objective.title if objective else None,
                "current_uncertainty": recent_message.content.get("uncertainties", [])
                if recent_message
                else [],
                "active_role": active_role,
                "latest_observation": record(latest) if latest else None,
                "roles": [
                    {
                        "role": role,
                        "version": ROLE_SPEC_VERSION,
                        "model": self.k.settings.alive_role_models.get(
                            role, self.k.settings.alive_meta_model
                        ),
                        "tools": [],
                    }
                    for role in ["observer", "proposer", "critic"]
                ]
                + [
                    {
                        "role": "investigator",
                        "version": 1,
                        "tools": ["authorised_memory", "controlled_sources"],
                    },
                    {"role": "evaluator", "version": 1, "deterministic": True},
                    {"role": "governor", "version": 1, "deterministic": True},
                ],
                "embedding": {
                    "available": self.memory.embedding.available,
                    "model": self.memory.embedding.model_id,
                    "revision": self.memory.embedding.revision,
                },
            }

    async def loop(self):
        while True:
            if self.mode == "running":
                async with self.command_lock:
                    await self.perceive()
                    if not self.worker or self.worker.done():
                        run_id = await self.auction()
                        if run_id:
                            self.worker = asyncio.create_task(self.execute(run_id))
                if self.worker and self.worker.done():
                    with contextlib.suppress(asyncio.CancelledError):
                        self.worker.result()
            await asyncio.sleep(0.3)

    async def perceive(self):
        k = self.k
        async with k.lock, k.db.sessions.begin() as session:
            control = await session.get(CognitiveControl, k.instance_id)
            config = CognitiveConfiguration.model_validate(control.configuration)
            events = (
                await session.scalars(
                    select(Event)
                    .where(Event.sequence_number > control.cursor)
                    .order_by(Event.sequence_number)
                    .limit(100)
                )
            ).all()
            pending = await session.scalar(
                select(func.count())
                .select_from(CognitiveObservation)
                .where(CognitiveObservation.status == "TRIAGED")
            )
            goals = (
                await session.scalars(
                    select(Goal)
                    .where(Goal.status.in_(["accepted", "active"]))
                    .order_by(Goal.created_at)
                    .limit(20)
                )
            ).all()
            topics = config.topics + [goal.title for goal in goals]
            for event in events:
                control.cursor = event.sequence_number
                if event.event_type not in (
                    "browser.page_opened",
                    "browser.dom_changed",
                    "goal.selected",
                    "agent.run_completed",
                    "alive.state_unexpected",
                ):
                    continue
                if event.event_type == "goal.selected":
                    goal = await session.get(Goal, event.payload.get("goal_id"))
                    if not goal:
                        continue
                    content = goal.title + " " + goal.description
                    url = "internal:commitment"
                    source_type = "commitment"
                elif event.event_type.startswith("browser."):
                    content = redact(event.payload.get("text", ""))
                    url = str(event.payload.get("url", "")).split("?")[0].split("#")[0]
                    parsed = urlsplit(url)
                    if f"{parsed.scheme}://{parsed.netloc}" not in config.origins:
                        continue
                    source_type = "extension" if event.source == "extension" else "managed_browser"
                else:
                    # Internal outcomes need useful content to compete for attention.
                    content = redact(event.payload.get("summary", ""))
                    url = "internal:outcome"
                    source_type = "internal"
                if not content.strip():
                    continue
                # A read-only preview/draft change must not recursively trigger its own analysis.
                claims = claims_from_text(content)
                meaningful = " ".join(
                    f"Claim: {c['subject']} | {c['predicate']} | {c['value']};" for c in claims
                )
                canonical = meaningful or content
                key = fingerprint(k.instance_id, url, canonical)
                if await session.scalar(
                    select(CognitiveObservation.id).where(CognitiveObservation.fingerprint == key)
                ):
                    continue
                previous = await session.scalar(
                    select(CognitiveObservation)
                    .order_by(CognitiveObservation.created_at.desc())
                    .limit(1)
                )
                age = (
                    (now() - aware(goal.created_at)).total_seconds()
                    if source_type == "commitment"
                    else 0
                )
                bid = attention(
                    canonical,
                    topics,
                    previous.content if previous else None,
                    accepted=source_type == "commitment",
                    age_seconds=age,
                )
                status = (
                    "TRIAGED"
                    if bid["score"] >= config.threshold and bid["relevance"] > 0
                    else "IGNORED"
                )
                if pending >= 128:
                    status = "BACKPRESSURE"
                row = CognitiveObservation(
                    id=uid(),
                    instance_id=k.instance_id,
                    source_event_id=event.id,
                    fingerprint=key,
                    content=canonical,
                    provenance={
                        "source_type": source_type,
                        "commitment_id": goal.id if source_type == "commitment" else None,
                        "url": url,
                        "source_event_ids": [event.id],
                        "classification": "authorised_observation",
                        "claims": claims,
                        "permission": "explicit API/sensor grant",
                        "timestamp": event.occurred_at.isoformat(),
                    },
                    attention=bid,
                    status=status,
                )
                session.add(row)
                pending += status == "TRIAGED"
                k.add_event(
                    session,
                    "cognition.attention_bid",
                    {
                        "observation_id": row.id,
                        "attention": bid,
                        "decision": "CANDIDATE" if status == "TRIAGED" else "NO ACTION WARRANTED",
                        "reason": status,
                    },
                    correlation=event.correlation_id,
                    cause=event.id,
                )

    async def auction(self):
        k = self.k
        async with k.lock, k.db.sessions.begin() as session:
            if await session.scalar(
                select(Investigation.id).where(~Investigation.state.in_(TERMINAL)).limit(1)
            ):
                return None
            control = await session.get(CognitiveControl, k.instance_id)
            config = CognitiveConfiguration.model_validate(control.configuration)
            candidates = (
                await session.scalars(
                    select(CognitiveObservation)
                    .where(CognitiveObservation.status == "TRIAGED")
                    .limit(128)
                )
            ).all()
            candidates = rank([record(row) for row in candidates], now())
            for candidate in candidates:
                observation = await session.get(CognitiveObservation, candidate["id"])
                commitment = observation.provenance.get("commitment_id")
                if commitment:
                    accepted_goal = await session.get(Goal, commitment)
                    if not accepted_goal or accepted_goal.status not in ("accepted", "active"):
                        observation.status = "CANCELLED"
                        k.add_event(
                            session,
                            "cognition.bid_rejected",
                            {
                                "observation_id": observation.id,
                                "reason": "commitment_no_longer_accepted",
                            },
                        )
                        continue
                if not commitment and (now() - aware(observation.created_at)).total_seconds() > 300:
                    observation.status = "EXPIRED"
                    k.add_event(
                        session,
                        "cognition.bid_rejected",
                        {"observation_id": observation.id, "reason": "expired"},
                    )
                    continue
                reserve = {
                    "calls": config.investigation_calls,
                    "tokens": config.investigation_tokens,
                    "tools": config.tool_calls,
                }
                enough = all(
                    control.spent.get(prefix + unit, 0)
                    + control.reserved.get(unit, 0)
                    + reserve[unit]
                    <= limit
                    for prefix, limits in [
                        (
                            "session_",
                            {"calls": config.session_calls, "tokens": config.session_tokens},
                        ),
                        (
                            "experiment_",
                            {"calls": config.experiment_calls, "tokens": config.experiment_tokens},
                        ),
                    ]
                    for unit, limit in limits.items()
                )
                if not enough:
                    observation.status = "BUDGET_REJECTED"
                    k.add_event(
                        session,
                        "cognition.bid_rejected",
                        {"observation_id": observation.id, "reason": "hard_budget_limit"},
                    )
                    continue
                goal = Goal(
                    id=uid(),
                    instance_id=k.instance_id,
                    title="Investigate: " + observation.content[:160],
                    description=json.dumps(
                        {
                            "trigger": observation.source_event_id,
                            "rationale": observation.attention,
                            "success_criteria": "Compare claims with independent evidence; "
                            "retain uncertainty",
                            "expected_outcome": "Evidence comparison",
                            "estimated_cost": reserve,
                            "requested_tools": ["authorised_memory", "controlled_sources"],
                            "permission": "internal_analysis",
                            "expires_seconds": 300,
                        }
                    ),
                    origin="cognitive_society",
                    status="active",
                )
                session.add(goal)
                await session.flush()
                run = Investigation(
                    id=uid(),
                    instance_id=k.instance_id,
                    observation_id=observation.id,
                    goal_id=goal.id,
                    state="SCHEDULED",
                    snapshot={},
                    budget=reserve,
                    usage={"calls": 0, "tokens": 0, "tools": 0, "latency_ms": 0},
                    history=[
                        {"state": "OBSERVED", "at": observation.created_at.isoformat()},
                        {"state": "TRIAGED", "at": now().isoformat()},
                        {"state": "GOAL_PROPOSED", "at": now().isoformat()},
                        {"state": "SCHEDULED", "at": now().isoformat()},
                    ],
                )
                session.add(run)
                observation.status = "SELECTED"
                control.reserved = {
                    unit: control.reserved.get(unit, 0) + value for unit, value in reserve.items()
                }
                k.add_event(
                    session,
                    "goal.proposed",
                    {
                        "goal_id": goal.id,
                        "investigation_id": run.id,
                        "permission": "internal cognitive analysis; no external action",
                    },
                )
                k.add_event(
                    session,
                    "cognition.auction_selected",
                    {
                        "investigation_id": run.id,
                        "selected": observation.id,
                        "considered": [c["id"] for c in candidates],
                        "score": observation.attention["score"],
                        "reserved": reserve,
                    },
                    correlation=run.id,
                )
                return run.id
        return None

    def _transition(self, session, row, target):
        if row.state == target:
            return
        if target not in TRANSITIONS.get(row.state, set()):
            raise ValueError(f"Invalid cognitive transition {row.state} → {target}")
        row.state = target
        row.updated_at = now()
        row.history = row.history + [{"state": target, "at": now().isoformat()}]
        self.k.add_event(
            session,
            "cognition.transition",
            {"investigation_id": row.id, "state": target},
            correlation=row.id,
        )

    async def transition(self, run_id, target):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(Investigation, run_id)
            self._transition(session, row, target)

    async def message(self, run_id, sender, kind, content, invocation=None):
        validated = CognitiveEnvelope(
            message_id=uid(),
            investigation_id=run_id,
            sender=sender,
            message_type=kind,
            content=content,
            model_invocation_id=invocation,
            timestamp=now(),
        )
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = CognitiveMessage(
                id=validated.message_id,
                investigation_id=run_id,
                sender=sender,
                recipient="governor",
                message_type=kind,
                content=content,
                invocation_id=invocation,
            )
            session.add(row)
            self.k.add_event(
                session,
                "cognition.message",
                {
                    "message_id": row.id,
                    "investigation_id": run_id,
                    "sender": sender,
                    "message_type": kind,
                    "deterministic": invocation is None,
                },
                correlation=run_id,
            )

    async def world_state(self, run_id):
        k = self.k
        async with k.db.sessions() as session:
            run = await session.get(Investigation, run_id)
            observation = await session.get(CognitiveObservation, run.observation_id)
            goals = (
                await session.scalars(
                    select(Goal).where(Goal.status.in_(["active", "accepted"])).limit(10)
                )
            ).all()
            path = urlsplit(observation.provenance["url"]).path
            env_id = path.removeprefix("/world/") if path.startswith("/world/") else None
            lab = await session.get(Laboratory, env_id) if env_id else None
            sources = lab.sources if lab else []
            control = await session.get(CognitiveControl, k.instance_id)
            recent = (
                await session.scalars(
                    select(Experience).order_by(Experience.created_at.desc()).limit(3)
                )
            ).all()
            remaining = {
                unit: max(
                    0,
                    control.configuration["session_" + unit]
                    - control.spent.get("session_" + unit, 0)
                    - control.reserved.get(unit, 0),
                )
                for unit in ("calls", "tokens")
            }
        await self.charge_tool(run_id)
        await self.memory.index(limit=8)
        context = await self.memory.retrieve(
            observation.content[:500], "hybrid", 5, observation.source_event_id
        )
        memories = [
            {"id": m["id"], "content": redact(m["content"])[:500], "provenance": m["metadata"]}
            for m in context["results"]
        ]
        snapshot = {
            "schema_version": 1,
            "snapshot_id": uid(),
            "observation_id": observation.id,
            "source_event_ids": [observation.source_event_id],
            "observation": observation.content,
            "claims": observation.provenance["claims"],
            "environment_id": env_id,
            "environment_version": lab.version if lab else None,
            "environment_terminated": lab.state.get("environment_terminated", False)
            if lab
            else False,
            "sources": sources,
            "memories": memories,
            "goals": [{"id": g.id, "title": g.title, "status": g.status} for g in goals],
            "budget": run.budget,
            "remaining_session_budget": remaining,
            "recent_outcomes": [
                {
                    "experience_id": r.id,
                    "outcome": r.data["outcome_state"],
                    "evaluation": r.data["evaluation"].get("status"),
                }
                for r in recent
            ],
            "retrieval_mode": context["mode"],
            "requested_action_kind": control.configuration.get(
                "preferred_action", "record_analysis"
            ),
            "model_versions": {
                "provider": control.provider,
                "roles": (
                    {
                        role: self.k.settings.alive_role_models.get(
                            role, self.k.settings.alive_meta_model
                        )
                        for role in ("observer", "proposer", "critic")
                    }
                    if control.provider == "meta"
                    else {"all": "controlled-role-fixture-v1"}
                ),
            },
            "timestamp": now().isoformat(),
        }
        snapshot["state_hash"] = hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode()
        ).hexdigest()
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(Investigation, run_id)
            row.snapshot = snapshot
        return snapshot

    async def call_role(self, run_id, role, context):
        k = self.k
        schema = RoleOutput.model_json_schema()
        prompt = role_prompt(role)
        reserve = (
            len(
                json.dumps(
                    {"instructions": prompt, "data": context, "schema": schema}, ensure_ascii=False
                ).encode()
            )
            + 1024
        )
        async with k.lock, k.db.sessions.begin() as session:
            row = await session.get(Investigation, run_id)
            control = await session.get(CognitiveControl, k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            reserve += cfg.output_tokens
            if self.mode != "running" or row.state in TERMINAL:
                raise asyncio.CancelledError()
            if (
                reserve > cfg.request_tokens
                or row.usage["calls"] >= row.budget["calls"]
                or row.usage["tokens"] + reserve > row.budget["tokens"]
            ):
                raise BudgetExhausted(
                    "Per-request or investigation budget exhausted before inference"
                )
            model = k.settings.alive_role_models.get(role, k.settings.alive_meta_model)
            call = ModelInvocation(
                id=uid(),
                investigation_id=run_id,
                role=role,
                provider=control.provider,
                model=model if control.provider == "meta" else "controlled-role-fixture-v1",
                input_json={
                    "role_spec_version": ROLE_SPEC_VERSION,
                    "instructions": prompt,
                    "context": context,
                },
                reserved_tokens=reserve,
            )
            session.add(call)
            # Charge worst-case immediately. An interrupted request never gets a free retry.
            row.usage = row.usage | {
                "calls": row.usage["calls"] + 1,
                "tokens": row.usage["tokens"] + reserve,
            }
            call_id = call.id
            provider = control.provider
            self.k.add_event(
                session,
                "cognition.model_reserved",
                {
                    "invocation_id": call_id,
                    "role": role,
                    "provider": provider,
                    "model": call.model,
                    "reserved_tokens": reserve,
                },
                correlation=run_id,
            )
        started = time.monotonic()
        usage = {}
        try:
            if provider == "meta":
                generated = await MetaProvider(k.settings).structured(
                    prompt,
                    context,
                    schema,
                    model=model,
                    max_output=cfg.output_tokens,
                    correlation=call_id,
                )
                usage = generated.usage
                output = RoleOutput.model_validate_json(generated.text)
            else:
                await asyncio.sleep(0)
                output = mock_role(role, context)
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "mode": "controlled_fixture",
                }
            validate_references(output, context)
        except BaseException as exc:
            usage = getattr(exc, "usage", usage) or usage
            async with k.lock, k.db.sessions.begin() as session:
                call = await session.get(ModelInvocation, call_id)
                call.status = "cancelled" if isinstance(exc, asyncio.CancelledError) else "failed"
                call.error = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
                if "generated" in locals():
                    call.output_json = {
                        "invalid_visible_output": redact(generated.text),
                        "validation": "rejected",
                    }
                call.latency_ms = (time.monotonic() - started) * 1000
                call.usage = usage | {
                    "charged_tokens": reserve,
                    "reason": "conservative reservation retained",
                }
            raise
        latency = (time.monotonic() - started) * 1000
        actual = usage.get("total_tokens")
        charged = actual if isinstance(actual, int) and actual >= 0 else reserve
        async with k.lock, k.db.sessions.begin() as session:
            call = await session.get(ModelInvocation, call_id)
            call.status = "validated"
            call.output_json = output.model_dump()
            call.usage = usage | {"charged_tokens": charged}
            call.latency_ms = latency
            row = await session.get(Investigation, run_id)
            row.usage = row.usage | {
                "tokens": row.usage["tokens"] - reserve + charged,
                "latency_ms": row.usage["latency_ms"] + latency,
            }
        if charged > reserve:
            raise BudgetExhausted("Provider usage exceeded conservative reservation")
        await self.message(
            run_id,
            role,
            {
                "observer": "observation",
                "proposer": "proposal",
                "critic": "critique",
                "evaluator": "evaluation",
            }[role],
            output.model_dump(),
            call_id,
        )
        return output

    async def charge_tool(self, run_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(Investigation, run_id)
            if run.usage["tools"] >= run.budget["tools"]:
                raise BudgetExhausted("Tool budget exhausted")
            run.usage = run.usage | {"tools": run.usage["tools"] + 1}

    async def tool_evidence(self, run_id, snapshot):
        await self.charge_tool(run_id)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            lab = (
                await session.get(Laboratory, snapshot["environment_id"])
                if snapshot["environment_id"]
                else None
            )
            sources = lab.sources if lab else []
            if lab and lab.version != snapshot["environment_version"]:
                session.add(
                    CognitiveMessage(
                        id=uid(),
                        investigation_id=run_id,
                        sender="investigator",
                        recipient="governor",
                        message_type="abstention",
                        content={"reason": "Environment version changed; evidence is stale"},
                    )
                )
                return [], {
                    "reason": "Environment changed during investigation; re-observation required"
                }
        await self.message(
            run_id,
            "investigator",
            "evidence",
            {
                "sources": sources,
                "method": "read-only version-checked controlled sources",
                "tool_count": 1,
            },
        )
        return sources, {}

    async def execute(self, run_id):
        try:
            async with self.k.db.sessions() as session:
                control = await session.get(CognitiveControl, self.k.instance_id)
                config = CognitiveConfiguration.model_validate(control.configuration)
            async with asyncio.timeout(config.wall_seconds):
                await self.transition(run_id, "INVESTIGATING")
                snapshot = await self.world_state(run_id)
                await self.message(
                    run_id,
                    "governor",
                    "decision",
                    {
                        "state_snapshot": snapshot["snapshot_id"],
                        "policy": "attention-v1",
                        "permissions": ["authorised_memory", "controlled_sources"],
                        "budget_reserved": snapshot["budget"],
                    },
                )
                context = {
                    key: snapshot[key]
                    for key in [
                        "observation",
                        "claims",
                        "sources",
                        "memories",
                        "source_event_ids",
                        "requested_action_kind",
                    ]
                }
                observer = await self.call_role(run_id, "observer", context)
                context = context | {"observer": observer.model_dump()}
                proposer = await self.call_role(run_id, "proposer", context)
                context = context | {"proposal": proposer.model_dump()}
                critic = None
                if config.use_critic:
                    await self.transition(run_id, "CRITIQUING")
                    critic = await self.call_role(run_id, "critic", context)
                sources, limitations = await self.tool_evidence(run_id, snapshot)
                await self.transition(run_id, "EVALUATING")
                evaluation = evaluate(
                    snapshot["claims"], [c.model_dump() for c in proposer.claims], sources
                )
                evaluation["limitations"] += list(limitations.values())
                await self.message(run_id, "evaluator", "evaluation", evaluation)
                async with self.k.lock, self.k.db.sessions.begin() as session:
                    run = await session.get(Investigation, run_id)
                    run.evaluation = evaluation
                if (
                    limitations
                    or proposer.recommendation == "abstain"
                    or not proposer.actions
                    or (critic and critic.recommendation == "abstain")
                ):
                    await self.finish(
                        run_id,
                        "ABSTAINED",
                        {"effect": "none", "reason": "Evidence or role abstention"},
                    )
                else:
                    await self.propose_action(run_id, proposer.actions[0], evaluation)
        except asyncio.CancelledError:
            await self.finish(
                run_id,
                "CANCELLED",
                {"effect": "none", "reason": "autonomy cancelled"},
                truncated=True,
            )
        except Exception as exc:
            error = (
                str(exc)
                if isinstance(exc, (ProviderError, BudgetExhausted))
                else type(exc).__name__
            )
            await self.finish(
                run_id, "FAILED", {"effect": "none", "reason": error}, truncated=True, error=error
            )

    async def propose_action(self, run_id, proposal, evaluation):
        k = self.k
        risk = {"record_analysis": "A", "lab_draft": "B", "external_message": "C"}[proposal.kind]
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(Investigation, run_id)
            control = await session.get(CognitiveControl, k.instance_id)
            if self.mode != "running":
                raise asyncio.CancelledError()
            row = ActionProposal(
                id=uid(),
                investigation_id=run_id,
                kind=proposal.kind,
                risk_class=risk,
                proposal=proposal.model_dump()
                | {
                    "environment_id": run.snapshot["environment_id"],
                    "evaluation_status": evaluation["conclusion_status"],
                },
            )
            session.add(row)
            k.add_event(
                session,
                "action.proposed",
                {"action_id": row.id, "risk_class": risk, "investigation_id": run_id},
                correlation=run_id,
            )
            if risk == "A" or risk == "B" and control.configuration.get("lab_writes"):
                self._transition(session, run, "EXECUTING")
                await self._execute_action(session, row, run, control)
            else:
                row.status = "awaiting_approval"
                self._transition(session, run, "AWAITING_APPROVAL")

    async def _execute_action(self, session, action, run, control):
        if self.mode != "running":
            raise ValueError("Autonomy must be running before executing an action")
        if action.status == "executed":
            return
        if action.risk_class == "C":
            raise PermissionError("Consequential external actions are unsupported")
        if action.kind == "lab_draft":
            lab = await session.get(Laboratory, run.snapshot["environment_id"])
            if not lab:
                raise PermissionError("No authorised controlled environment")
            if lab.version != run.snapshot["environment_version"]:
                raise PermissionError("Environment changed; action approval is stale")
            lab.draft = redact(action.proposal["content"])
            lab.version += 1
            outcome = {
                "effect": "laboratory_draft_updated",
                "environment_id": lab.id,
                "version_before": run.snapshot["environment_version"],
                "version_after": lab.version,
            }
        else:
            event = self.k.add_event(
                session,
                "cognition.analysis_recorded",
                {"investigation_id": run.id},
                correlation=run.id,
            )
            await session.flush()
            memory = Memory(
                id=uid(),
                instance_id=self.k.instance_id,
                content=redact(action.proposal["content"]),
                memory_type="cognitive_analysis",
                source_event_id=str(event.event_id),
                metadata_json={
                    "investigation_id": run.id,
                    "provenance": "model_generated_analysis",
                    "evaluation": run.evaluation,
                    "independent_evidence": False,
                },
            )
            session.add(memory)
            outcome = {"effect": "analysis_memory_recorded", "memory_id": memory.id}
        action.status, action.outcome = "executed", outcome
        self.k.add_event(
            session,
            "action.executed",
            {"action_id": action.id, "outcome": outcome},
            correlation=run.id,
        )
        self._transition(session, run, "COMPLETED")
        goal = await session.get(Goal, run.goal_id)
        goal.status, goal.completed_at = "completed", now()
        self._experience(session, run, control, outcome, action=record(action))

    async def approve(self, action_id, decision):
        async with self.command_lock, self.k.lock, self.k.db.sessions.begin() as session:
            action = await session.get(ActionProposal, action_id)
            if not action:
                raise KeyError("Action proposal not found")
            if action.status == "executed":
                return record(action)
            if action.status != "awaiting_approval":
                raise ValueError("Action is no longer awaiting approval")
            run = await session.get(Investigation, action.investigation_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            if decision == "approve":
                if action.risk_class == "C":
                    raise PermissionError(
                        "Consequential external actions remain unsupported, even with approval"
                    )
                self.k.add_event(
                    session,
                    "action.approved",
                    {"action_id": action.id, "authority": "human"},
                    correlation=run.id,
                )
                self._transition(session, run, "EXECUTING")
                await self._execute_action(session, action, run, control)
            else:
                action.status = "rejected" if decision == "reject" else "cancelled"
                self._transition(session, run, "ABSTAINED" if decision == "reject" else "CANCELLED")
                self._experience(
                    session,
                    run,
                    control,
                    {"effect": "none", "reason": "human_" + decision},
                    action=record(action),
                    truncated=decision == "cancel",
                )
            return record(action)

    def _experience(self, session, run, control, outcome, *, action=None, truncated=False):
        # Called once on terminal transition; unique investigation_id is a final DB safeguard.
        used = run.usage
        control.reserved = {
            key: max(0, control.reserved.get(key, 0) - value) for key, value in run.budget.items()
        }
        control.spent = control.spent | {
            prefix + key: control.spent.get(prefix + key, 0) + used.get(key, 0)
            for prefix in ["session_", "experiment_"]
            for key in ["calls", "tokens", "tools"]
        }
        elapsed = max(0, (now() - aware(run.created_at)).total_seconds())
        verdict = run.evaluation.get("conclusion_status")
        reward = {
            "correctness": 1 if verdict == "VERIFIED" else 0 if verdict == "CONTRADICTED" else None,
            "task_progress": 1 if outcome.get("effect") not in ("none", None) else 0,
            "latency_cost": -elapsed / 180,
            "model_cost_usd": None,
            "permission_violations": 0,
        }
        data = {
            "schema_version": 1,
            "experience_id": uid(),
            "agent_instance": self.k.instance_id,
            "environment_id": run.snapshot.get("environment_id"),
            "episode_id": run.id,
            "state_snapshot": run.snapshot,
            "candidate_actions": action and [action["proposal"]] or [],
            "chosen_action": action,
            "behaviour_policy": "attention-v1/governor-v1",
            "selection_probability": 1.0,
            "action_permissions": {
                "automatic": ["A"],
                "B": "configured or explicit human approval",
                "C": "unsupported",
            },
            "outcome_state": outcome,
            "reward_components": reward,
            "reward_provenance": "deterministic source checks and observed database effects; "
            "unknown values remain null",
            "terminated": bool(run.snapshot.get("environment_terminated", False)),
            "truncated": truncated,
            "timestamp": now().isoformat(),
            "relevant_event_ids": run.snapshot.get("source_event_ids", []),
            "evaluation": run.evaluation,
            "model_versions": run.snapshot.get("model_versions", {"provider": "not_invoked"}),
            "embedding_version": {
                "model": self.memory.embedding.model_id,
                "revision": self.memory.embedding.revision,
                "used": run.snapshot.get("retrieval_mode") in ("hybrid_rrf", "vector_cosine"),
            },
            "usage": used,
            "elapsed_seconds": elapsed,
            "evaluation_split": "laboratory-acceptance-fixtures"
            if run.snapshot.get("environment_id")
            else "unspecified-user-environment",
            "outcome_termination_note": "Investigation completion is not environmental termination",
        }
        data = ExperienceRecord.model_validate(data).model_dump(mode="json")
        session.add(
            Experience(
                id=data["experience_id"],
                investigation_id=run.id,
                instance_id=self.k.instance_id,
                data=data,
            )
        )
        self.k.add_event(
            session,
            "cognition.experience_recorded",
            {
                "experience_id": data["experience_id"],
                "investigation_id": run.id,
                "state": run.state,
            },
            correlation=run.id,
        )

    async def finish(self, run_id, target, outcome, *, truncated=False, error=None):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(Investigation, run_id)
            if not run:
                raise KeyError("Investigation not found")
            if run.state in TERMINAL:
                return
            self._transition(session, run, target)
            run.error = error
            goal = await session.get(Goal, run.goal_id)
            if goal and target in ("FAILED", "CANCELLED", "ABSTAINED"):
                goal.status = "proposed"
            action = await session.scalar(
                select(ActionProposal).where(ActionProposal.investigation_id == run_id)
            )
            if action and action.status not in ("executed", "rejected"):
                action.status = "cancelled"
            control = await session.get(CognitiveControl, self.k.instance_id)
            self._experience(session, run, control, outcome, truncated=truncated)

    async def detail(self, run_id):
        async with self.k.db.sessions() as session:
            row = await session.get(Investigation, run_id)
            if not row:
                raise KeyError("Investigation not found")
            result = record(row)
            for name, model in [
                ("messages", CognitiveMessage),
                ("invocations", ModelInvocation),
                ("actions", ActionProposal),
                ("experiences", Experience),
            ]:
                result[name] = [
                    record(item)
                    for item in (
                        await session.scalars(
                            select(model)
                            .where(model.investigation_id == run_id)
                            .order_by(model.created_at)
                        )
                    ).all()
                ]
            return result

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        if self.worker and not self.worker.done():
            self.worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker
