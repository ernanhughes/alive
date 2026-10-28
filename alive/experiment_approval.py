"""Owner-authenticated campaign registration and approval records.

The approval is a server-side record created through the authenticated owner API.
A local JSON file alone is never evidence of owner authorisation.
"""

import hashlib
import hmac
import json
import secrets

from pydantic import BaseModel, ConfigDict, Field

from alive.models import now, record, uid
from alive.web_models import WebExperience

CAMPAIGN_KIND = "research_experiment_campaign"
APPROVAL_KIND = "research_experiment_approval"
FROZEN_PROTOCOL_SHA256 = "85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b"
FROZEN_ANSWER_KEY_SHA256 = "255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d"
FROZEN_OUTPUT_TOKEN_CAP = 1536
ALLOWED_PROVIDER_MODELS = {
    "meta": "muse-spark-1.3",
    "local_stub": "deterministic-local-stub-v1",
}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampaignRequest(Strict):
    campaign_digest: str = Field(min_length=64, max_length=64)
    run_id: str = Field(min_length=1, max_length=160)
    protocol_sha256: str = Field(min_length=64, max_length=64)
    answer_key_sha256: str = Field(min_length=64, max_length=64)
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    task_count: int = Field(ge=1, le=100)
    call_cap: int = Field(ge=1, le=500)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_usd: float = Field(ge=0)
    no_retries: bool
    stages: dict
    stage_contracts: dict | None = None
    analysis_mode: str = "paired"
    content: dict | None = None
    manifest: dict
    synthetic: bool = False


class ApprovalRequest(Strict):
    stage: int = Field(default=1, ge=1, le=10)
    call_cap: int = Field(ge=1, le=500)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_usd: float = Field(ge=0)
    no_retries: bool
    human_attestation: bool = False


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


