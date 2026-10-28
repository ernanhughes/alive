"""Governor-bounded Chrome → Meta → observed feedback → durable empirical policy."""

import asyncio
import json
import time

from sqlalchemy import select

from alive.cognitive_models import CognitiveControl
from alive.cognitive_schema import CognitiveConfiguration, RoleOutput
from alive.experiment.metrics import price
from alive.experiment_budget import check_spend
from alive.living_evaluation import assess
from alive.living_models import LivingJourney, LivingPolicy, LivingTransition
from alive.living_policy import (
    choose,
    digest,
    state_from_dom,
    update,
    visible_measurement,
)
from alive.models import Memory, now, record, uid
from alive.providers import MetaProvider, ProviderError
from alive.schemas import BrowserAction
from alive.society import role_prompt

MODEL = "muse-spark-1.3"
INSTRUCTION = role_prompt("proposer") + (
    " Living-experience-v1: read-only evidence synthesis. Actions must be []. "
    "If sources is empty, abstain with claims=[]; current and historical claims are not "
    "verified current instrument evidence. If sources contains a visible current measurement, "
    "return one claim: subject Aster, predicate endurance_hours, numeric value from that "
    "measurement, evidence_refs=[its id], recommendation proceed. Explain whether it matches "
    "the observed page claim. Past experience is useful context, not current verification. "
    "Do not choose the browser action or request extra tools."
)


