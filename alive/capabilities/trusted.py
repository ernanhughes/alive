"""Reviewed implementation allowlist. YAML IDs never become imports or commands."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from alive.capabilities.contracts import json_bytes

ROOT = Path(__file__).resolve().parents[2]
# id, operation, kind, effects, adapter, legacy underlying binding, reason, permissions
_LEGACY = [
    [
        "result-record-v1",
        "result.record",
        "deterministic",
        "write",
        "record",
        "alive.workflows.adapters:record",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "workflow_result",
        },
    ],
    [
        "context-prepare-v1",
        "context.prepare",
        "deterministic",
        "read",
        "prepare",
        "alive.cognition:Cognition.world_state",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "memory-retrieve-v1",
        "memory.retrieve",
        "deterministic",
        "read",
        None,
        "alive.memory:MemoryService.retrieve",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "cognition-role-v1",
        "cognition.role",
        "pi_agent",
        "none",
        "role",
        "alive.model_gateway:gateway_for",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "governed_pi"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "validate-references-v1",
        "evidence.validate_references",
        "validation",
        "none",
        "references",
        "alive.society:validate_references",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "evidence-evaluate-v1",
        "evidence.evaluate",
        "validation",
        "none",
        "compare",
        "alive.society:evaluate",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "evidence-qualify-v1",
        "evidence.qualify",
        "validation",
        "read",
        None,
        "alive.evidence_qualification:EvidenceQualifier.qualify",
        None,
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "approved_context",
            "persistence": "none",
        },
    ],
    [
        "evidence-record-v1",
        "evidence.record",
        "deterministic",
        "write",
        None,
        None,
        "No standalone evidence-recording operation exists: Cognition.finish() settles an "
        "Investigation and cannot be called on its own.",
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "none",
            "persistence": "none",
        },
    ],
    [
        "approval-request-v1",
        "approval.request",
        "approval_gate",
        "none",
        None,
        None,
        "Approvals are experiment-specific (ExperimentApprovals); there is no general gate yet.",
        {
            "filesystem": {"mode": "none", "roots": []},
            "network": {"mode": "none"},
            "process": {"mode": "none"},
            "evidence": "none",
            "persistence": "none",
        },
    ],
]


def permission_bits(permissions):
    result = set()
    if permissions["filesystem"]["mode"] == "read_only":
        result.add("repository.read")
    if permissions["network"]["mode"] == "governed_pi":
        result.add("model.infer")
    if permissions["evidence"] == "approved_context":
        result.add("evidence.read")
    if permissions["persistence"] == "workflow_result":
        result.add("workflow.write")
    return frozenset(result)


@dataclass(frozen=True)
class TrustedImplementation:
    id: str
    kind: str
    side_effects: str
    adapter_name: str | None
    legacy_binding: str | None
    legacy_reason: str | None
    permission_ceiling: frozenset[str]
    source_files: tuple[str, ...]
    interface: str = "stage-context/v1"

    @property
    def installed(self):
        return self.adapter_name is not None and all(
            (ROOT / p).is_file() for p in self.source_files
        )

    def fingerprint(self):
        hasher = hashlib.sha256(
            json_bytes(
                {
                    "id": self.id,
                    "interface": self.interface,
                    "permissions": sorted(self.permission_ceiling),
                }
            )
        )
        for path in self.source_files:
            hasher.update(path.encode())
            hasher.update((ROOT / path).read_bytes().replace(b"\r\n", b"\n"))
        return hasher.hexdigest()

    def resolve(self):
        if not self.installed:
            raise ValueError("trusted implementation unavailable")
        if self.id == "repository-inspector-v1":
            from alive.capabilities.repository import inspect_repository

            return inspect_repository
        # Both this module and these attribute names are server-owned reviewed code.
        from alive.workflows import adapters

        return getattr(adapters, self.adapter_name)


_BUILTINS = {
    item[0]: TrustedImplementation(
        item[0],
        item[2],
        item[3],
        item[4],
        item[5],
        item[6],
        permission_bits(item[7]),
        ("alive/workflows/adapters.py", "alive/society.py", "alive/cognitive_schema.py"),
    )
    for item in _LEGACY
}
_BUILTINS["repository-inspector-v1"] = TrustedImplementation(
    "repository-inspector-v1",
    "deterministic",
    "read",
    "inspect_repository",
    "alive.capabilities.repository:inspect_repository",
    None,
    frozenset({"repository.read"}),
    ("alive/capabilities/repository.py", "alive/capabilities/contracts.py"),
)
TRUSTED = MappingProxyType(_BUILTINS)
