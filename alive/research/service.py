"""LOOP-01: bounded, model-directed research over an approved local corpus.

The model chooses search/read/answer/abstain actions. The host executes them and an independent
verifier checks controlled answers. The loop reuses Cognition's Governor reservation and Pi/model
dispatch path; it does not add a second model gateway or provider client.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select

from alive.cognition import BudgetExhausted
from alive.cognitive_models import (
    CognitiveMessage,
    CognitiveObservation,
    Experience,
    Investigation,
    ModelInvocation,
)
from alive.models import Goal, uid
from alive.research import corpus
from alive.research.authority import ResearchClaim, source_for
from alive.research.contracts import (
    MAX_STEPS,
    ResearchAction,
    ResearchReference,
    Spec,
    action_catalog,
    role_contract,
)
from alive.research.verification import verify
from alive.workflows.context import digest, require

SOURCE = "research-owner"
SPEC = Spec()
OBSERVATION_PREFIX = "research-observation:"


def _fingerprint(consent_ref: str, request_key: str) -> str:
    return digest([consent_ref, request_key])


def _requester(current: dict) -> tuple[ResearchClaim, dict]:
    terms = current["terms"]
    research = terms.get("research")
    require(bool(research), "research_session_required")
    require(tuple(terms["paths"]) == tuple(research["paths"]), "research_paths_changed")
    claim = ResearchClaim(
        consent_ref=current["id"],
        goal_ref=terms["goal_ref"],
        principal=terms["principal"],
        paths=tuple(terms["paths"]),
    )
    return claim, research


async def _existing(kernel, fingerprint: str):
    async with kernel.db.sessions() as session:
        observation = await session.scalar(
            select(CognitiveObservation).where(
                CognitiveObservation.instance_id == kernel.instance_id,
                CognitiveObservation.fingerprint == OBSERVATION_PREFIX + fingerprint,
            )
        )
        if observation is None:
            return None
        return await session.scalar(
            select(Investigation).where(
                Investigation.instance_id == kernel.instance_id,
                Investigation.observation_id == observation.id,
            )
        )


def _clip(text: Any, limit: int) -> Any:
    if not isinstance(text, str):
        return text
    return text if len(text) <= limit else text[:limit] + "…"


def _bound(value: Any, *, text_limit: int = 700, depth: int = 0) -> Any:
    """Bound untrusted observation text before it enters the model situation."""
    if depth > 6:
        return "[depth-limit]"
    if isinstance(value, str):
        return _clip(value, text_limit)
    if isinstance(value, list):
        return [_bound(item, text_limit=text_limit, depth=depth + 1) for item in value[:8]]
    if isinstance(value, dict):
        return {
            str(key): _bound(item, text_limit=text_limit, depth=depth + 1)
            for key, item in list(value.items())[:24]
        }
    return value


STOPWORDS = frozenset(
    {
        "answer",
        "does",
        "exactly",
        "from",
        "have",
        "only",
        "that",
        "the",
        "this",
        "time",
        "what",
        "with",
    }
)


def _terms(text: str) -> set[str]:
    return {
        word.lower().strip(".,:;?!\"'()[]{}")
        for word in str(text).split()
        if len(word) > 3 and word.lower().strip(".,:;?!\"'()[]{}") not in STOPWORDS
    }


async def _similar_episode(kernel, source_ref: str, question: str):
    """Retrieve one relevant, outcome-labelled prior decision trajectory."""
    terms = _terms(question)
    if not terms:
        return None
    async with kernel.db.sessions() as session:
        rows = (
            await session.scalars(
                select(Experience)
                .where(Experience.instance_id == kernel.instance_id)
                .order_by(Experience.created_at.desc())
                .limit(20)
            )
        ).all()
    best = None
    best_score = 0
    for row in rows:
        data = row.data or {}
        snapshot = data.get("state_snapshot") or {}
        if snapshot.get("source_ref") != source_ref:
            continue
        score = len(terms & _terms(snapshot.get("question", "")))
        if score <= best_score:
            continue
        trace = snapshot.get("decision_trace") or []
        verification = snapshot.get("verification") or {}
        best_score = score
        best = {
            "episode_id": row.id,
            "question": _clip(snapshot.get("question"), 400),
            "first_action": (
                _clip(trace[0].get("action", {}).get("action"), 40) if trace else None
            ),
            "decision_trace": _bound(trace[-3:], text_limit=400),
            "verification": verification,
            "verified_success": verification.get("status") == "VERIFIED_SUCCESS",
            "outcome": data.get("outcome_state"),
        }
    return best


async def _create(kernel, cognition, claim, research, request, source):
    fingerprint = _fingerprint(claim.consent_ref, request.idempotency_key)
    async with kernel.lock:
        existing = await _existing(kernel, fingerprint)
        if existing is not None:
            snapshot = existing.snapshot or {}
            require(
                snapshot.get("question") == request.goal
                and list(snapshot.get("paths", [])) == list(claim.paths)
                and snapshot.get("reference_id")
                == (request.reference.reference_id if request.reference else None),
                "research_retry_conflict",
            )
            return existing, False
        async with kernel.db.sessions.begin() as session:
            goal = await session.get(Goal, claim.goal_ref)
            require(
                goal is not None
                and goal.instance_id == kernel.instance_id
                and goal.status in ("active", "accepted"),
                "accepted_owner_goal_required",
            )
            observation_id = uid()
            event = kernel.add_event(
                session,
                "research.question",
                {
                    "question": request.goal,
                    "source_ref": source.source_ref,
                    "source_sha256": source.content_sha256,
                    "consent_ref": claim.consent_ref,
                    "request_fingerprint": fingerprint,
                },
                source=SOURCE,
                correlation=observation_id,
            )
            await session.flush()
            observation = CognitiveObservation(
                id=observation_id,
                instance_id=kernel.instance_id,
                source_event_id=str(event.event_id),
                fingerprint=OBSERVATION_PREFIX + fingerprint,
                content=request.goal,
                provenance={
                    "url": "internal:research",
                    "source": "owner-admission",
                    "source_type": "owner_question",
                    "source_ref": source.source_ref,
                    "claims": [],
                },
                attention={"score": 1.0, "policy": "research-loop/v1"},
                status="TRIAGED",
            )
            session.add(observation)
            await session.flush()
            snapshot = {
                "question": request.goal,
                "paths": list(claim.paths),
                "reference_id": (request.reference.reference_id if request.reference else None),
                "source_ref": source.source_ref,
                "source_sha256": source.content_sha256,
                "decision_trace": [],
                "evidence": [],
                "verification": None,
                "previous_episode": None,
                "reuse": None,
            }
            row = Investigation(
                id=uid(),
                instance_id=kernel.instance_id,
                observation_id=observation.id,
                goal_id=goal.id,
                state="SCHEDULED",
                snapshot=snapshot,
                history=[],
                budget={
                    "calls": int(research["max_model_calls"]),
                    "tokens": int(research["max_tokens"]),
                    "tools": MAX_STEPS,
                },
                usage={"calls": 0, "tokens": 0, "tools": 0, "latency_ms": 0},
                evaluation={},
            )
            session.add(row)
            await session.flush()
            cognition._transition(session, row, "INVESTIGATING")
            await session.flush()
            return row, True


def _full_corpus(source_content: dict, *, budget: int = 12000) -> list[dict]:
    """Qualification-only one-call baseline context; never used by the product loop."""
    remaining = budget
    documents = []
    for document in corpus.documents(source_content):
        text = document.content[: min(remaining, 4000)]
        if not text:
            break
        documents.append({"document_id": document.document_id, "text": text})
        remaining -= len(text)
        if remaining <= 0:
            break
    return documents


def _situation(
    *,
    question: str,
    source,
    evidence: list[dict],
    trace: list[dict],
    last_observation: dict | None,
    previous: dict | None,
    budget: dict,
    usage: dict,
    baseline: bool = False,
) -> dict:
    value = {
        "objective": question,
        "success_criteria": (
            "Answer only from approved corpus evidence with verifiable citations, or abstain."
        ),
        "source": {
            "label": source.label,
            "source_ref": source.source_ref,
            "content_sha256": source.content_sha256,
            "scope_sha256": source.scope_sha256,
        },
        "corpus": corpus.catalog(source.content)[:40],
        "evidence": [
            {
                "document_id": item["document_id"],
                "quote": _clip(str(item["quote"]), 500),
                "line_start": item.get("line_start"),
                "line_end": item.get("line_end"),
            }
            for item in evidence[-6:]
        ],
        "last_observation": _bound(last_observation),
        "previous_actions": [
            {
                "step": item["step"],
                "action": item["action"]["action"],
                "reason": _clip(item["action"].get("reason", ""), 300),
            }
            for item in trace[-3:]
        ],
        "previous_episode": previous,
        "open_questions": [] if evidence else ["Gather evidence before answering."],
        "actions": action_catalog(),
        "budget": {
            "max_calls": budget["calls"],
            "max_tokens": budget["tokens"],
            "max_steps": 1 if baseline else MAX_STEPS,
            "calls_used": usage.get("calls", 0),
            "tokens_used": usage.get("tokens", 0),
        },
        "policy": {
            "role_contract": role_contract(),
            "max_steps": 1 if baseline else MAX_STEPS,
        },
    }
    if baseline:
        value["baseline"] = (
            "Qualification one-call baseline: every approved document is supplied in "
            "corpus_full. The model gets exactly one dispatch and no tool round-trip."
        )
        value["corpus_full"] = _full_corpus(source.content)
    return value


def _snapshot(
    *,
    request,
    claim,
    source,
    trace: list[dict],
    evidence: list[dict],
    verification: dict | None,
    previous: dict | None,
    reuse: dict | None,
    baseline: bool = False,
) -> dict:
    return {
        "question": request.goal,
        "paths": list(claim.paths),
        "baseline": baseline,
        "reference_id": request.reference.reference_id if request.reference else None,
        "source_ref": source.source_ref,
        "source_sha256": source.content_sha256,
        "decision_trace": trace,
        "evidence": evidence[-20:],
        "verification": verification,
        "previous_episode": previous,
        "reuse": reuse,
    }


def _conclusion(verification: dict | None) -> str:
    status = verification.get("status") if verification else None
    return {
        "VERIFIED_SUCCESS": "VERIFIED",
        "VERIFIED_FAILURE": "CONTRADICTED",
        "ABSTAINED": "ABSTAINED",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "ERROR": "ERROR",
    }.get(status, "INCONCLUSIVE")


def _reuse(previous: dict | None, trace: list[dict]) -> dict:
    first = trace[0]["action"]["action"] if trace else None
    previous_first = previous.get("first_action") if previous else None
    return {
        "supplied": previous is not None,
        "previous_episode_id": previous.get("episode_id") if previous else None,
        "previous_outcome_status": (
            (previous.get("verification") or {}).get("status") if previous else None
        ),
        "previous_first_action": previous_first,
        "current_first_action": first,
        "first_action_changed": bool(previous) and previous_first != first,
    }


async def _persist(kernel, row_id: str, snapshot: dict) -> None:
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await session.get(Investigation, row_id)
        if row is not None and row.state not in ("COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"):
            row.snapshot = snapshot


async def run(
    app,
    request,
    current: dict,
    *,
    reference: ResearchReference | None = None,
    baseline: bool = False,
) -> dict:
    kernel, cognition = app.state.kernel, app.state.cognition
    claim, research = _requester(current)
    source = await source_for(claim, kernel)
    row, created = await _create(kernel, cognition, claim, research, request, source)
    if not created:
        return await view(kernel, row.id)
    previous = await _similar_episode(kernel, source.source_ref, request.goal)
    evidence: list[dict] = []
    trace: list[dict] = []
    last_observation: dict | None = None
    action: ResearchAction | None = None
    verification: dict | None = None
    error = None
    cancelled = False
    terminal = False
    try:
        for step in range(1, (1 if baseline else MAX_STEPS) + 1):
            async with kernel.db.sessions() as session:
                current_row = await session.get(Investigation, row.id)
                situation = _situation(
                    question=request.goal,
                    source=source,
                    evidence=evidence,
                    trace=trace,
                    last_observation=last_observation,
                    previous=previous,
                    budget=current_row.budget,
                    usage=current_row.usage,
                    baseline=baseline,
                )
            try:
                action = await cognition.call_role(
                    row.id,
                    "research_decider",
                    situation,
                    spec=SPEC,
                    research_claim=claim,
                    output_ceiling=min(1536, int(research["max_output_tokens"])),
                )
            except asyncio.CancelledError:
                cancelled = True
                raise
            except BudgetExhausted as exc:
                error = str(exc) or type(exc).__name__
                verification = {
                    "status": "INCONCLUSIVE",
                    "basis": "budget_exhausted",
                    "notes": [error],
                }
                break
            except Exception as exc:  # noqa: BLE001 - a failed decision is a visible outcome
                error = type(exc).__name__
                break
            step_record = {
                "step": step,
                "action": action.model_dump(mode="json"),
                "observation": None,
            }
            if action.action in ("answer", "abstain"):
                verification = verify(
                    action, source_content=source.content, reference=reference
                ).model_dump(mode="json")
                step_record["observation"] = {"verification": verification}
                trace.append(step_record)
                terminal = True
                await _persist(
                    kernel,
                    row.id,
                    _snapshot(
                        request=request,
                        claim=claim,
                        source=source,
                        trace=trace,
                        evidence=evidence,
                        verification=verification,
                        previous=previous,
                        reuse=_reuse(previous, trace),
                        baseline=baseline,
                    ),
                )
                break
            if baseline:
                step_record["observation"] = {
                    "baseline": "tool not executed; the one-call baseline has no round-trip"
                }
                trace.append(step_record)
                verification = {
                    "status": "INCONCLUSIVE",
                    "basis": "baseline_did_not_answer",
                    "notes": ["The baseline model chose a tool action in its only call."],
                }
                break
            try:
                await cognition.charge_tool(row.id)
                if action.action == "search":
                    result = corpus.search(source.content, action.query)
                    evidence.extend(
                        {
                            "document_id": item["document_id"],
                            "quote": item["snippet"],
                            "line_start": item["line_start"],
                            "line_end": item["line_end"],
                        }
                        for item in result
                    )
                    observation = {
                        "action": "search",
                        "query": action.query,
                        "results": result,
                    }
                else:
                    result = corpus.read(source.content, action.document_id, action.section)
                    evidence.append(
                        {
                            "document_id": result["document_id"],
                            "quote": result["text"][:1000],
                            "line_start": result["line_start"],
                            "line_end": result["line_end"],
                        }
                    )
                    observation = {"action": "read", "document": result}
                step_record["observation"] = observation
                last_observation = observation
                trace.append(step_record)
                await cognition.message(row.id, "investigator", "evidence", observation)
                await _persist(
                    kernel,
                    row.id,
                    _snapshot(
                        request=request,
                        claim=claim,
                        source=source,
                        trace=trace,
                        evidence=evidence,
                        verification=None,
                        previous=previous,
                        reuse=_reuse(previous, trace),
                        baseline=baseline,
                    ),
                )
            except Exception as exc:  # noqa: BLE001 - tool failure is visible
                error = type(exc).__name__
                step_record["observation"] = {"error": error}
                trace.append(step_record)
                break
    finally:
        async with kernel.lock, kernel.db.sessions.begin() as session:
            run_row = await session.get(Investigation, row.id)
            if run_row.state not in ("COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"):
                if cancelled:
                    target = "CANCELLED"
                    verification = verification or {
                        "status": "ERROR",
                        "basis": "cancelled",
                    }
                elif error and verification is None:
                    verification = {
                        "status": "ERROR",
                        "basis": "decision_or_tool_failure",
                        "notes": [error],
                    }
                    target = "FAILED"
                elif verification is not None and verification.get("status") == "ABSTAINED":
                    target = "ABSTAINED"
                elif terminal and action is not None and action.action == "answer":
                    target = "COMPLETED"
                elif verification is not None and verification.get("status") == "INCONCLUSIVE":
                    target = "ABSTAINED"
                else:
                    verification = {
                        "status": "INCONCLUSIVE",
                        "basis": "step_budget_exhausted",
                        "notes": ["No terminal answer or abstention before the step ceiling."],
                    }
                    target = "ABSTAINED"
                snapshot = _snapshot(
                    request=request,
                    claim=claim,
                    source=source,
                    trace=trace,
                    evidence=evidence,
                    verification=verification,
                    previous=previous,
                    reuse=_reuse(previous, trace),
                    baseline=baseline,
                )
                run_row.snapshot = snapshot
                run_row.evaluation = {
                    "conclusion_status": _conclusion(verification),
                    "verification": verification,
                    "error": error,
                }
                cognition._transition(session, run_row, "EVALUATING")
                if target == "COMPLETED":
                    cognition._transition(session, run_row, "EXECUTING")
                action_record = (
                    {"proposal": action.model_dump(mode="json"), "status": "executed"}
                    if action is not None
                    else None
                )
                await cognition.finish_in_session(
                    session,
                    run_row.id,
                    target,
                    {
                        "effect": "answer" if target == "COMPLETED" else "none",
                        "reason": (
                            "research_answer_retained"
                            if target == "COMPLETED"
                            else "research_abstained"
                            if target == "ABSTAINED"
                            else "research_failed"
                            if target == "FAILED"
                            else "research_cancelled"
                        ),
                        "verification": verification,
                    },
                    error=error,
                    action=action_record,
                )
    return await view(kernel, row.id)


async def view(kernel, investigation_id: str) -> dict:
    async with kernel.db.sessions() as session:
        row = await session.get(Investigation, investigation_id)
        require(
            row is not None and row.instance_id == kernel.instance_id, "research_task_not_found"
        )
        experience = await session.scalar(
            select(Experience).where(Experience.investigation_id == row.id)
        )
        calls = (
            await session.scalars(
                select(ModelInvocation)
                .where(ModelInvocation.investigation_id == row.id)
                .order_by(ModelInvocation.created_at)
            )
        ).all()
        messages = (
            await session.scalars(
                select(CognitiveMessage)
                .where(CognitiveMessage.investigation_id == row.id)
                .order_by(CognitiveMessage.created_at)
            )
        ).all()
        snapshot = row.snapshot or {}
        data = experience.data if experience else {}
        final_action = None
        for item in reversed(snapshot.get("decision_trace", [])):
            if item.get("action", {}).get("action") in ("answer", "abstain"):
                final_action = item["action"]
                break
        return {
            "task_id": row.id,
            "episode_id": experience.id if experience else None,
            "question": snapshot.get("question"),
            "state": row.state,
            "source_ref": snapshot.get("source_ref"),
            "status": (
                "LIVE MODEL" if any(call.provider == "meta" for call in calls) else "NO MODEL CALL"
            ),
            "model_calls": len(calls),
            "models": [
                {
                    "role": call.role,
                    "provider": call.provider,
                    "model": call.model,
                    "status": call.status,
                }
                for call in calls
            ],
            "usage": [
                {"id": call.id, "usage": call.usage, "latency_ms": call.latency_ms}
                for call in calls
            ],
            "actions": snapshot.get("decision_trace", []),
            "evidence": snapshot.get("evidence", []),
            "answer": final_action,
            "verification": snapshot.get("verification"),
            "conclusion_status": (row.evaluation or {}).get("conclusion_status"),
            "outcome": data.get("outcome_state"),
            "previous_episode": snapshot.get("previous_episode"),
            "reuse": snapshot.get("reuse"),
            "messages": [
                {
                    "sender": message.sender,
                    "type": message.message_type,
                    "content": message.content,
                    "at": message.created_at.isoformat(),
                }
                for message in messages
            ],
        }


def reference_from_dict(payload: dict[str, Any]) -> ResearchReference:
    return ResearchReference.model_validate(payload)


__all__ = ["run", "view", "reference_from_dict"]
