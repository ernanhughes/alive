"""Reviewed implementation allowlist. YAML IDs never become imports or commands."""

import hashlib
import importlib
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
    if permissions.get("sources", "none") == "approved_capture":
        result.add("source.read")
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
    # "module:function" selected by this reviewed table, never by a manifest. It is part of the
    # fingerprint, so re-pointing an implementation at different code changes its identity.
    adapter: str | None
    legacy_binding: str | None
    legacy_reason: str | None
    permission_ceiling: frozenset[str]
    source_files: tuple[str, ...]
    interface: str = "stage-context/v1"
    # What downstream code may rely on this implementation to be (for example the only writer
    # of a workflow result). Code-owned and fingerprinted; a manifest cannot grant a trait.
    traits: frozenset[str] = frozenset()

    @property
    def installed(self):
        return self.adapter is not None and all((ROOT / p).is_file() for p in self.source_files)

    def fingerprint(self):
        """Identify what actually runs: the selection metadata and the reviewed source bytes.

        Not transitive: helpers imported by these files are covered only if listed. The listed
        files are the review boundary (see docs/capabilities/PI-03A-SECURITY.md).
        """
        hasher = hashlib.sha256(
            json_bytes(
                {
                    "id": self.id,
                    "interface": self.interface,
                    "kind": self.kind,
                    "side_effects": self.side_effects,
                    "adapter": self.adapter,
                    "legacy_binding": self.legacy_binding,
                    "permissions": sorted(self.permission_ceiling),
                    "traits": sorted(self.traits),
                    "source_files": list(self.source_files),
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
        # The reference is a constant in this reviewed module; no manifest value reaches it.
        module, _, function = self.adapter.partition(":")
        return getattr(importlib.import_module(module), function)


# Traits by implementation id. A capability has a trait because of the implementation it names,
# never because of its own id: reusing result-record-v1 under another capability id keeps it.
TRAITS = {
    "cognition-role-v1": {"model.role"},
    "result-record-v1": {"result.writer"},
    "validate-references-v1": {"validation.independent", "validation.reference-identity"},
    "evidence-evaluate-v1": {"validation.independent"},
}
# The model gateway's own operation name. It is a gateway namespace, not a capability id.
MODEL_OPERATION = "cognition.role"

_BUILTINS = {
    item[0]: TrustedImplementation(
        item[0],
        item[2],
        item[3],
        f"alive.workflows.adapters:{item[4]}" if item[4] else None,
        item[5],
        item[6],
        permission_bits(item[7]),
        (
            "alive/workflows/adapters.py",
            "alive/workflows/context.py",
            "alive/society.py",
            "alive/cognitive_schema.py",
        ),
        traits=frozenset(TRAITS.get(item[0], ())),
    )
    for item in _LEGACY
}
_BUILTINS["repository-inspector-v1"] = TrustedImplementation(
    "repository-inspector-v1",
    "deterministic",
    "read",
    "alive.capabilities.repository:inspect_repository",
    "alive.capabilities.repository:inspect_repository",
    None,
    frozenset({"repository.read"}),
    ("alive/capabilities/repository.py", "alive/capabilities/contracts.py"),
)


def _source_implementation(identifier, adapter, *files):
    """Implementations that read owner-approved captured sources (alive.sources)."""
    return TrustedImplementation(
        identifier,
        "deterministic",
        "read",
        f"alive.capabilities.source_adapters:{adapter}",
        f"alive.capabilities.source_adapters:{adapter}",  # the legacy "a method exists" binding
        None,
        frozenset({"source.read"}),
        ("alive/capabilities/source_adapters.py", "alive/sources/custody.py", *files),
    )


_BUILTINS["repository-inspector-v2"] = _source_implementation(
    "repository-inspector-v2", "inspect_repository_v2", "alive/capabilities/repository.py"
)
_BUILTINS["document-extractor-v1"] = _source_implementation(
    "document-extractor-v1", "extract_document", "alive/sources/documents.py"
)
_BUILTINS["browser-source-v1"] = _source_implementation(
    "browser-source-v1", "prepare_browser_source", "alive/sources/documents.py"
)
_BUILTINS["collection-retriever-v1"] = _source_implementation(
    "collection-retriever-v1", "retrieve_collection"
)
_ANALYSIS_FILES = (
    "alive/analysis/adapters.py",
    "alive/analysis/contracts.py",
    "alive/analysis/context.py",
)
# L1-02. The analyst makes the one model call; it holds both the source-disclosure bit and the
# model bit, so its own custody check names the `repository.analyze` operation.
_BUILTINS["repository-analyst-v1"] = TrustedImplementation(
    "repository-analyst-v1",
    "pi_agent",
    "none",
    "alive.analysis.adapters:analyze",
    "alive.analysis.adapters:analyze",
    None,
    frozenset({"model.infer", "source.read"}),
    _ANALYSIS_FILES,
    traits=frozenset({"model.role"}),
)
_BUILTINS["repository-findings-validator-v1"] = TrustedImplementation(
    "repository-findings-validator-v1",
    "validation",
    "none",
    "alive.analysis.adapters:validate_findings",
    "alive.analysis.adapters:validate_findings",
    None,
    frozenset(),
    (*_ANALYSIS_FILES, "alive/analysis/validation.py", "alive/analysis/report.py"),
    traits=frozenset({"validation.independent"}),
)
TRUSTED = MappingProxyType(_BUILTINS)


def traits_of(implementation_id):
    implementation = TRUSTED.get(implementation_id)
    return implementation.traits if implementation else frozenset()


LEGACY_OPERATIONS = frozenset(item[1] for item in _LEGACY)
# Pre-PI-03 executions retained no capability identity; the operation ids they used were the only
# ones that existed and each mapped to exactly one implementation. Frozen history, never extended.
LEGACY_IMPLEMENTATION_BY_OPERATION = MappingProxyType({item[1]: item[0] for item in _LEGACY})
# Definitions shipped before PI-03 whose declared stage contracts predate the manifests. Adoption
# under the DAG-only contract is allowed ONLY for these exact definition hashes and for
# pre-existing database rows that have no binding yet. Everything else registers under the full
# capability contract. Retirement: remove an entry once that definition is re-issued as a new
# version that passes the modern contract; delete the branch when the set is empty.
LEGACY_DEFINITION_SHA256 = frozenset(
    {
        "84d396acf1deec85d507c9e0f5ff6c54c9f4e3cb89ae4569ed0a74537d651377",  # research-review v1
        "e97c11da4cd69d03bc6786879893e235abc7d47b958b2f1036bb0abf47de7d7d",  # fixture v1
    }
)