class Living:
    def __init__(self, app, kernel):
        self.app, self.k = app, kernel
        self.worker = None
        self.journey_id = None
        self.lock = asyncio.Lock()

    @property
    def active(self):
        return self.worker is not None and not self.worker.done()

    async def initialize(self):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            if not await session.get(LivingPolicy, self.k.instance_id):
                session.add(LivingPolicy(instance_id=self.k.instance_id))
            control = await session.get(CognitiveControl, self.k.instance_id)
            for journey in (
                await session.scalars(
                    select(LivingJourney).where(LivingJourney.status == "running")
                )
            ).all():
                ledger = [dict(c) for c in journey.data["ledger"]]
                for call in ledger:
                    if call["status"] == "reserved":
                        self.app.state.experiments._settle_control(
                            control, call["reserved_tokens"], call["reserved_tokens"]
                        )
                        call.update(
                            status="interrupted",
                            error="unknown provider completion",
                            charged_tokens=call["reserved_tokens"],
                        )
                journey.status = "interrupted"
                journey.data = journey.data | {
                    "ledger": ledger,
                    "error": "Backend restarted; no action or paid inference is replayed",
                }

    async def create(self, provider, allow):
        if not allow:
            raise PermissionError("Explicit controlled-browser read permission is required")
        if provider == "meta":
            catalog = await MetaProvider(self.k.settings).discover()
            if MODEL not in catalog.get("models", []):
                raise ValueError("Pinned Meta model unavailable")
        async with self.k.lock, self.k.db.sessions.begin() as session:
            policy = await session.get(LivingPolicy, self.k.instance_id)
            journey = LivingJourney(
                id=uid(),
                instance_id=self.k.instance_id,
                provider=provider,
                data={
                    "grant": "controlled local habitat read/click only",
                    "allow": True,
                    "max_calls": 2,
                    "max_tokens": 40000,
                    "max_micro_usd": 150000,
                    "max_tools": 6,
                    "initial_policy": policy.data,
                    "episodes": [],
                    "ledger": [],
                    "tool_log": [],
                    "phases": [],
                    "error": None,
                },
            )
            session.add(journey)
            self.k.add_event(
                session,
                "living.journey_created",
                {"journey_id": journey.id, "provider": provider, "scope": journey.data["grant"]},
            )
            await session.flush()
            return record(journey)

    async def advance(self, journey_id):
        async with self.lock:
            if self.active or self.app.state.experiments.active or self.app.state.web.active:
                raise ValueError("Another cognitive worker is active")
            async with self.k.lock, self.k.db.sessions.begin() as session:
                row = await session.get(LivingJourney, journey_id)
                if not row:
                    raise KeyError("Unknown journey")
                if row.status != "ready" or len(row.data["episodes"]) >= 2:
                    raise ValueError(
                        "Journey is not ready; interrupted episodes are never replayed"
                    )
                control = await session.get(CognitiveControl, self.k.instance_id)
                if control.mode == "running" or control.reserved.get("calls", 0):
                    raise ValueError("Pause autonomy and resolve outstanding reservations first")
                row.status = "running"
                row.data = row.data | {"error": None}
            self.journey_id = journey_id
            self.worker = asyncio.create_task(self.execute(journey_id))
            return {"status": "running", "journey_id": journey_id}

    async def phase(self, journey_id, stage, data=None):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(LivingJourney, journey_id)
            entry = {"stage": stage, "at": now().isoformat(), "data": data or {}}
            row.data = row.data | {"stage": stage, "phases": row.data["phases"] + [entry]}
            self.k.add_event(session, "living." + stage, {"journey_id": journey_id, **entry})
        await asyncio.sleep(0.12)

    async def tool(self, journey_id, episode, session_id, operation, url):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(LivingJourney, journey_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            browser = self.app.state.browsers
            if row.status != "running" or not row.data["allow"] or control.mode == "running":
                raise PermissionError("Controlled permission revoked or autonomy conflict")
            if not browser.allowed(url) or not url.startswith(
                f"http://127.0.0.1:8000/living/world/{journey_id}/"
            ):
                raise PermissionError("Living actions are restricted to this controlled habitat")
            count = sum(t["episode"] == episode for t in row.data["tool_log"])
            if count >= cfg.tool_calls or len(row.data["tool_log"]) >= row.data["max_tools"]:
                raise ValueError("Governor tool ceiling exhausted before browser action")
            if operation not in {"observe", "retrieve", "feedback"}:
                raise PermissionError("Unsupported living action")
            row.data = row.data | {
                "tool_log": row.data["tool_log"]
                + [
                    {
                        "episode": episode,
                        "operation": operation,
                        "session_id": session_id,
                        "at": now().isoformat(),
                        "url": url,
                    }
                ]
            }
            control.spent = control.spent | {
                p + "tools": control.spent.get(p + "tools", 0) + 1
                for p in ["session_", "experiment_"]
            }
            self.k.add_event(
                session,
                "living.governor_tool_permitted",
                {"journey_id": journey_id, "operation": operation, "episode": episode},
            )
        if operation == "observe":
            return await browser.navigate(session_id, url)
        if browser.page(session_id).url != url:
            raise PermissionError("Controlled page changed; re-observation required")
        selector = "#retrieve" if operation == "retrieve" else "#feedback-button"
        return await browser.action(session_id, BrowserAction(operation="click", selector=selector))

    async def reason(self, journey_id, episode, context):
        schema = RoleOutput.model_json_schema()
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(LivingJourney, journey_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            reserve = (
                len(
                    json.dumps(
                        {"instructions": INSTRUCTION, "input": context, "schema": schema}
                    ).encode()
                )
                + 1024
                + cfg.output_tokens
            )
            ledger = row.data["ledger"]
            used = sum(c.get("charged_tokens", c["reserved_tokens"]) for c in ledger)
            if control.mode == "running" or row.status != "running":
                raise PermissionError("Cognitive control changed")
            if (
                reserve > cfg.request_tokens
                or reserve > cfg.investigation_tokens
                or sum(c["episode"] == episode for c in ledger) >= cfg.investigation_calls
                or len(ledger) >= row.data["max_calls"]
                or used + reserve > row.data["max_tokens"]
            ):
                raise ValueError("Governor request, episode or journey ceiling exhausted")
            for p in ["session_", "experiment_"]:
                if control.spent.get(p + "calls", 0) + control.reserved.get(
                    "calls", 0
                ) + 1 > getattr(cfg, p + "calls") or control.spent.get(
                    p + "tokens", 0
                ) + control.reserved.get("tokens", 0) + reserve > getattr(cfg, p + "tokens"):
                    raise ValueError("Governor cumulative budget exhausted before inference")
            check_spend(ledger, reserve, cap=row.data["max_micro_usd"])
            call = {
                "id": uid(),
                "episode": episode,
                "status": "reserved",
                "usage": None,
                "reserved_tokens": reserve,
                "provider": row.provider,
                "model": MODEL if row.provider == "meta" else "controlled-living-v1",
                "input": context,
                "instructions": INSTRUCTION,
                "started_at": now().isoformat(),
            }
            row.data = row.data | {"ledger": ledger + [call]}
            control.reserved = control.reserved | {
                "calls": control.reserved.get("calls", 0) + 1,
                "tokens": control.reserved.get("tokens", 0) + reserve,
            }
            provider = row.provider
        started, usage, output, error = time.monotonic(), None, None, None
        try:
            if provider == "meta":
                generated = await MetaProvider(self.k.settings).structured(
                    INSTRUCTION,
                    context,
                    schema,
                    model=MODEL,
                    max_output=cfg.output_tokens,
                    correlation=call["id"],
                )
                usage = generated.usage
                output = RoleOutput.model_validate_json(generated.text)
            else:
                sources = context["sources"]
                output = RoleOutput(
                    summary="Controlled fixture, not live inference.",
                    claims=[
                        {
                            "subject": "Aster",
                            "predicate": "endurance_hours",
                            "value": sources[0]["value"],
                            "evidence_refs": [sources[0]["id"]],
                        }
                    ]
                    if sources
                    else [],
                    actions=[],
                    criticisms=[],
                    uncertainties=[] if sources else ["No current instrument evidence"],
                    recommendation="proceed" if sources else "abstain",
                    confidence=0.9,
                )
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "mode": "controlled_fixture",
                }
            if output.actions:
                raise ValueError("Living synthesis cannot request executable actions")
        except BaseException as exc:
            usage = getattr(exc, "usage", None) or usage
            error = exc.category if isinstance(exc, ProviderError) else type(exc).__name__
        charged = usage.get("total_tokens") if usage and not error else reserve
        if not isinstance(charged, int) or charged < 0:
            charged = reserve
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await session.get(LivingJourney, journey_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            self.app.state.experiments._settle_control(control, reserve, charged)
            settled = call | {
                "status": "failed" if error else "validated",
                "usage": usage,
                "charged_tokens": charged,
                "estimated_usd": price(usage),
                "error": error,
                "output": output.model_dump() if output else None,
                "latency_ms": (time.monotonic() - started) * 1000,
                "completed_at": now().isoformat(),
            }
            row.data = row.data | {
                "ledger": [settled if c["id"] == call["id"] else c for c in row.data["ledger"]]
            }
        if error == "CancelledError":
            raise asyncio.CancelledError()
        if error or charged > reserve:
            raise ValueError("Model call failed or exceeded reservation: " + str(error))
        return output, call["id"]

    async def execute(self, journey_id):
        browser_id = None
        try:
            async with self.k.db.sessions() as session:
                row = await session.get(LivingJourney, journey_id)
                episode = len(row.data["episodes"]) + 1
                provider = row.provider
                cfg = CognitiveConfiguration.model_validate(
                    (await session.get(CognitiveControl, self.k.instance_id)).configuration
                )
            async with asyncio.timeout(cfg.wall_seconds):
                browser_id = (await self.app.state.browsers.create())["id"]
                url = f"http://127.0.0.1:8000/living/world/{journey_id}/{episode}"
                await self.phase(journey_id, "observing", {"episode": episode})
                observation = await self.tool(journey_id, episode, browser_id, "observe", url)
                state = state_from_dom(observation["text"], provider)
                await self.phase(
                    journey_id, "observed", {"state": state, "observation": observation}
                )
                async with self.k.db.sessions() as session:
                    policy = (await session.get(LivingPolicy, self.k.instance_id)).data
                    journey = await session.get(LivingJourney, journey_id)
                    memories = (
                        await session.scalars(
                            select(LivingTransition)
                            .where(
                                LivingTransition.instance_id == self.k.instance_id,
                                LivingTransition.context == state["context"],
                            )
                            .order_by(LivingTransition.created_at.desc())
                            .limit(20)
                        )
                    ).all()
                    relevant = [
                        {
                            "id": m.id,
                            "action": m.data["choice"]["action"],
                            "reward": m.data["reward"],
                            "outcome": m.data["outcome"],
                        }
                        for m in memories
                    ]
                    initial = journey.data["initial_policy"]
                choice = choose(policy, state["context"])
                cold = choose(initial, state["context"])
                await self.phase(
                    journey_id, "remembering", {"memory_ids": [m["id"] for m in relevant]}
                )
                await self.phase(journey_id, "predicting", choice)
                await self.phase(
                    journey_id,
                    "choosing",
                    {
                        "action": choice["action"],
                        "initial_policy_counterfactual": cold["action"],
                        "feature_hash": state["feature_hash"],
                    },
                )
                evidence, sources = None, []
                if choice["action"] == "retrieve":
                    evidence = await self.tool(journey_id, episode, browser_id, "retrieve", url)
                    sources = [
                        {
                            "id": f"measurement:{journey_id}:{episode}",
                            "value": visible_measurement(evidence["text"]),
                            "provenance": "Visible current Chrome DOM after permitted retrieval",
                        }
                    ]
                await self.phase(
                    journey_id,
                    "acting",
                    {"action": choice["action"], "evidence": evidence, "sources": sources},
                )
                await self.phase(
                    journey_id, "reasoning", {"action_already_selected": choice["action"]}
                )
                output, call_id = await self.reason(
                    journey_id,
                    episode,
                    {
                        "observation": observation["text"],
                        "sources": sources,
                        "relevant_experience": relevant,
                        "chosen_action": choice["action"],
                    },
                )
                feedback = await self.tool(journey_id, episode, browser_id, "feedback", url)
                measured = visible_measurement(feedback["text"], feedback=True)
                assessment = assess(output, sources, measured)
                resolved, safely_abstained = assessment["resolved"], assessment["safe_abstention"]
                reward = 1.0 if resolved else -0.5 if safely_abstained else -1.0
                reward -= 0.15 if choice["action"] == "retrieve" else 0
                outcome = {
                    **assessment,
                    "measurement": measured,
                    "resource_cost": 0.15 if sources else 0,
                    "synthetic_goal_reward": reward,
                }
                await self.phase(journey_id, "feedback", outcome)
                async with self.k.lock, self.k.db.sessions.begin() as session:
                    current = await session.get(LivingPolicy, self.k.instance_id)
                    if digest(current.data) != choice["policy_hash"]:
                        raise ValueError("Policy changed during episode; no stale update allowed")
                    after = update(current.data, choice["action"], reward, state["context"])
                    transition = LivingTransition(
                        id=uid(),
                        instance_id=self.k.instance_id,
                        journey_id=journey_id,
                        episode=episode,
                        context=state["context"],
                        data={
                            "episode": episode,
                            "state": state,
                            "choice": choice,
                            "initial_policy_counterfactual": cold,
                            "memory_ids": [m["id"] for m in relevant],
                            "relevant_experience": relevant,
                            "observation": observation,
                            "evidence": evidence,
                            "feedback": feedback,
                            "model_output": output.model_dump(),
                            "model_call_id": call_id,
                            "outcome": outcome,
                            "reward": reward,
                            "prediction_error": reward
                            - choice["predictions"][choice["action"]]["mean"],
                            "policy_before": current.data,
                            "policy_after": after,
                            "before_hash": digest(current.data),
                            "after_hash": digest(after),
                            "next_choice": choose(after, state["context"]),
                            "browser_session_id": browser_id,
                            "reward_provenance": "Published end-of-episode Chrome DOM, "
                            "checked against "
                            "the current observed instrument conclusion; synthetic goal utility",
                        },
                    )
                    session.add(transition)
                    current.data, current.updated_at = after, now()
                    journey = await session.get(LivingJourney, journey_id)
                    journey.data = journey.data | {
                        "episodes": journey.data["episodes"] + [transition.id],
                        "stage": "learned",
                    }
                    journey.status = "completed" if episode == 2 else "ready"
                    event = self.k.add_event(
                        session,
                        "living.experience_learned",
                        {
                            "journey_id": journey_id,
                            "transition_id": transition.id,
                            "policy_before": choice["policy_hash"],
                            "policy_after": digest(after),
                        },
                    )
                    session.add(
                        Memory(
                            instance_id=self.k.instance_id,
                            content=f"Living experience: {state['recent_event']}; "
                            f"{choice['action']} "
                            f"returned {reward}; current-goal resolved={resolved}.",
                            source_event_id=str(event.event_id),
                            metadata_json={
                                "transition_id": transition.id,
                                "context": state["context"],
                                "provenance": "Observed controlled-browser feedback",
                            },
                        )
                    )
        except BaseException as exc:
            error = (
                str(exc) if isinstance(exc, (ValueError, PermissionError)) else type(exc).__name__
            )
            async with self.k.lock, self.k.db.sessions.begin() as session:
                row = await session.get(LivingJourney, journey_id)
                row.status = "stopped" if isinstance(exc, asyncio.CancelledError) else "failed"
                row.data = row.data | {"error": error, "stage": row.status}
                self.k.add_event(
                    session, "living.interrupted", {"journey_id": journey_id, "error": error}
                )
        finally:
            if browser_id:
                await self.app.state.browsers.close_session(browser_id)

    async def cancel(self, journey_id=None):
        if journey_id and self.active and journey_id != self.journey_id:
            raise ValueError("A different living journey is active")
        if self.active:
            self.worker.cancel()
            await self.worker
        target = journey_id or self.journey_id
        if target:
            async with self.k.lock, self.k.db.sessions.begin() as session:
                row = await session.get(LivingJourney, target)
                if row and row.status != "completed":
                    row.status = "stopped"
                    row.data = row.data | {"allow": False, "stage": "stopped"}
        return {"status": "stopped"}

    async def close(self):
        # Idle, explicitly authorized next steps survive restart; no action auto-resumes.
        if self.active:
            await self.cancel()

    async def detail(self, journey_id):
        async with self.k.db.sessions() as session:
            row = await session.get(LivingJourney, journey_id)
            if not row:
                raise KeyError("Unknown journey")
            result = record(row)
            result["transitions"] = [
                record(t)
                for t in (
                    await session.scalars(
                        select(LivingTransition)
                        .where(LivingTransition.journey_id == journey_id)
                        .order_by(LivingTransition.episode)
                    )
                ).all()
            ]
            result["current_policy"] = (await session.get(LivingPolicy, self.k.instance_id)).data
            return result
