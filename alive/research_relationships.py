"""Owner-authorised outbound relationship analysis over retained research memory.

Local retrieval and local lexical connections remain separate from this module. Nothing in
this service transmits content unless the owner previews an exact payload, authorises that
payload, and the server revalidates every bound hash before dispatch.
"""

import asyncio
import hashlib
import json
import re
import time
from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from alive.cognitive_models import CognitiveControl
from alive.cognitive_schema import CognitiveConfiguration
from alive.experiment.metrics import price
from alive.experiment_budget import charged_micro_usd, check_spend, worst_micro_usd
from alive.models import now, record
from alive.providers import MetaProvider
from alive.research_memory import (
    CONNECTION_KIND,
    _overlap_spans,
    _tokens,
)

CONSENT_KIND = "research_outbound_consent"
ATTEMPT_KIND = "research_relationship_analysis"
ANALYSIS_VERSION = "alive14-relationship-v1"
VALIDATOR_VERSION = "alive14r1-evidence-v1"
MIN_QUOTE_CHARS = 16
MIN_QUOTE_TERMS = 2
MIN_SHARED_TERMS = 1
MAX_ABSTENTION_CONFIDENCE = 0.2
MAX_CURRENT_CHARS = 3000
MAX_HISTORICAL_CHARS = 2000
MAX_PAYLOAD_CHARS = 5000
CONSENT_TTL_MINUTES = 10
LOCAL_STUB_MODEL = "deterministic-local-stub-v1"
GENERIC_EVIDENCE_TERMS = {
    "about",
    "approach",
    "content",
    "context",
    "data",
    "information",
    "method",
    "methods",
    "note",
    "notes",
    "page",
    "pages",
    "process",
    "record",
    "records",
    "result",
    "results",
    "source",
    "sources",
    "system",
    "systems",
    "text",
    "value",
    "values",
    "work",
}
ASSERTIVE_EVIDENCE_LANGUAGE = re.compile(
    r"\b(support(?:s|ed)?|confirm(?:s|ed)?|prove(?:s|n)?|demonstrat(?:e|es|ed)|"
    r"contradict(?:s|ed)?|clearly|definitely|certainly|therefore)\b",
    re.IGNORECASE,
)

