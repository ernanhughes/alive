"""Read-only capability catalogue. Discovery here never installs, enables or runs anything.

Responses are built from explicit field lists: no implementation import paths, filesystem roots,
credentials or environment values. A listed capability is not authorized for any run.
"""

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select

from alive.capabilities.contracts import json_bytes
from alive.capabilities.manifest import ID, VERSION
from alive.capabilities.registry import default_registry
from alive.capabilities.trusted import permission_bits
from alive.workflows.models import WorkflowCapabilityBinding, WorkflowDefinition

CAPABILITY_ID = Path(pattern=ID, max_length=64, description="capability id")
CAPABILITY_VERSION = Path(pattern=VERSION, max_length=32, description="semantic version")
MAX_REFERENCES = 50

PERMISSION_LABELS = {
    "repository.read": "Bounded read of an owner-approved repository capture",
    "evidence.read": "Read of owner-approved evidence context",
    "model.infer": "Model inference through existing Pi admission",
    "workflow.write": "Persistence of a workflow result through the existing writer",
}


def effect_class(manifest):
    """One coarse, non-reassuring label. Installed never means safe or authorized."""
    bits = permission_bits(manifest["permissions"])
    if manifest["execution"]["side_effects"] == "write" or "workflow.write" in bits:
        return "writes"
    if "model.infer" in bits:
        return "model"
    if "repository.read" in bits or manifest["execution"]["side_effects"] == "read":
        return "read"
    return "none"


def summary(registry, cap):
    m = cap.manifest
    return {
        "id": m["id"],
        "version": m["version"],
        "name": m["name"],
        "description": m["description"],
        "category": m["presentation"]["category"],
        "icon": m["presentation"]["icon"],
        "tags": m["presentation"]["tags"],
        "status": cap.status,
        "workflow_available": cap.executable,
        "unavailable_reason": cap.reason,
        "deprecated": m["deprecated"],
        "kind": m["execution"]["kind"],
        "side_effects": m["execution"]["side_effects"],
        "effect_class": effect_class(m),
        "permission_classes": [
            PERMISSION_LABELS[bit] for bit in sorted(permission_bits(m["permissions"]))
        ],
        "manifest_sha256": cap.manifest_sha256,
        "implementation_state": registry.implementation_state(cap),
    }


def detail(registry, cap):
    m = cap.manifest
    return summary(registry, cap) | {
        "implementation": {
            "id": m["implementation"]["id"],
            "provider": m["implementation"]["provider"],
            "interface": m["implementation"]["interface"],
            "sha256": cap.implementation_sha256,
        },
        "permissions": m["permissions"],
        "declared_limits": m["execution"],
        "effective_limits": registry.limits_for(cap),
        "policy_sha256": registry.policy_sha256(cap),
        "inputs": m["inputs"],
        "outputs": m["outputs"],
        "supported_source_types": m["supported_source_types"],
        "examples": m["examples"],
        "authorization": "Requires an exact owner grant; availability is not permission",
    }


def catalog_sha256(registry):
    return hashlib.sha256(
        json_bytes([[c.identity["id"], c.identity["version"], c.manifest_sha256, c.status]
                    for c in registry.list()])
    ).hexdigest()  # fmt: skip


async def workflow_references(kernel, identity):  # definitions are global, not per-instance
    """Definitions whose retained binding names this exact id, version and manifest hash."""
    async with kernel.db.sessions() as session:
        rows = await session.execute(
            select(WorkflowDefinition, WorkflowCapabilityBinding)
            .join(
                WorkflowCapabilityBinding,
                WorkflowCapabilityBinding.definition_id == WorkflowDefinition.id,
            )
            .order_by(WorkflowDefinition.name, WorkflowDefinition.version)
        )
        found = []
        for definition, binding in rows.all():
            stages = [
                stage_id
                for stage_id, item in binding.snapshot.get("stages", {}).items()
                if all(
                    item["identity"].get(key) == identity[key]
                    for key in ("id", "version", "manifest_sha256")
                )
            ]
            if stages:
                found.append(
                    {
                        "name": definition.name,
                        "version": definition.version,
                        "status": definition.status,
                        "stages": sorted(stages),
                    }
                )
        return found[:MAX_REFERENCES]


def router(app, ready):
    api = APIRouter(prefix="/api/v1/capabilities/catalog", dependencies=[Depends(ready)])

    def registry():
        return getattr(app.state, "capabilities", None) or default_registry()

    @api.get("")
    async def catalogue():
        current = registry()
        return {
            "catalog_sha256": catalog_sha256(current),
            "capabilities": [summary(current, cap) for cap in current.list()],
        }

    @api.get("/{capability_id}")
    async def versions(capability_id: str = CAPABILITY_ID):
        current = registry()
        found = [cap for cap in current.list() if cap.identity["id"] == capability_id]
        if not found:
            raise HTTPException(404, "Unknown capability")
        return {
            "catalog_sha256": catalog_sha256(current),
            "versions": [summary(current, cap) for cap in found],
        }

    @api.get("/{capability_id}/versions/{version}")
    async def version_detail(capability_id: str = CAPABILITY_ID, version: str = CAPABILITY_VERSION):
        current = registry()
        try:
            cap = current.get(capability_id, version)
        except KeyError:
            raise HTTPException(404, "Unknown capability version") from None
        return {
            "catalog_sha256": catalog_sha256(current),
            "capability": detail(current, cap),
            "workflows": await workflow_references(app.state.kernel, cap.identity),
        }

    return api