class ExperimentApprovals:
    def __init__(self, kernel):
        self.k = kernel

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

    async def web_get(self, session, row_id, kind):
        row = await session.get(WebExperience, row_id)
        if not row or row.instance_id != self.k.instance_id or row.kind != kind:
            raise KeyError("Unknown " + kind)
        return row

    @staticmethod
    def canonical_content(content):
        return hashlib.sha256(
            json.dumps(content, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    @staticmethod
    def validate_campaign_content(data):
        content = data.content
        if content is None:
            if not data.synthetic:
                raise ValueError("Real campaigns require immutable content binding")
            if data.protocol_sha256 != FROZEN_PROTOCOL_SHA256:
                raise ValueError("Legacy campaign protocol hash is not frozen v3")
            if data.answer_key_sha256 != FROZEN_ANSWER_KEY_SHA256:
                raise ValueError("Legacy campaign answer-key hash is not frozen")
            if data.provider not in ALLOWED_PROVIDER_MODELS:
                raise ValueError("Legacy campaign provider is not allowed")
            if data.model != ALLOWED_PROVIDER_MODELS[data.provider]:
                raise ValueError("Legacy campaign model is not the pinned model")
            return
        required = {
            "schema_version",
            "protocol_version",
            "protocol_sha256",
            "answer_key_sha256",
            "provider",
            "model",
            "analysis_mode",
            "instructions_sha256",
            "schema_sha256",
            "max_output_tokens",
            "task_order",
            "tasks",
            "call_order",
            "cells",
        }
        if set(content) != required:
            raise ValueError("Campaign content has missing or unknown fields")
        if content["schema_version"] != "alive14-r5-campaign-v1":
            raise ValueError("Unsupported campaign schema version")
        if content["protocol_version"] != "alive14r3-paired-v3":
            raise ValueError("Campaign protocol version is not the frozen v3 protocol")
        if content["protocol_sha256"] != FROZEN_PROTOCOL_SHA256:
            raise ValueError("Campaign protocol hash does not match the frozen identity")
        if content["answer_key_sha256"] != FROZEN_ANSWER_KEY_SHA256:
            raise ValueError("Campaign answer-key hash does not match the frozen identity")
        if content["provider"] not in ALLOWED_PROVIDER_MODELS:
            raise ValueError("Campaign provider is not allowed")
        if content["model"] != ALLOWED_PROVIDER_MODELS[content["provider"]]:
            raise ValueError("Campaign model does not match the pinned model")
        if data.provider != content["provider"] or data.model != content["model"]:
            raise ValueError("Campaign provider/model fields disagree")
        if content["analysis_mode"] != "paired":
            raise ValueError("Campaign analysis mode must be paired")
        if content["max_output_tokens"] != FROZEN_OUTPUT_TOKEN_CAP:
            raise ValueError("Campaign output-token cap is not the frozen cap")
        if data.max_output_tokens != content["max_output_tokens"]:
            raise ValueError("Campaign output-token caps disagree")
        task_order = content["task_order"]
        tasks = content["tasks"]
        call_order = content["call_order"]
        cells = content["cells"]
        if len(task_order) != len(set(task_order)) or len(tasks) != len(task_order):
            raise ValueError("Campaign task order or task count is inconsistent")
        if data.task_count != len(tasks):
            raise ValueError("Campaign task count is inconsistent")
        task_ids = [task["task_id"] for task in tasks]
        if task_ids != task_order:
            raise ValueError("Campaign task order does not match task records")
        if len(call_order) != len(task_order) * 2 or len(cells) != len(call_order):
            raise ValueError("Campaign cell count is inconsistent")
        if data.call_cap != len(cells):
            raise ValueError("Campaign call cap does not match its cell count")
        for index, call in enumerate(call_order):
            task_id = task_order[index // 2]
            condition = "A" if index % 2 == 0 else "B"
            if call.get("task_id") != task_id or call.get("condition") != condition:
                raise ValueError("Campaign call order is not the frozen A/B order")
        for index, cell in enumerate(cells):
            if cell.get("call_index") != index:
                raise ValueError("Campaign cell index is not sequential")
            if cell.get("task_id") != call_order[index]["task_id"]:
                raise ValueError("Campaign cell task does not match call order")
            if cell.get("condition") != call_order[index]["condition"]:
                raise ValueError("Campaign cell condition does not match call order")
            expected_keys = {
                "task_id",
                "condition",
                "goal",
                "question",
                "current_url",
                "current_sha256",
                "current_excerpt",
                "call_index",
                "reserved_tokens",
                "reserved_micro_usd",
                "content_sha256",
            }
            if cell["condition"] == "B":
                expected_keys |= {
                    "historical_url",
                    "historical_sha256",
                    "historical_excerpt",
                }
            if set(cell) != expected_keys:
                raise ValueError("Campaign cell has missing or unknown fields")
            hash_input = {
                key: cell[key]
                for key in (
                    "task_id",
                    "condition",
                    "goal",
                    "question",
                    "current_url",
                    "current_sha256",
                    "current_excerpt",
                )
            }
            if cell["condition"] == "B":
                hash_input |= {
                    "historical_url": cell["historical_url"],
                    "historical_sha256": cell["historical_sha256"],
                    "historical_excerpt": cell["historical_excerpt"],
                }
            expected_hash = hashlib.sha256(
                json.dumps(hash_input, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            if cell["content_sha256"] != expected_hash:
                raise ValueError("Campaign cell content hash is invalid")
        stage_one = cells[:2]
        stage_one_tokens = sum(int(cell["reserved_tokens"]) for cell in stage_one)
        stage_one_usd = sum(int(cell["reserved_micro_usd"]) for cell in stage_one) / 1e6
        total_tokens = sum(int(cell["reserved_tokens"]) for cell in cells)
        total_usd = sum(int(cell["reserved_micro_usd"]) for cell in cells) / 1e6
        contracts = data.stage_contracts
        if set(contracts) != {"1", "2"}:
            raise ValueError("Campaign must register exactly stage 1 and stage 2")
        expected_contracts = {
            "1": {
                "stage": 1,
                "call_cap": 2,
                "index_start": 0,
                "index_end": 2,
                "reserved_tokens": stage_one_tokens,
                "max_usd": stage_one_usd,
            },
            "2": {
                "stage": 2,
                "call_cap": len(cells),
                "index_start": 2,
                "index_end": len(cells),
                "reserved_tokens": total_tokens,
                "max_usd": total_usd,
            },
        }
        for key, expected in expected_contracts.items():
            actual = contracts[key]
            if actual.get("stage") != expected["stage"]:
                raise ValueError("Stage contract number is inconsistent")
            if actual.get("call_cap") != expected["call_cap"]:
                raise ValueError("Stage call cap is inconsistent")
            if (
                actual.get("index_start") != expected["index_start"]
                or actual.get("index_end") != expected["index_end"]
            ):
                raise ValueError("Stage cell range is inconsistent")
            if actual.get("reserved_tokens") != expected["reserved_tokens"]:
                raise ValueError("Stage token reservation is inconsistent")
            if abs(float(actual.get("max_usd", -1)) - expected["max_usd"]) > 1e-9:
                raise ValueError("Stage USD reservation is inconsistent")
        if data.max_input_tokens < total_tokens:
            raise ValueError("Campaign token cap is below its cell reservations")
        if data.max_usd < total_usd:
            raise ValueError("Campaign USD cap is below its stage reservations")
        if data.campaign_digest != ExperimentApprovals.canonical_content(content):
            raise ValueError("Client campaign digest does not match canonical content")

    async def register_campaign(self, data):
        self.validate_campaign_content(data)
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.rows(session, CAMPAIGN_KIND):
                if row.data.get("campaign_digest") != data.campaign_digest:
                    continue
                registration_sha = hashlib.sha256(
                    json.dumps(data.model_dump(), sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                if row.data.get("registration_sha256") != registration_sha:
                    raise ValueError("Campaign digest already registered with other content")
                return self.public(row)
            registration_payload = json.dumps(data.model_dump(), sort_keys=True, ensure_ascii=False)
            row = WebExperience(
                id=uid(),
                instance_id=self.k.instance_id,
                kind=CAMPAIGN_KIND,
                status="registered",
                data=data.model_dump()
                | {
                    "registration_sha256": _hash(registration_payload),
                    "manifest_sha256": _hash(
                        json.dumps(data.manifest, sort_keys=True, ensure_ascii=False)
                    ),
                    "registered_at": now().isoformat(),
                    "status": "registered",
                },
            )
            session.add(row)
            await session.flush()
            return self.public(row)

    async def list_campaigns(self):
        async with self.k.db.sessions() as session:
            return {
                "campaigns": [self.public(row) for row in await self.rows(session, CAMPAIGN_KIND)]
            }

    async def campaign(self, campaign_digest):
        async with self.k.db.sessions() as session:
            return await self.campaign_locked(session, campaign_digest)

    async def campaign_locked(self, session, campaign_digest):
        for row in await self.rows(session, CAMPAIGN_KIND):
            if row.data.get("campaign_digest") == campaign_digest:
                return row
        raise KeyError("Unknown campaign")

    async def approval_locked(self, session, approval_id):
        for row in await self.rows(session, APPROVAL_KIND):
            if row.data.get("approval_id") == approval_id:
                return row
        raise KeyError("Unknown approval")

    async def attempts_locked(self, session, campaign_digest):
        from sqlalchemy import select

        rows = (
            await session.scalars(
                select(WebExperience).where(
                    WebExperience.instance_id == self.k.instance_id,
                    WebExperience.kind == "research_relationship_analysis",
                )
            )
        ).all()
        return [row for row in rows if row.data.get("campaign_digest") == campaign_digest]

    async def stage_one_eligible_locked(self, session, campaign_digest):
        rows = [
            row
            for row in await self.attempts_locked(session, campaign_digest)
            if row.data.get("stage") == 1
        ]
        if len(rows) != 2:
            return False
        if any(row.status == "reserved" for row in rows):
            return False
        if any(row.data.get("campaign_fatal") for row in rows):
            return False
        return any(row.status == "validated" for row in rows)

    @staticmethod
    def stage_contract(campaign, stage):
        contract = (campaign.data.get("stage_contracts") or {}).get(str(stage))
        if contract:
            return contract
        if not campaign.data.get("content"):
            if not campaign.data.get("synthetic"):
                raise ValueError("Real campaign requires a strict stage contract")
            stages = campaign.data.get("stages") or {}
            legacy = stages.get("stage_1" if stage == 1 else "full")
            if not legacy:
                raise ValueError("Legacy campaign has no definition for this stage")
            call_cap = int(legacy["call_cap"])
            return {
                "stage": stage,
                "call_cap": call_cap,
                "index_start": 0 if stage == 1 else 2,
                "index_end": 2 if stage == 1 else call_cap,
                "reserved_tokens": int(legacy["reserved_tokens"]),
                "max_usd": float(legacy["worst_case_micro_usd"]) / 1e6,
            }
        raise ValueError("The campaign has no server-side contract for this stage")

    def _validate_stage_approval(self, campaign, data):
        contract = self.stage_contract(campaign, data.stage)
        if data.call_cap != contract["call_cap"]:
            raise ValueError(f"Stage {data.stage} requires exactly {contract['call_cap']} calls")
        if data.max_input_tokens < contract["reserved_tokens"]:
            raise ValueError("Approval token cap does not cover the stage reservation")
        if not campaign.data.get("synthetic") and data.max_usd < contract["max_usd"]:
            raise ValueError("Approval USD cap does not cover the stage reservation")
        if data.max_input_tokens > campaign.data["max_input_tokens"]:
            raise ValueError("Approval token cap exceeds the registered campaign")
        if data.max_usd > campaign.data["max_usd"]:
            raise ValueError("Approval USD cap exceeds the registered campaign")
        if data.max_output_tokens != campaign.data["max_output_tokens"]:
            raise ValueError("Approval output-token cap must equal the frozen campaign cap")
        return contract

    async def approve(self, campaign_digest, data):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            campaign = None
            for row in await self.rows(session, CAMPAIGN_KIND):
                if row.data.get("campaign_digest") == campaign_digest:
                    campaign = row
                    break
            if campaign is None:
                raise KeyError("Unknown campaign")
            if data.no_retries is not True:
                raise ValueError("Zero-retry approval is required")
            if data.stage not in (1, 2):
                raise ValueError("Only stage 1 and stage 2 are defined")
            synthetic = bool(campaign.data.get("synthetic"))
            contract = self._validate_stage_approval(campaign, data)
            attempts = await self.attempts_locked(session, campaign_digest)
            if data.stage == 1 and any(row.data.get("stage") == 1 for row in attempts):
                raise ValueError("Stage 1 already started; approve stage 2 instead")
            if data.stage == 2:
                if campaign.data.get("content") and not await self.stage_one_eligible_locked(
                    session, campaign_digest
                ):
                    raise ValueError(
                        "Stage 2 is not eligible until stage 1 has two terminal attempts "
                        "and at least one validated result"
                    )
                if any(row.data.get("stage") == 2 for row in attempts):
                    raise ValueError("Stage 2 already started")
            if not synthetic and not data.human_attestation:
                raise ValueError("Real approval requires explicit human attestation")
            capability = secrets.token_urlsafe(32)
            for prior in await self.rows(session, APPROVAL_KIND):
                if (
                    prior.data.get("campaign_digest") == campaign_digest
                    and prior.status == "active"
                ):
                    prior.status = "superseded"
                    prior.data = prior.data | {
                        "status": "superseded",
                        "superseded_at": now().isoformat(),
                    }
            row = WebExperience(
                id=uid(),
                instance_id=self.k.instance_id,
                kind=APPROVAL_KIND,
                parent_id=campaign.id,
                status="active",
                data={
                    "approval_id": uid(),
                    "campaign_digest": campaign_digest,
                    "run_id": campaign.data["run_id"],
                    "protocol_sha256": campaign.data["protocol_sha256"],
                    "provider": campaign.data["provider"],
                    "model": campaign.data["model"],
                    "stage": data.stage,
                    "stage_contract": contract,
                    "call_cap": data.call_cap,
                    "max_input_tokens": data.max_input_tokens,
                    "max_output_tokens": data.max_output_tokens,
                    "max_usd": data.max_usd,
                    "no_retries": True,
                    "human_attestation": data.human_attestation,
                    "synthetic": synthetic,
                    "provenance": (
                        "synthetic_owner_endpoint" if synthetic else "authenticated_owner_interface"
                    ),
                    "approved_by": (
                        "synthetic_local_runner" if synthetic else "authenticated_owner_interface"
                    ),
                    "approved_at": now().isoformat(),
                    "status": "active",
                    "capability_hash": _hash(capability),
                },
            )
            session.add(row)
            await session.flush()
            return self.public(row) | {"approval_capability": capability}

    @staticmethod
    def _canonical_content(campaign, task, condition, payload):
        content = {
            "protocol_sha256": campaign.data["protocol_sha256"],
            "answer_key_sha256": campaign.data["answer_key_sha256"],
            "provider": campaign.data["provider"],
            "model": campaign.data["model"],
            "analysis_mode": campaign.data.get("analysis_mode", "paired"),
            "max_output_tokens": campaign.data["max_output_tokens"],
            "instructions_sha256": campaign.data["manifest"]["instructions_sha256"],
            "schema_sha256": campaign.data["manifest"]["schema_sha256"],
            "task_id": task["task_id"],
            "goal": task["goal"],
            "question": task["question"],
            "current_url": task["current_url"],
            "current_sha256": task["current_sha256"],
            "current_excerpt": task["current_excerpt"],
        }
        if condition == "B":
            content |= {
                "historical_url": task["historical_url"],
                "historical_sha256": task["historical_sha256"],
                "historical_excerpt": task["historical_excerpt"],
            }
        return content

    async def assert_dispatch_locked(
        self,
        session,
        *,
        campaign_digest,
        approval_id,
        run_id,
        stage,
        task_id,
        condition,
        call_index,
        payload,
        request_sha256,
        instructions_sha256,
        schema_sha256,
        max_output_tokens,
        exclude_attempt_id=None,
    ):
        campaign = await self.campaign_locked(session, campaign_digest)
        approval = await self.approval_locked(session, approval_id)
        if approval.status != "active":
            raise PermissionError("Campaign approval is not active")
        data = approval.data
        if data.get("campaign_digest") != campaign_digest:
            raise PermissionError("Approval is bound to another campaign")
        if data.get("run_id") != run_id or campaign.data.get("run_id") != run_id:
            raise PermissionError("Approval is bound to another run")
        if int(data.get("stage", 0)) != int(stage):
            raise PermissionError("Approval stage does not match the dispatch")
        contract = self.stage_contract(campaign, stage)
        if not (contract["index_start"] <= call_index < contract["index_end"]):
            raise PermissionError("Call index is outside the approved stage")
        if call_index >= int(data.get("call_cap", 0)):
            raise PermissionError("Call index exceeds the approval call cap")
        manifest = campaign.data.get("content") or campaign.data["manifest"]
        call_order = manifest.get("call_order", [])
        if call_index >= len(call_order):
            raise PermissionError("Call index is not in the frozen call order")
        expected = call_order[call_index]
        if expected["task_id"] != task_id or expected["condition"] != condition:
            raise PermissionError("Cell does not match the frozen call order")
        if stage == 2 and not await self.stage_one_eligible_locked(session, campaign_digest):
            raise PermissionError("Stage 2 is not eligible")
        attempts = await self.attempts_locked(session, campaign_digest)
        if any(
            row.data.get("call_index") == call_index and row.id != exclude_attempt_id
            for row in attempts
        ):
            raise PermissionError("This call index has already been attempted")
        task = next((row for row in manifest["tasks"] if row["task_id"] == task_id), None)
        if task is None:
            raise PermissionError("Task is not in the approved manifest")
        if payload.get("analysis_mode") != campaign.data.get("analysis_mode", "paired"):
            raise PermissionError("Analysis mode does not match the approval")
        if payload.get("provider") != campaign.data["provider"]:
            raise PermissionError("Provider does not match the approval")
        if payload.get("model") != campaign.data["model"]:
            raise PermissionError("Model does not match the approval")
        if payload.get("goal_instruction") != task["goal"]:
            raise PermissionError("Goal does not match the approved manifest")
        if payload.get("research_question") != task["question"]:
            raise PermissionError("Research question does not match the approved manifest")
        if payload.get("current_url") != task["current_url"]:
            raise PermissionError("Current URL does not match the approved manifest")
        if payload.get("current_sha256") != task["current_sha256"]:
            raise PermissionError("Current source hash does not match the approved manifest")
        if payload.get("current_excerpt") != task["current_excerpt"]:
            raise PermissionError("Current excerpt does not match the approved manifest")
        historical_keys = {
            "historical_memory_id",
            "historical_url",
            "historical_sha256",
            "historical_excerpt",
        }
        if condition == "A":
            if historical_keys & set(payload):
                raise PermissionError("Condition A payload contains historical evidence")
        else:
            if payload.get("historical_url") != task["historical_url"]:
                raise PermissionError("Historical URL does not match the approved manifest")
            if payload.get("historical_sha256") != task["historical_sha256"]:
                raise PermissionError("Historical source hash does not match the approved manifest")
            if payload.get("historical_excerpt") != task["historical_excerpt"]:
                raise PermissionError("Historical excerpt does not match the approved manifest")
        if instructions_sha256 != manifest["instructions_sha256"]:
            raise PermissionError("Instructions do not match the approved manifest")
        if schema_sha256 != manifest["schema_sha256"]:
            raise PermissionError("Schema does not match the approved manifest")
        if int(max_output_tokens) != int(manifest["max_output_tokens"]):
            raise PermissionError("Output-token cap does not match the approved manifest")
        content = self._canonical_content(campaign, task, condition, payload)
        return {
            "stage": int(stage),
            "approval_id": approval_id,
            "campaign_digest": campaign_digest,
            "task_id": task_id,
            "condition": condition,
            "call_index": call_index,
            "content": content,
            "content_sha256": _hash(json.dumps(content, sort_keys=True, ensure_ascii=False)),
            "request_sha256": request_sha256,
        }

    async def get_approval(self, approval_id, capability=None):
        async with self.k.db.sessions() as session:
            for row in await self.rows(session, APPROVAL_KIND):
                if row.data.get("approval_id") != approval_id:
                    continue
                if capability is not None:
                    supplied = _hash(capability)
                    if not hmac.compare_digest(supplied, row.data.get("capability_hash", "")):
                        raise PermissionError("Approval capability is invalid")
                return self.public(row)
        raise KeyError("Unknown approval")

    async def active_for_digest(self, campaign_digest):
        async with self.k.db.sessions() as session:
            candidates = [
                row
                for row in await self.rows(session, APPROVAL_KIND)
                if row.data.get("campaign_digest") == campaign_digest and row.status == "active"
            ]
            if not candidates:
                raise KeyError("No active approval for campaign")
            candidates.sort(key=lambda row: row.data.get("approved_at", ""), reverse=True)
            return self.public(candidates[0])

    async def revoke(self, approval_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.rows(session, APPROVAL_KIND):
                if row.data.get("approval_id") == approval_id:
                    row.status = "revoked"
                    row.data = row.data | {
                        "status": "revoked",
                        "revoked_at": now().isoformat(),
                    }
                    return self.public(row)
        raise KeyError("Unknown approval")

    @staticmethod
    def public(row):
        data = dict(row.data)
        data.pop("capability_hash", None)
        return record(row) | {"data": data}