RELATIONSHIP_INSTRUCTIONS = (
    "You are ALIVE's evidence-grounded research relationship assistant. The owner has "
    "explicitly authorised this bounded payload for external analysis. Use only the current "
    "and historical excerpts supplied. Propose a cautious relationship hypothesis or abstain. "
    "Return exact quotations copied from each supplied excerpt; never invent or paraphrase a "
    "quotation. Shared words alone do not establish agreement, contradiction or support. State "
    "limitations and use insufficient_evidence when the excerpts do not support a hypothesis."
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationshipOutput(Strict):
    relationship: Literal[
        "possible_conceptual_connection",
        "possible_methodological_difference",
        "possible_disagreement",
        "insufficient_evidence",
    ]
    explanation: str = Field(min_length=1, max_length=1200)
    current_quote: str | None = Field(default=None, max_length=300)
    historical_quote: str | None = Field(default=None, max_length=300)
    limitations: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def validate_relationship_output(output, payload):
    """Validate quote provenance and bounded evidence, not semantic truth."""
    goal_terms = _tokens(payload.get("goal_instruction", ""))
    current = output.current_quote
    historical = output.historical_quote
    current_exact = bool(current and current in payload["current_excerpt"])
    historical_exact = bool(historical and historical in payload["historical_excerpt"])

    def meaningful(quote):
        terms = _tokens(quote or "") - goal_terms
        return sorted(term for term in terms if term not in GENERIC_EVIDENCE_TERMS)

    current_terms = meaningful(current)
    historical_terms = meaningful(historical)
    shared_terms = sorted(set(current_terms) & set(historical_terms))
    reasons = []
    if current is not None and len(current) < MIN_QUOTE_CHARS:
        reasons.append("current_quote_too_short")
    if historical is not None and len(historical) < MIN_QUOTE_CHARS:
        reasons.append("historical_quote_too_short")
    if current is not None and not current_exact:
        reasons.append("current_quote_not_exact")
    if historical is not None and not historical_exact:
        reasons.append("historical_quote_not_exact")
    if output.relationship == "insufficient_evidence":
        if output.confidence > MAX_ABSTENTION_CONFIDENCE:
            reasons.append("abstention_confidence_too_high")
        if ASSERTIVE_EVIDENCE_LANGUAGE.search(output.explanation + " " + output.limitations):
            reasons.append("abstention_contains_assertive_claim")
    else:
        if current is None or historical is None:
            reasons.append("evidence_quotes_required")
        if len(current_terms) < MIN_QUOTE_TERMS:
            reasons.append("current_quote_lacks_meaningful_terms")
        if len(historical_terms) < MIN_QUOTE_TERMS:
            reasons.append("historical_quote_lacks_meaningful_terms")
        if len(shared_terms) < MIN_SHARED_TERMS:
            reasons.append("quotes_share_no_meaningful_terms")
        if current is not None and current == historical:
            reasons.append("identical_evidence_span")
    quote_provenance = bool(current_exact and historical_exact)
    return {
        "validator_version": VALIDATOR_VERSION,
        "valid": not reasons,
        "reasons": reasons,
        "quote_provenance": quote_provenance,
        "semantic_verification": False,
        "explanation_status": "unverified_model_interpretation",
        "current_quote_exact": current_exact,
        "historical_quote_exact": historical_exact,
        "current_quote_length": len(current or ""),
        "historical_quote_length": len(historical or ""),
        "current_meaningful_terms": current_terms,
        "historical_meaningful_terms": historical_terms,
        "shared_meaningful_terms": shared_terms,
        "same_evidence_span": bool(current and current == historical),
    }


class ResearchRelationships:
    def __init__(self, research, experiments, settings):
        self.research = research
        self.web = research.web
        self.k = research.k
        self.experiments = experiments
        self.settings = settings

    def _provider_identity(self, provider):
        if provider == "local_stub":
            return {
                "id": "local_stub",
                "model": LOCAL_STUB_MODEL,
                "external": False,
            }
        if provider == "local_stub_invalid":
            if not self.settings.alive_relationship_allow_test_providers:
                raise PermissionError("Invalid-output test provider is not enabled")
            return {
                "id": "local_stub_invalid",
                "model": "deterministic-local-stub-invalid-v1",
                "external": False,
            }
        if provider == "meta":
            if not self.settings.alive_research_meta_enabled:
                raise PermissionError(
                    "External Meta relationship analysis is not authorised on this runtime"
                )
            return {
                "id": "meta",
                "model": self.settings.alive_meta_model,
                "external": True,
            }
        raise ValueError("Unknown relationship provider")

    def _reserve(self, payload, model):
        return (
            len(
                json.dumps(
                    {
                        "instructions": RELATIONSHIP_INSTRUCTIONS,
                        "input": payload,
                        "schema": RelationshipOutput.model_json_schema(),
                    },
                    ensure_ascii=False,
                ).encode()
            )
            + 1024
            + self.settings.alive_meta_max_output
        )

    def _request(self, payload):
        return {
            "instructions": RELATIONSHIP_INSTRUCTIONS,
            "input": payload,
            "schema": RelationshipOutput.model_json_schema(),
        }

    def _request_sha256(self, payload):
        return _digest(self._request(payload))

    async def _allowance(self, session):
        control = await session.get(CognitiveControl, self.k.instance_id)
        cfg = CognitiveConfiguration.model_validate(control.configuration)
        ledger = await self._ledger(session)
        cap = self.settings.alive_relationship_micro_usd_limit
        cap = cap if cap is not None else 100000
        return {
            "session_calls_remaining": max(
                0,
                cfg.session_calls
                - control.spent.get("session_calls", 0)
                - control.reserved.get("calls", 0),
            ),
            "session_tokens_remaining": max(
                0,
                cfg.session_tokens
                - control.spent.get("session_tokens", 0)
                - control.reserved.get("tokens", 0),
            ),
            "experiment_calls_remaining": max(
                0,
                cfg.experiment_calls
                - control.spent.get("experiment_calls", 0)
                - control.reserved.get("calls", 0),
            ),
            "experiment_tokens_remaining": max(
                0,
                cfg.experiment_tokens
                - control.spent.get("experiment_tokens", 0)
                - control.reserved.get("tokens", 0),
            ),
            "micro_usd_remaining": max(0, cap - charged_micro_usd(ledger)),
            "micro_usd_ceiling": cap,
        }

    def _payload(self, snapshot, memory, goal, provider, model):
        current_excerpt = snapshot.data["text"][:MAX_CURRENT_CHARS]
        historical_excerpt = memory.data["excerpt"][:MAX_HISTORICAL_CHARS]
        if len(current_excerpt) + len(historical_excerpt) > MAX_PAYLOAD_CHARS:
            raise ValueError("Selected excerpts exceed the outbound payload limit")
        return {
            "current_snapshot_id": snapshot.id,
            "current_url": snapshot.data["url"],
            "current_sha256": snapshot.data["sha256"],
            "current_excerpt": current_excerpt,
            "historical_memory_id": memory.id,
            "historical_url": memory.data["url"],
            "historical_sha256": memory.data["sha256"],
            "historical_excerpt": historical_excerpt,
            "goal_id": goal.id,
            "goal_instruction": goal.data["instruction"],
            "provider": provider,
            "model": model,
        }

    async def _validate_sources(self, session, consent):
        payload = consent.data["payload"]
        snapshot = await self.web.get(session, payload["current_snapshot_id"], "snapshot")
        await self.web.valid_grant(session, snapshot.parent_id)
        memory = await self.research._research_row(session, payload["historical_memory_id"])
        goal = await self.web.get(session, payload["goal_id"], "goal")
        if memory.status != "active":
            raise ValueError("Historical research memory is withdrawn")
        if memory.data["goal_id"] != goal.id or snapshot.data["goal_id"] != goal.id:
            raise PermissionError("Consent sources do not share the authorised goal")
        if snapshot.data["url"] == memory.data["url"]:
            raise ValueError("Outbound analysis requires different source pages")
        if (
            snapshot.data["sha256"] != payload["current_sha256"]
            or snapshot.data["text"][:MAX_CURRENT_CHARS] != payload["current_excerpt"]
        ):
            raise PermissionError("Current source changed; preview the outbound payload again")
        if (
            memory.data["sha256"] != payload["historical_sha256"]
            or memory.data["excerpt"][:MAX_HISTORICAL_CHARS] != payload["historical_excerpt"]
        ):
            raise PermissionError("Historical source changed; preview the outbound payload again")
        if _digest(payload) != consent.data["payload_sha256"]:
            raise PermissionError("Outbound payload hash changed")
        return snapshot, memory, goal

    async def preview(self, snapshot_id, research_id, provider="local_stub"):
        identity = self._provider_identity(provider)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            snapshot = await self.web.get(session, snapshot_id, "snapshot")
            # A live reviewed page grant is required even though this operation is local.
            await self.web.valid_grant(session, snapshot.parent_id)
            memory = await self.research._research_row(session, research_id)
            goal = await self.web.get(session, snapshot.data["goal_id"], "goal")
            if memory.status != "active":
                raise ValueError("Research memory is withdrawn")
            if memory.data["goal_id"] != goal.id:
                raise ValueError("Research memory belongs to a different goal")
            if memory.data["url"] == snapshot.data["url"]:
                raise ValueError("Outbound analysis requires different source pages")
            payload = self._payload(snapshot, memory, goal, provider, identity["model"])
            reserve = self._reserve(payload, identity["model"])
            request = self._request(payload)
            request_sha256 = _digest(request)
            allowance = await self._allowance(session)
            row = self.web.add(
                session,
                CONSENT_KIND,
                {
                    "payload": payload,
                    "payload_sha256": _digest(payload),
                    "request_sha256": request_sha256,
                    "provider": identity,
                    "goal_id": goal.id,
                    "current_snapshot_id": snapshot.id,
                    "grant_id": snapshot.parent_id,
                    "historical_memory_id": memory.id,
                    "reserved_tokens": reserve,
                    "estimated_max_micro_usd": worst_micro_usd(reserve),
                    "limits": {
                        "max_current_chars": MAX_CURRENT_CHARS,
                        "max_historical_chars": MAX_HISTORICAL_CHARS,
                        "max_payload_chars": MAX_PAYLOAD_CHARS,
                    },
                    "created_at": now().isoformat(),
                    "expires_at": (now() + timedelta(minutes=CONSENT_TTL_MINUTES)).isoformat(),
                    "authorized_at": None,
                    "consumed_at": None,
                    "external": identity["external"],
                },
                snapshot.id,
                "pending",
            )
            await session.flush()
            return record(row) | {
                "payload_sha256": row.data["payload_sha256"],
                "preview": payload,
                "provider": identity,
                "external": identity["external"],
                "goal": {"id": goal.id, "instruction": goal.data["instruction"]},
                "current_source": {
                    "url": snapshot.data["url"],
                    "sha256": snapshot.data["sha256"],
                    "excerpt": payload["current_excerpt"],
                },
                "historical_source": {
                    "url": memory.data["url"],
                    "sha256": memory.data["sha256"],
                    "excerpt": payload["historical_excerpt"],
                },
                "estimated_max_tokens": reserve,
                "estimated_max_micro_usd": worst_micro_usd(reserve),
                "single_call_reservation": reserve,
                "remaining_allowance": allowance,
                "request": request,
                "request_sha256": request_sha256,
                "provider_operation": ("external_meta" if identity["external"] else "local_test"),
                "payload_immutable": True,
                "requires_owner_authorisation": True,
            }

    async def authorize(self, consent_id, payload_sha256):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            consent = await self.web.get(session, consent_id, CONSENT_KIND)
            if consent.status != "pending":
                raise ValueError("Only a pending consent can be authorised")
            if consent.data["expires_at"] < now().isoformat():
                consent.status = "expired"
                raise PermissionError("Outbound consent expired; preview the payload again")
            if consent.data["payload_sha256"] != payload_sha256:
                raise PermissionError("The displayed payload changed; preview it again")
            await self._validate_sources(session, consent)
            consent.status = "authorized"
            consent.data = consent.data | {"authorized_at": now().isoformat()}
            self.k.add_event(
                session,
                "research.outbound_authorized",
                {
                    "consent_id": consent.id,
                    "payload_sha256": consent.data["payload_sha256"],
                    "provider": consent.data["provider"]["id"],
                },
            )
            return record(consent)

    async def revoke(self, consent_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            consent = await self.web.get(session, consent_id, CONSENT_KIND)
            if consent.status == "consumed":
                raise ValueError("A consumed consent cannot be revoked")
            consent.status = "revoked"
            consent.data = consent.data | {"revoked_at": now().isoformat()}
            return record(consent)

    async def _ledger(self, session, exclude_attempt_id=None):
        rows = await self.web.rows(session, ATTEMPT_KIND)
        return [
            {
                "status": row.status,
                "reserved_tokens": row.data.get("reserved_tokens", 0),
                "usage": row.data.get("usage"),
            }
            for row in rows
            if row.id != exclude_attempt_id
        ]

    async def _existing_connection(self, session, consent):
        payload = consent.data["payload"]
        provider = consent.data["provider"]
        for row in await self.web.rows(session, CONNECTION_KIND):
            data = row.data
            if (
                data.get("analysis_version") == ANALYSIS_VERSION
                and data.get("validator_version") == VALIDATOR_VERSION
                and data.get("current_snapshot_id") == payload["current_snapshot_id"]
                and data.get("historical_memory_id") == payload["historical_memory_id"]
                and data.get("current_sha256") == payload["current_sha256"]
                and data.get("historical_sha256") == payload["historical_sha256"]
                and data.get("payload_sha256") == consent.data["payload_sha256"]
                and data.get("request_sha256") == consent.data["request_sha256"]
                and data.get("provider") == provider
                and data.get("model") == provider["model"]
                and row.status in ("candidate", "insufficient_evidence")
            ):
                return row
        return None

    async def analyze(self, consent_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            consent = await self.web.get(session, consent_id, CONSENT_KIND)
            if consent.status != "authorized":
                raise ValueError("Owner authorisation is required before outbound analysis")
            if consent.data["expires_at"] < now().isoformat():
                consent.status = "expired"
                raise PermissionError("Outbound consent expired; preview the payload again")
            snapshot, memory, goal = await self._validate_sources(session, consent)
            existing = await self._existing_connection(session, consent)
            if existing:
                consent.status = "cached"
                consent.data = consent.data | {
                    "cached_at": now().isoformat(),
                    "reused_connection_id": existing.id,
                }
                self.k.add_event(
                    session,
                    "research.relationship_cached",
                    {
                        "consent_id": consent.id,
                        "connection_id": existing.id,
                        "payload_sha256": consent.data["payload_sha256"],
                        "provider": consent.data["provider"]["id"],
                    },
                )
                return record(existing) | {
                    "idempotent": True,
                    "reused": True,
                    "cached": True,
                }
            if memory.id in self.research.outbound_inflight:
                raise ValueError("An outbound analysis for this memory is already in progress")
            control = await session.get(CognitiveControl, self.k.instance_id)
            cfg = CognitiveConfiguration.model_validate(control.configuration)
            if control.mode == "running" or control.reserved.get("calls", 0):
                raise ValueError("Pause autonomy and resolve reservations first")
            reserve = consent.data["reserved_tokens"]
            if reserve > min(cfg.request_tokens, cfg.investigation_tokens):
                raise ValueError("Governor request limit exhausted")
            for prefix in ("session_", "experiment_"):
                if control.spent.get(prefix + "calls", 0) + 1 > getattr(
                    cfg, prefix + "calls"
                ) or control.spent.get(prefix + "tokens", 0) + reserve > getattr(
                    cfg, prefix + "tokens"
                ):
                    raise ValueError("Governor cumulative limit exhausted")
            capped = self.settings.alive_relationship_micro_usd_limit
            check_spend(
                await self._ledger(session),
                reserve,
                cap=capped if capped is not None else 100000,
            )
            consent.status = "consumed"
            consent.data = consent.data | {"consumed_at": now().isoformat()}
            self.research.outbound_inflight.add(memory.id)
            attempt = self.web.add(
                session,
                ATTEMPT_KIND,
                {
                    "consent_id": consent.id,
                    "analysis_version": ANALYSIS_VERSION,
                    "provider": consent.data["provider"],
                    "payload_sha256": consent.data["payload_sha256"],
                    "request_sha256": consent.data["request_sha256"],
                    "current_snapshot_id": snapshot.id,
                    "historical_memory_id": memory.id,
                    "current_sha256": snapshot.data["sha256"],
                    "historical_sha256": memory.data["sha256"],
                    "reserved_tokens": reserve,
                    "started_at": now().isoformat(),
                },
                snapshot.id,
                "reserved",
            )
            control.reserved = control.reserved | {
                "calls": control.reserved.get("calls", 0) + 1,
                "tokens": control.reserved.get("tokens", 0) + reserve,
            }
            await session.flush()
            attempt_id = attempt.id
            payload = consent.data["payload"]
            provider = consent.data["provider"]
        usage, raw, error, output = None, None, None, None
        started = time.monotonic()
        try:
            async with asyncio.timeout(cfg.wall_seconds):
                async with self.k.lock, self.k.db.sessions() as guard_session:
                    if consent.data.get("request_sha256") != self._request_sha256(payload):
                        raise PermissionError(
                            "Outbound request representation changed; preview and authorise again"
                        )
                    current_provider = self._provider_identity(provider["id"])
                    if current_provider != provider:
                        raise PermissionError(
                            "Provider or pinned model changed after authorisation; "
                            "preview and authorise again"
                        )
                    guard_control = await guard_session.get(CognitiveControl, self.k.instance_id)
                    if (
                        guard_control.mode == "running"
                        or guard_control.reserved.get("calls", 0) != 1
                        or guard_control.reserved.get("tokens", 0) != reserve
                    ):
                        raise PermissionError(
                            "Governor reservation changed before provider dispatch"
                        )
                    capped = self.settings.alive_relationship_micro_usd_limit
                    check_spend(
                        await self._ledger(guard_session, exclude_attempt_id=attempt_id),
                        reserve,
                        cap=capped if capped is not None else 100000,
                    )
                if provider["id"] == "local_stub":
                    output = self._local_stub(payload)
                    raw = output.model_dump_json()
                    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                elif provider["id"] == "local_stub_invalid":
                    output = self._local_stub_invalid(payload)
                    raw = output.model_dump_json()
                    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                else:
                    result = await MetaProvider(self.settings).structured(
                        RELATIONSHIP_INSTRUCTIONS,
                        payload,
                        RelationshipOutput.model_json_schema(),
                        model=provider["model"],
                        max_output=min(cfg.output_tokens, self.settings.alive_meta_max_output),
                        correlation=attempt_id,
                    )
                    usage = result.usage
                    raw = result.text
                    output = RelationshipOutput.model_validate_json(raw)
                    validation = self._quote_validation(output, payload)
                    if not validation["valid"]:
                        raise ValueError(
                            "Relationship output failed evidence validation: "
                            + ", ".join(validation["reasons"])
                        )
        except BaseException as exc:
            usage = getattr(exc, "usage", None) or usage
            error = type(exc).__name__
        charged = usage.get("total_tokens") if usage and not error else reserve
        if not isinstance(charged, int) or charged < 0:
            charged = reserve
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await self.web.get(session, attempt_id, ATTEMPT_KIND)
            control = await session.get(CognitiveControl, self.k.instance_id)
            self.experiments._settle_control(control, reserve, charged)
            self.research.outbound_inflight.discard(row.data["historical_memory_id"])
            validation = (
                self._quote_validation(output, payload)
                if output
                else {
                    "validator_version": VALIDATOR_VERSION,
                    "valid": False,
                    "reasons": ["no_structured_output"],
                    "quote_provenance": False,
                    "semantic_verification": False,
                    "explanation_status": "unverified_model_interpretation",
                    "current_quote_exact": False,
                    "historical_quote_exact": False,
                }
            )
            row.status = (
                "validated"
                if output and not error and validation["valid"]
                else "rejected"
                if output
                else "failed"
            )
            row.data = row.data | {
                "usage": usage,
                "charged_tokens": charged,
                "estimated_usd": price(usage),
                "raw_response": raw[:16384] if isinstance(raw, str) else None,
                "raw_response_sha256": hashlib.sha256(raw.encode()).hexdigest()
                if isinstance(raw, str)
                else None,
                "raw_response_truncated": isinstance(raw, str) and len(raw) > 16384,
                "validation": validation,
                "validator_version": VALIDATOR_VERSION,
                "error": error,
                "latency_ms": (time.monotonic() - started) * 1000,
                "completed_at": now().isoformat(),
            }
            connection = None
            if row.status == "validated" and output:
                goal_terms = _tokens(payload.get("goal_instruction", ""))
                shown_terms = sorted(
                    (_tokens(output.current_quote or "") & _tokens(output.historical_quote or ""))
                    - goal_terms
                )
                connection = self.web.add(
                    session,
                    CONNECTION_KIND,
                    {
                        "goal_id": payload["goal_id"],
                        "current_snapshot_id": payload["current_snapshot_id"],
                        "current_url": payload["current_url"],
                        "current_sha256": payload["current_sha256"],
                        "current_quote": output.current_quote,
                        "historical_memory_id": payload["historical_memory_id"],
                        "historical_url": payload["historical_url"],
                        "historical_sha256": payload["historical_sha256"],
                        "historical_quote": output.historical_quote,
                        "model_evidence_quote": output.historical_quote,
                        "shared_terms": shown_terms,
                        "relation_type": output.relationship,
                        "explanation": output.explanation,
                        "limitations": output.limitations,
                        "confidence": output.confidence,
                        "status": "candidate"
                        if output.relationship != "insufficient_evidence"
                        else "insufficient_evidence",
                        "evidence_policy": (
                            "model hypothesis with exact source quotations; not independently "
                            "verified truth"
                        ),
                        "analysis_version": ANALYSIS_VERSION,
                        "validator_version": VALIDATOR_VERSION,
                        "payload_sha256": row.data["payload_sha256"],
                        "request_sha256": row.data["request_sha256"],
                        "provider": provider,
                        "model": provider["model"],
                        "consent_id": row.data["consent_id"],
                        "validation": validation,
                        "evidence_status": "quote_provenance_only_unverified_interpretation",
                        "explanation_status": "unverified_model_interpretation",
                        "usage": usage,
                        "estimated_usd": price(usage),
                        "inference_calls": 0 if provider["id"] == "local_stub" else 1,
                        "owner_useful": None,
                        "created_at": now().isoformat(),
                    },
                    payload["current_snapshot_id"],
                    "candidate"
                    if output.relationship != "insufficient_evidence"
                    else "insufficient_evidence",
                )
                row.data = row.data | {"connection_id": connection.id}
            self.k.add_event(
                session,
                "research.relationship_settled",
                {
                    "attempt_id": row.id,
                    "status": row.status,
                    "consent_id": row.data["consent_id"],
                    "charged_tokens": charged,
                },
            )
            await session.flush()
            result = {
                "analysis": record(row),
                "connection": record(connection) if connection else None,
                "abstained": bool(
                    not connection or connection.data.get("status") == "insufficient_evidence"
                ),
            }
        return result

    def _local_stub(self, payload):
        current = payload["current_excerpt"]
        historical = payload["historical_excerpt"]
        goal_terms = _tokens(payload.get("goal_instruction", ""))
        terms = sorted((_tokens(current) & _tokens(historical)) - goal_terms)
        current_quote, historical_quote, shown = _overlap_spans(current, historical, terms)
        if shown and current_quote and historical_quote:
            return RelationshipOutput(
                relationship="possible_conceptual_connection",
                explanation=(
                    "The local deterministic stub found shared lexical terms "
                    + ", ".join(shown[:6])
                    + " in the displayed spans. This is a scripted candidate, not a semantic "
                    "finding or an external model result."
                ),
                current_quote=current_quote,
                historical_quote=historical_quote,
                limitations=(
                    "Lexical overlap does not establish agreement, support, contradiction or "
                    "corroboration. No external model was called."
                ),
                confidence=0.25,
            )
        return RelationshipOutput(
            relationship="insufficient_evidence",
            explanation=(
                "The local deterministic stub found no substantive shared source span after "
                "goal vocabulary was excluded."
            ),
            current_quote=None,
            historical_quote=None,
            limitations="No external model was called.",
            confidence=0.0,
        )

    def _local_stub_invalid(self, payload):
        return RelationshipOutput(
            relationship="possible_conceptual_connection",
            explanation="A fabricated authority claim that is not supported by evidence.",
            current_quote="a",
            historical_quote="b",
            limitations="Controlled invalid-output fixture.",
            confidence=0.99,
        )

    def _quote_validation(self, output, payload):
        return validate_relationship_output(output, payload)

    async def invalidate_for_grant(self, grant_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.web.rows(session, CONSENT_KIND):
                if row.data.get("grant_id") == grant_id and row.status in ("pending", "authorized"):
                    row.status = "invalidated"
                    row.data = row.data | {
                        "invalidated_at": now().isoformat(),
                        "invalid_reason": "current_page_grant_revoked",
                    }

    async def invalidate_for_memory(self, memory_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.web.rows(session, CONSENT_KIND):
                if row.data.get("historical_memory_id") == memory_id and row.status in (
                    "pending",
                    "authorized",
                ):
                    row.status = "invalidated"
                    row.data = row.data | {
                        "invalidated_at": now().isoformat(),
                        "invalid_reason": "historical_memory_withdrawn",
                    }

    async def initialize(self):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.web.rows(session, ATTEMPT_KIND):
                if row.status != "reserved":
                    continue
                control = await session.get(CognitiveControl, self.k.instance_id)
                reserve = row.data.get("reserved_tokens", 0)
                self.experiments._settle_control(control, reserve, reserve)
                row.status = "interrupted"
                row.data = row.data | {
                    "charged_tokens": reserve,
                    "error": "Unknown completion; never replayed",
                }
                self.research.outbound_inflight.discard(row.data["historical_memory_id"])

    async def list(self):
        async with self.k.db.sessions() as session:
            return {
                "analyses": [record(row) for row in await self.web.rows(session, ATTEMPT_KIND)],
                "connections": [
                    record(row)
                    for row in await self.web.rows(session, CONNECTION_KIND)
                    if row.data.get("analysis_version") == ANALYSIS_VERSION
                ],
            }
