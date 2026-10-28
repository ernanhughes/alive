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

    async def register_campaign(self, data):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            for row in await self.rows(session, CAMPAIGN_KIND):
                if row.data.get("campaign_digest") != data.campaign_digest:
                    continue
                manifest_sha = hashlib.sha256(
                    json.dumps(data.manifest, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest()
                if row.data.get("manifest_sha256") != manifest_sha:
                    raise ValueError("Campaign digest already registered with other content")
                return self.public(row)
            manifest_payload = json.dumps(data.manifest, sort_keys=True, ensure_ascii=False)
            row = WebExperience(
                id=uid(),
                instance_id=self.k.instance_id,
                kind=CAMPAIGN_KIND,
                status="registered",
                data=data.model_dump()
                | {
                    "manifest_sha256": _hash(manifest_payload),
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
            for row in await self.rows(session, CAMPAIGN_KIND):
                if row.data.get("campaign_digest") == campaign_digest:
                    return self.public(row)
        raise KeyError("Unknown campaign")

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
            if data.call_cap > campaign.data["call_cap"]:
                raise ValueError("Approval call cap exceeds the registered campaign")
            if data.max_usd > campaign.data["max_usd"]:
                raise ValueError("Approval USD cap exceeds the registered campaign")
            if data.max_input_tokens > campaign.data["max_input_tokens"]:
                raise ValueError("Approval token cap exceeds the registered campaign")
            synthetic = bool(campaign.data.get("synthetic"))
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
