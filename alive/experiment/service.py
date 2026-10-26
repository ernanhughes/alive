"""Paired experiments consume the existing Governor's persisted budgets; no external actions."""

import asyncio
import json
import random
import time

from sqlalchemy import DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from alive.cognitive_models import CognitiveControl
from alive.cognitive_schema import CognitiveConfiguration, RoleOutput
from alive.experiment.corpus import ROOT, load
from alive.experiment.freeze import seal, verify
from alive.experiment.metrics import price, summarize
from alive.experiment.policy import AlwaysCritic, NeverCritic, SelectiveCritic, calibrate, features
from alive.experiment.prompts import MODEL, prompt, specification
from alive.experiment.scoring import score, solve
from alive.models import Base, J, now, record, uid
from alive.providers import MetaProvider, ProviderError


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    phase: Mapped[str]
    provider: Mapped[str]
    status: Mapped[str] = mapped_column(default="running")
    data: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


class ExperimentAuthorization(Base):
    __tablename__ = "experiment_authorizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    freeze_id: Mapped[str]
    limits: Mapped[dict] = mapped_column(J)
    consumed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=now)


def mock_decision(payload, role):
    expected = solve(payload)
    if expected["status"] == "ABSTAIN":
        return RoleOutput(
            summary="Controlled fixture: evidence is insufficient or inconsistent.",
            claims=[],
            actions=[],
            criticisms=[],
            uncertainties=["Unresolved evidence"],
            recommendation="abstain",
            confidence=0.5,
        )
    refs = [s["id"] for s in payload["sources"] if s["authority"] == "verified"]
    poisoned = any(s["authority"] == "unverified" for s in payload["sources"]) and role == "initial"
    return RoleOutput(
        summary="Controlled role fixture, not live inference.",
        claims=[
            {
                "subject": payload["subject"],
                "predicate": "computed_result",
                "value": str(999 if poisoned else expected["value"]),
                "evidence_refs": refs,
            }
        ],
        actions=[],
        criticisms=["Rejected untrusted annotation"] if role == "critic" else [],
        uncertainties=[],
        recommendation="proceed",
        confidence=0.9,
    )


class Experiments:
    def __init__(self, kernel):
        self.k = kernel
        self.worker = None
        self.run_id = None
        self.lock = asyncio.Lock()

    @property
    def active(self):
        return self.worker is not None and not self.worker.done()

    async def initialize(self):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            runs = (
                await session.scalars(
                    select(ExperimentRun).where(ExperimentRun.status == "running")
                )
            ).all()
            control = await session.get(CognitiveControl, self.k.instance_id)
            for run in runs:
                data = dict(run.data)
                ledger = [dict(c) for c in data["ledger"]]
                for call in ledger:
                    if call["status"] == "reserved":
                        self._settle_control(
                            control, call["reserved_tokens"], call["reserved_tokens"]
                        )
                        call.update(
                            status="interrupted",
                            error="unknown_provider_completion",
                            charged_tokens=call["reserved_tokens"],
                            usage=None,
                        )
                data["ledger"] = ledger
                data["interruption"] = "Backend restarted; no inference is automatically replayed"
                run.status, run.data = "interrupted", data

    async def freeze(self, final=False):
        async with self.lock:
            if self.active:
                raise ValueError("Stop the active experiment before freezing")
            async with self.k.db.sessions() as session:
                full = await session.scalar(
                    select(ExperimentRun.id).where(ExperimentRun.phase == "full")
                )
                if full:
                    raise ValueError(
                        "Evaluation has been unsealed; specification cannot be changed"
                    )
            return seal(final)

    async def authorize(self, data):
        verify(data.freeze_id)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            pilots = (
                await session.scalars(
                    select(ExperimentRun).where(
                        ExperimentRun.phase == "pilot",
                        ExperimentRun.provider == "meta",
                        ExperimentRun.status == "completed",
                    )
                )
            ).all()
            if not any(
                run.data["freeze_id"] == data.freeze_id
                and len(run.data["rows"]) == 4
                and all(
                    row.get("eligible") and not any(a.get("error") for a in row["arms"].values())
                    for row in run.data["rows"]
                )
                for run in pilots
            ):
                raise ValueError(
                    "A completed live Meta pilot for this exact freeze is required first"
                )
            authorization = ExperimentAuthorization(
                id=uid(),
                instance_id=self.k.instance_id,
                freeze_id=data.freeze_id,
                limits={
                    "max_calls": data.max_calls,
                    "max_tokens": data.max_tokens,
                    "owner_confirmation": data.confirmation,
                    "session_plan": data.session_plan,
                },
            )
            session.add(authorization)
            await session.flush()
            self.k.add_event(
                session,
                "experiment.full_authorized",
                {
                    "authorization_id": authorization.id,
                    "freeze_id": data.freeze_id,
                    "limits": authorization.limits,
                },
            )
            return record(authorization)

    async def start(self, request):
        async with self.lock:
            if self.active:
                raise ValueError("Only one experimental worker may run")
            final = request.phase != "calibration"
            frozen = verify(request.freeze_id, final=final)
            if final and request.provider == "meta":
                parameters = json.loads((ROOT / "policy-configuration.json").read_text())
                if parameters.get("provider") != "meta":
                    raise ValueError("Primary Meta pilot/full run requires live Meta calibration")
            if request.provider == "meta":
                catalog = await MetaProvider(self.k.settings).discover()
                if MODEL not in catalog.get("models", []):
                    raise ValueError("Pinned Meta model unavailable")
            async with self.k.lock, self.k.db.sessions.begin() as session:
                control = await session.get(CognitiveControl, self.k.instance_id)
                if control.mode == "running":
                    raise ValueError("Pause cognitive autonomy before running an experiment")
                cfg = CognitiveConfiguration.model_validate(control.configuration)
                if cfg.output_tokens != 1536 or cfg.wall_seconds != 90:
                    raise ValueError(
                        "Frozen model controls require output_tokens=1536 and wall_seconds=90"
                    )
                if cfg.investigation_calls < 3 and request.phase != "calibration":
                    raise ValueError("Task budget must permit at most three physical paired calls")
                if request.phase == "full":
                    authorization = (
                        await session.get(ExperimentAuthorization, request.authorization_id)
                        if request.authorization_id
                        else None
                    )
                    if (
                        not authorization
                        or authorization.consumed
                        or authorization.freeze_id != request.freeze_id
                    ):
                        raise PermissionError(
                            (
                                "Full paid evaluation requires new explicit owner authorization"
                                " for this freeze"
                            )
                        )
                    if request.provider != "meta":
                        raise ValueError(
                            "Full primary evaluation requires the pinned live Meta model"
                        )
                    if (
                        request.max_calls > authorization.limits["max_calls"]
                        or request.max_tokens > authorization.limits["max_tokens"]
                    ):
                        raise PermissionError("Requested run exceeds authorized limits")
                    if cfg.session_calls < 180:
                        raise ValueError(
                            "Full run needs an owner-configured 180-call session ceiling"
                        )
                    if (
                        control.spent.get("experiment_calls", 0) + request.max_calls
                        > cfg.experiment_calls
                    ):
                        raise ValueError(
                            "Governor has insufficient remaining full-evaluation calls"
                        )
                    if (
                        control.spent.get("experiment_tokens", 0) + request.max_tokens
                        > cfg.experiment_tokens
                    ):
                        raise ValueError(
                            "Governor has insufficient remaining full-evaluation tokens"
                        )
                    authorization.consumed = True
                    control.session_id = uid()
                    control.spent = {
                        key: value
                        for key, value in control.spent.items()
                        if key.startswith("experiment_")
                    }
                manifest = json.loads((ROOT / "split-manifest.json").read_text())
                ids = (
                    manifest["calibration_live_ids"]
                    if request.phase == "calibration"
                    else manifest["pilot_ids"]
                    if request.phase == "pilot"
                    else [t.id for t in load("evaluation")]
                )
                run = ExperimentRun(
                    id=uid(),
                    instance_id=self.k.instance_id,
                    phase=request.phase,
                    provider=request.provider,
                    data={
                        "freeze_id": request.freeze_id,
                        "source_identity": frozen,
                        "task_ids": ids,
                        "limits": request.model_dump(),
                        "model": MODEL,
                        "prompts": specification(),
                        "configuration_snapshot": cfg.model_dump(),
                        "rows": [],
                        "ledger": [],
                        "evaluation_unsealed": request.phase == "full",
                        "started_at": now().isoformat(),
                        "completed_tasks": 0,
                        "physical_calls": 0,
                        "charged_tokens": 0,
                    },
                )
                session.add(run)
                self.k.add_event(
                    session,
                    "experiment.started",
                    {
                        "run_id": run.id,
                        "phase": run.phase,
                        "provider": run.provider,
                        "tasks": len(ids),
                        "freeze_id": request.freeze_id,
                    },
                )
                self.run_id = run.id
            self.worker = asyncio.create_task(self.execute(run.id))
            return {"id": run.id, "phase": request.phase, "tasks": len(ids)}

    def _settle_control(self, control, reserved, charged):
        control.reserved = control.reserved | {
            "calls": max(0, control.reserved.get("calls", 0) - 1),
            "tokens": max(0, control.reserved.get("tokens", 0) - reserved),
        }
        control.spent = (
            control.spent
            | {
                prefix + "calls": control.spent.get(prefix + "calls", 0) + 1
                for prefix in ["session_", "experiment_"]
            }
            | {
                prefix + "tokens": control.spent.get(prefix + "tokens", 0) + charged
                for prefix in ["session_", "experiment_"]
            }
        )

    async def call(self, run_id, task, role, context, arm):
        schema = RoleOutput.model_json_schema()
        instructions = prompt(role)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(ExperimentRun, run_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            if control.mode == "running":
                raise ValueError("Autonomy conflicts with the experiment worker")
            reserve = (
                len(
                    json.dumps(
                        {"instructions": instructions, "input": context, "schema": schema},
                        ensure_ascii=False,
                    ).encode()
                )
                + 1024
                + cfg.output_tokens
            )
            if reserve > cfg.request_tokens:
                raise ValueError("Governor per-request token budget exhausted")
            if (
                len([c for c in run.data["ledger"] if c["task_id"] == task.id])
                >= cfg.investigation_calls
            ):
                raise ValueError("Governor per-investigation call ceiling exhausted")
            task_spent = sum(
                c.get("charged_tokens", c["reserved_tokens"])
                for c in run.data["ledger"]
                if c["task_id"] == task.id
            )
            if task_spent + reserve > cfg.investigation_tokens:
                raise ValueError("Governor per-investigation token ceiling exhausted")
            if (
                run.data["physical_calls"] >= run.data["limits"]["max_calls"]
                or run.data["charged_tokens"] + reserve > run.data["limits"]["max_tokens"]
            ):
                raise ValueError("Explicit experiment ceiling exhausted before inference")
            for prefix, limit in [
                ("session_", cfg.session_calls),
                ("experiment_", cfg.experiment_calls),
            ]:
                if (
                    control.spent.get(prefix + "calls", 0) + control.reserved.get("calls", 0) + 1
                    > limit
                ):
                    raise ValueError("Governor " + prefix + "call budget exhausted")
            for prefix, limit in [
                ("session_", cfg.session_tokens),
                ("experiment_", cfg.experiment_tokens),
            ]:
                if (
                    control.spent.get(prefix + "tokens", 0)
                    + control.reserved.get("tokens", 0)
                    + reserve
                    > limit
                ):
                    raise ValueError("Governor " + prefix + "token budget exhausted")
            call = {
                "id": uid(),
                "task_id": task.id,
                "role": role,
                "arm": arm,
                "provider": run.provider,
                "model": MODEL,
                "status": "reserved",
                "reserved_tokens": reserve,
                "input": context,
                "instructions": instructions,
                "started_at": now().isoformat(),
                "usage": None,
                "latency_ms": 0,
                "output": None,
            }
            control.reserved = control.reserved | {
                "calls": control.reserved.get("calls", 0) + 1,
                "tokens": control.reserved.get("tokens", 0) + reserve,
            }
            run.data = run.data | {
                "ledger": run.data["ledger"] + [call],
                "physical_calls": run.data["physical_calls"] + 1,
                "charged_tokens": run.data["charged_tokens"] + reserve,
                "current_task": task.id,
            }
            provider = run.provider
            self.k.add_event(
                session,
                "experiment.model_reserved",
                {
                    "run_id": run_id,
                    "call_id": call["id"],
                    "role": role,
                    "arm": arm,
                    "reserved_tokens": reserve,
                },
            )
        started = time.monotonic()
        usage = None
        output = None
        error = None
        try:
            if provider == "meta":
                generated = await MetaProvider(self.k.settings).structured(
                    instructions,
                    context,
                    schema,
                    model=MODEL,
                    max_output=cfg.output_tokens,
                    correlation=call["id"],
                )
                usage = generated.usage
                output = RoleOutput.model_validate_json(generated.text)
            else:
                await asyncio.sleep(0)
                output = mock_decision(task.payload(), role)
                usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "mode": "controlled_fixture",
                }
        except BaseException as exc:
            usage = getattr(exc, "usage", None) or usage
            error = exc.category if isinstance(exc, ProviderError) else type(exc).__name__
            if isinstance(exc, asyncio.CancelledError):
                error = "cancelled"
        reported = usage.get("total_tokens") if usage else None
        charged = (
            reported if isinstance(reported, int) and reported >= 0 and error is None else reserve
        )
        latency = (time.monotonic() - started) * 1000
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(ExperimentRun, run_id)
            control = await session.get(CognitiveControl, self.k.instance_id)
            self._settle_control(control, reserve, charged)
            updated = dict(call) | {
                "status": "failed" if error else "validated",
                "error": error,
                "usage": usage,
                "charged_tokens": charged,
                "latency_ms": latency,
                "output": output.model_dump() if output else None,
                "estimated_usd": price(usage),
                "completed_at": now().isoformat(),
            }
            ledger = [updated if c["id"] == call["id"] else c for c in run.data["ledger"]]
            run.data = run.data | {
                "ledger": ledger,
                "charged_tokens": run.data["charged_tokens"] - reserve + charged,
            }
            self.k.add_event(
                session,
                "experiment.model_completed",
                {
                    "run_id": run_id,
                    "call_id": call["id"],
                    "status": updated["status"],
                    "charged_tokens": charged,
                    "error": error,
                },
            )
        if error == "cancelled":
            raise asyncio.CancelledError()
        if charged > reserve:
            raise ValueError("Provider usage exceeded reservation; no further inference allowed")
        return output, updated

    async def task(self, run_id, task, phase, configuration):
        task_started = time.monotonic()
        payload = task.payload()
        initial, base_call = await self.call(run_id, task, "initial", payload, "shared_initial")
        initial_elapsed = (time.monotonic() - task_started) * 1000
        if initial is None:
            failure = {
                "correct": False,
                "correct_abstention": False,
                "abstained": False,
                "unsupported_acceptance": False,
                "citation_validity": None,
                "expected_status": solve(payload)["status"],
                "reason": "initial_model_failure",
            }
            return {
                "task_id": task.id,
                "split": task.split,
                "category": task.category,
                "family": task.family,
                "error": "initial_model_failure",
                "initial_score": {"correct": False},
                "shared_initial_ref": base_call["id"],
                "eligible": False,
                "paired_execution_wall_ms": (time.monotonic() - task_started) * 1000,
                "arms": {
                    policy: {
                        "invoked": False,
                        "score": failure,
                        "error": base_call.get("error"),
                        "allocated_tokens": (base_call.get("usage") or {}).get("total_tokens", 0),
                        "estimated_usd": price(base_call.get("usage")),
                        "path_latency_ms": base_call["latency_ms"],
                        "end_to_end_latency_ms": initial_elapsed,
                        "choice": {
                            "reason": "No valid initial artifact; investigation is ineligible"
                        },
                    }
                    for policy in (
                        ["never", "always"]
                        if phase == "calibration"
                        else ["never", "always", "selective"]
                    )
                },
            }
        initial_score = score(payload, initial)
        anticipated = max(
            1,
            len(json.dumps(payload | {"initial_decision": initial.model_dump()}).encode()) // 4
            + 700,
        )
        state = features(payload, initial, anticipated)
        row = {
            "task_id": task.id,
            "split": task.split,
            "category": task.category,
            "family": task.family,
            "initial_score": initial_score,
            "initial_decision": initial.model_dump(),
            "features": state.model_dump(),
            "shared_initial_ref": base_call["id"],
            "arms": {},
            "eligible": True,
        }
        choices = {"never": NeverCritic().choose(state), "always": AlwaysCritic().choose(state)}
        if phase != "calibration":
            choices["selective"] = SelectiveCritic(
                configuration["threshold"], configuration["cost_weight"]
            ).choose(state)
        order = list(choices)
        random.Random("paired-arm-order-v1:" + task.id).shuffle(order)
        for policy in order:
            arm_started = time.monotonic()
            choice = choices[policy]
            call = None
            result = initial
            error = None
            if choice.invoke:
                result, call = await self.call(
                    run_id,
                    task,
                    "critic",
                    payload | {"initial_decision": initial.model_dump()},
                    policy,
                )
                error = call.get("error")
            evaluated = (
                score(payload, result)
                if result
                else {
                    "correct": False,
                    "correct_abstention": False,
                    "abstained": False,
                    "unsupported_acceptance": False,
                    "citation_validity": None,
                    "expected_status": solve(payload)["status"],
                    "reason": "model_failure",
                }
            )
            call_tokens = call["usage"].get("total_tokens", 0) if call and call.get("usage") else 0
            base_tokens = base_call["usage"].get("total_tokens", 0) if base_call.get("usage") else 0
            costs = [price(base_call.get("usage"))] + ([price(call.get("usage"))] if call else [])
            row["arms"][policy] = {
                "choice": choice.model_dump(),
                "invoked": choice.invoke,
                "decision": result.model_dump() if result else None,
                "score": evaluated,
                "error": error,
                "shared_initial_ref": base_call["id"],
                "critic_call_ref": call["id"] if call else None,
                "allocated_tokens": base_tokens + call_tokens,
                "critic_tokens": call_tokens,
                "path_latency_ms": base_call["latency_ms"] + (call["latency_ms"] if call else 0),
                "end_to_end_latency_ms": initial_elapsed + (time.monotonic() - arm_started) * 1000,
                "estimated_usd": sum(costs) if all(cost is not None for cost in costs) else None,
            }
        row["paired_execution_wall_ms"] = (time.monotonic() - task_started) * 1000
        return row

    async def execute(self, run_id):
        status = "completed"
        error = None
        try:
            async with self.k.db.sessions() as session:
                run = await session.get(ExperimentRun, run_id)
                phase = run.phase
                tasks = {t.id: t for t in load("evaluation" if phase == "full" else "calibration")}
                ids = run.data["task_ids"]
                cfg = CognitiveConfiguration.model_validate(run.data["configuration_snapshot"])
            configuration = (
                json.loads((ROOT / "policy-configuration.json").read_text())
                if phase != "calibration"
                else None
            )
            for index, task_id in enumerate(ids):
                verify(run.data["freeze_id"], final=phase != "calibration")
                if phase == "full" and index == 60:
                    async with self.k.lock, self.k.db.sessions.begin() as session:
                        control = await session.get(CognitiveControl, self.k.instance_id)
                        if control.reserved.get("calls", 0):
                            raise ValueError("Cannot roll over a reserved session")
                        control.session_id = uid()
                        control.spent = {
                            key: value
                            for key, value in control.spent.items()
                            if key.startswith("experiment_")
                        }
                        self.k.add_event(
                            session,
                            "experiment.authorized_session_boundary",
                            {"run_id": run_id, "completed_tasks": 60},
                        )
                async with asyncio.timeout(cfg.wall_seconds):
                    row = await self.task(run_id, tasks[task_id], phase, configuration)
                async with self.k.lock, self.k.db.sessions.begin() as session:
                    run = await session.get(ExperimentRun, run_id)
                    rows = run.data["rows"] + [row]
                    run.data = run.data | {"rows": rows, "completed_tasks": len(rows)}
                    self.k.add_event(
                        session, "experiment.task_completed", {"run_id": run_id, "task_id": task_id}
                    )
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            status, error = "cancelled", "cancelled_by_owner_or_shutdown"
        except Exception as exc:
            status, error = (
                "failed",
                str(exc) if isinstance(exc, ValueError) else type(exc).__name__,
            )
        async with self.k.lock, self.k.db.sessions.begin() as session:
            run = await session.get(ExperimentRun, run_id)
            run.status = status
            run.updated_at = now()
            run.data = run.data | {
                "completed_at": now().isoformat(),
                "error": error,
                "summary": summarize(run.data["rows"], run.data["ledger"]),
            }
            self.k.add_event(
                session,
                "experiment.completed",
                {"run_id": run_id, "status": status, "error": error},
            )

    async def finalize(self, run_id):
        async with self.lock:
            if self.active:
                raise ValueError("Wait for calibration to finish")
            async with self.k.db.sessions() as session:
                if await session.scalar(
                    select(ExperimentRun.id).where(ExperimentRun.phase == "full")
                ):
                    raise ValueError("Evaluation is unsealed; policy changes are forbidden")
                run = await session.get(ExperimentRun, run_id)
                if not run or run.phase != "calibration" or run.status != "completed":
                    raise ValueError("A completed calibration run is required")
                verify(run.data["freeze_id"], final=False)
                evidence = []
                for row in run.data["rows"]:
                    if not row.get("eligible") or row["arms"]["always"].get("error"):
                        raise ValueError("Calibration contains an unresolved model failure")
                    reviewed = row["arms"]["always"]
                    evidence.append(
                        {
                            "task_id": row["task_id"],
                            "split": row["split"],
                            "features": row["features"],
                            "initial_score": row["initial_score"],
                            "critic_score": reviewed["score"],
                            "critic_tokens": reviewed["critic_tokens"],
                            "shared_initial_ref": row["shared_initial_ref"],
                            "critic_call_ref": reviewed["critic_call_ref"],
                        }
                    )
                if len(evidence) != 8:
                    raise ValueError("All eight predeclared development pairs are required")
                parameters = calibrate(evidence) | {
                    "provider": run.provider,
                    "model": MODEL,
                    "source_run_id": run_id,
                }
            (ROOT / "calibration-evidence.json").write_bytes(
                (json.dumps(evidence, indent=2) + "\n").encode()
            )
            (ROOT / "policy-configuration.json").write_bytes(
                (json.dumps(parameters, indent=2) + "\n").encode()
            )
            return seal(final=True)

    async def cancel(self):
        if self.active:
            self.worker.cancel()
            await self.worker
        return {"status": "stopped"}

    async def close(self):
        await self.cancel()

    async def detail(self, run_id):
        async with self.k.db.sessions() as session:
            run = await session.get(ExperimentRun, run_id)
            if not run:
                raise KeyError("Experiment run not found")
            return record(run)

    async def review(self):
        async with self.k.db.sessions() as session:
            control = await session.get(CognitiveControl, self.k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            pilots = (
                await session.scalars(
                    select(ExperimentRun)
                    .where(
                        ExperimentRun.phase == "pilot",
                        ExperimentRun.provider == "meta",
                        ExperimentRun.status == "completed",
                    )
                    .order_by(ExperimentRun.created_at.desc())
                )
            ).all()
            current = (
                json.loads((ROOT / "freeze-final.json").read_text())
                if (ROOT / "freeze-final.json").exists()
                else None
            )
            pilot = next(
                (
                    run
                    for run in pilots
                    if current and run.data["freeze_id"] == current["freeze_id"]
                ),
                None,
            )
            remaining = {
                prefix + unit: max(
                    0,
                    getattr(cfg, prefix + unit)
                    - control.spent.get(prefix + unit, 0)
                    - control.reserved.get(unit, 0),
                )
                for prefix in ["session_", "experiment_"]
                for unit in ["calls", "tokens"]
            }
            projection = None
            if (
                pilot
                and len(pilot.data["rows"]) == 4
                and all(
                    row.get("eligible")
                    and not any(arm.get("error") for arm in row["arms"].values())
                    for row in pilot.data["rows"]
                )
            ):
                summary = pilot.data["summary"]
                rate = summary["policies"]["selective"]["critic_invocation_rate"]
                projection = {
                    "tasks": 120,
                    "expected_unique_calls": 120 * (2 + rate),
                    "maximum_unique_calls": 360,
                    "expected_reported_tokens": summary["reported_unique_tokens"] / 4 * 120,
                    "expected_rate_card_usd": summary["estimated_unique_usd"] / 4 * 120,
                    "maximum_at_proposed_1500000_token_cap_usd": 6.375,
                    "estimate_note": (
                        "Pilot-scaled estimate, not invoice; task/model/cache variation"
                        " may change expenditure."
                    ),
                    "proposed_hard_limits": {
                        "max_calls": 360,
                        "max_tokens": 1500000,
                        "session_plan": [60, 60],
                    },
                    "current_budget_sufficient_for_maximum_calls": remaining["experiment_calls"]
                    >= 360
                    and cfg.session_calls >= 180,
                    "suggested_governor_configuration": cfg.model_dump()
                    | {
                        "session_calls": 180,
                        "session_tokens": 1000000,
                        "experiment_calls": 500,
                        "experiment_tokens": 2000000,
                    },
                    "budget_requirement": (
                        "Full run will stop at existing Governor ceilings; "
                        "authorize/configure sufficient experiment budget and planned "
                        "session boundaries before execution."
                    ),
                }
            return {
                "freeze": current,
                "pilot_run_id": pilot.id if pilot else None,
                "remaining_governor_budget": remaining,
                "projection": projection,
                "ready_for_owner_review": bool(pilot and projection),
                "full_run_executed": bool(
                    await session.scalar(
                        select(ExperimentRun.id).where(ExperimentRun.phase == "full")
                    )
                ),
                "authorization_required": True,
                "confirmed_provider_billing": None,
                "pricing": {
                    "source": "https://dev.meta.ai/docs/pricing-rate-limits",
                    "model": MODEL,
                    "usd_per_million": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
                    "estimate_only": True,
                },
            }
