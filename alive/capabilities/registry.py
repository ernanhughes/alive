"""Immutable startup catalogue; compatibility projections are derived from it."""

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from alive.capabilities.contracts import json_bytes, validate
from alive.capabilities.manifest import ManifestError, canonical_bytes, parse
from alive.capabilities.trusted import LEGACY_OPERATIONS, TRUSTED, permission_bits


@dataclass(frozen=True)
class Operation:
    # Legacy 'available' means an underlying method exists, not an authorized adapter.
    id: str
    kind: str
    summary: str
    side_effects: str
    binding: str | None
    unavailable_reason: str | None = None
    executable: bool = False
    workflow_unavailable_reason: str | None = None

    @property
    def available(self):
        return self.binding is not None


@dataclass(frozen=True)
class Capability:
    content: bytes
    manifest_sha256: str
    implementation_sha256: str | None
    status: str
    reason: str | None

    @property
    def manifest(self):
        # Callers receive a copy, never a mutable reference into the catalogue.
        return json.loads(self.content)

    @property
    def executable(self):
        return self.status in {"available", "deprecated"}

    @property
    def identity(self):
        m = self.manifest
        return {
            "id": m["id"],
            "version": m["version"],
            "manifest_sha256": self.manifest_sha256,
            "implementation_id": m["implementation"]["id"],
            "implementation_sha256": self.implementation_sha256,
        }

    def public_view(self):
        m = self.manifest
        return m | {
            "manifest_sha256": self.manifest_sha256,
            "implementation_sha256": self.implementation_sha256,
            "status": self.status,
            "workflow_available": self.executable,
            "unavailable_reason": self.reason,
            "authorization": "Requires an exact owner grant; availability is not permission",
        }


class CapabilityRegistry:
    def __setattr__(self, name, value):
        if getattr(self, "_sealed", False):
            raise TypeError("capability registry is immutable; construct a new startup registry")
        object.__setattr__(self, name, value)

    def __init__(
        self, manifests, *, implementations=TRUSTED, disabled=(), snapshots=(), limits=None
    ):
        snapshots = tuple(snapshots)
        entries = {}
        disabled = frozenset(disabled)
        for manifest in manifests:
            # Revalidate copies supplied by trusted callers too.
            m = parse(canonical_bytes(manifest))
            key = (m.id, m.version)
            if key in entries:
                raise ManifestError("duplicate capability identity/version")
            impl = implementations.get(m.implementation.id)
            requested = permission_bits(m.permissions.model_dump())
            fingerprint, reason, status = None, None, "available"
            if impl is None or not impl.installed:
                status, reason = "unavailable", "Trusted workflow implementation is not installed"
            else:
                if (
                    not requested <= impl.permission_ceiling
                    or not impl.permission_ceiling <= requested
                ):
                    raise ManifestError("manifest permissions do not match implementation ceiling")
                if (m.execution.kind, m.execution.side_effects) != (impl.kind, impl.side_effects):
                    raise ManifestError("manifest execution kind or effects mismatch")
                fingerprint = impl.fingerprint()
                if m.implementation.sha256 and m.implementation.sha256 != fingerprint:
                    status, reason = "incompatible", "Trusted implementation fingerprint mismatch"
            if m.id in disabled or f"{m.id}@{m.version}" in disabled:
                status, reason = "disabled", "Disabled by deployment policy"
            elif status == "available" and m.deprecated:
                status = "deprecated"
            blob = canonical_bytes(m)
            entries[key] = Capability(
                blob, hashlib.sha256(blob).hexdigest(), fingerprint, status, reason
            )
        self._entries = MappingProxyType(entries)
        known = {ident for ident, _ in entries} | {f"{i}@{v}" for i, v in entries}
        if disabled - known:
            raise ManifestError("unknown disabled capability")
        self._implementations = MappingProxyType(dict(implementations))
        self._snapshots = MappingProxyType({s.reference: s for s in snapshots})
        if len(self._snapshots) != len(tuple(snapshots)):
            raise ManifestError("duplicate repository snapshot reference")
        grouped = {}
        for (ident, version), cap in entries.items():
            grouped.setdefault(ident, []).append(cap)
        operations = {}
        for ident, versions in grouped.items():
            if len({v.manifest["execution"]["kind"] for v in versions}) != 1:
                raise ManifestError("an operation id cannot change kind across versions")
            cap = max(versions, key=lambda v: tuple(map(int, v.manifest["version"].split("."))))
            m = cap.manifest
            impl = implementations.get(m["implementation"]["id"])
            binding = impl.legacy_binding if impl else None
            legacy_reason = impl.legacy_reason if impl else "No underlying implementation installed"
            operations[ident] = Operation(
                ident,
                m["execution"]["kind"],
                m["description"],
                m["execution"]["side_effects"],
                binding,
                legacy_reason,
                cap.executable,
                cap.reason,
            )
        self.operations = MappingProxyType(operations)
        policies = {}
        for key, overrides in (limits or {}).items():
            choices = [
                c
                for c in entries.values()
                if key in {c.identity["id"], c.identity["id"] + "@" + c.identity["version"]}
            ]
            if not choices or type(overrides) is not dict:
                raise ManifestError("unknown capability policy")
            for cap in choices:
                policy_key = (cap.identity["id"], cap.identity["version"])
                effective = (
                    json.loads(policies[policy_key])
                    if policy_key in policies
                    else dict(cap.manifest["execution"])
                )
                for field, value in overrides.items():
                    if (
                        field
                        not in {
                            "timeout_seconds",
                            "max_input_bytes",
                            "max_output_bytes",
                            "max_input_items",
                            "max_files",
                            "max_source_bytes",
                            "max_model_calls",
                            "max_output_tokens",
                        }
                        or type(value) is not int
                    ):
                        raise ManifestError("invalid capability configuration")
                    minimum = (
                        1
                        if field
                        in {
                            "timeout_seconds",
                            "max_input_bytes",
                            "max_output_bytes",
                            "max_input_items",
                        }
                        else 0
                    )
                    if not minimum <= value <= effective[field]:
                        raise ManifestError("configuration cannot widen a manifest limit")
                    effective[field] = value
                policies[policy_key] = json_bytes(effective)
        self._policies = MappingProxyType(policies)
        self._sealed = True

    def list(self):
        return tuple(self._entries[key] for key in sorted(self._entries))

    def get(self, capability_id, version=None):
        if version is not None:
            return self._entries[(capability_id, version)]
        candidates = [c for (ident, _), c in self._entries.items() if ident == capability_id]
        if not candidates:
            raise KeyError(capability_id)
        return max(candidates, key=lambda c: tuple(map(int, c.manifest["version"].split("."))))

    def adapter(self, capability_id, version=None):
        cap = self.get(capability_id, version)
        if not cap.executable:
            raise ValueError("capability unavailable")
        return self._implementations[cap.identity["implementation_id"]].resolve()

    def recheck(self, identity):
        try:
            cap = self.get(identity["id"], identity["version"])
        except KeyError:
            raise ValueError("pinned capability unavailable") from None
        if not cap.executable or cap.identity != identity:
            raise ValueError("pinned capability unavailable or changed")
        impl = self._implementations.get(identity["implementation_id"])
        if (
            impl is None
            or not impl.installed
            or impl.fingerprint() != identity["implementation_sha256"]
        ):
            raise ValueError("trusted implementation changed since startup")
        return cap

    def implementation_state(self, cap):
        """Descriptive only: installed code is not authorization to run it."""
        impl = self._implementations.get(cap.manifest["implementation"]["id"])
        if impl is None or not impl.installed:
            return "missing"
        declared = cap.manifest["implementation"].get("sha256")
        return (
            "fingerprint_mismatch" if declared and declared != impl.fingerprint() else "installed"
        )

    def limits_for(self, cap):
        key = (cap.identity["id"], cap.identity["version"])
        return (
            json.loads(self._policies[key]) if key in self._policies else cap.manifest["execution"]
        )

    def policy_sha256(self, cap):
        return hashlib.sha256(
            json_bytes(
                {
                    "policy": "capability-policy/v1",
                    "identity": cap.identity,
                    "limits": self.limits_for(cap),
                }
            )
        ).hexdigest()

    def grants_for(self, snapshot, *, resources=None):
        """Trusted owner convenience only; no HTTP or model can publish the resulting grant."""
        grants = {}
        for stage_id, binding in snapshot.items():
            cap = self.recheck(binding["identity"])
            limits = {
                k: v
                for k, v in self.limits_for(cap).items()
                if k not in {"kind", "side_effects", "retry_policy"}
            }
            limits["timeout_seconds"] = min(
                limits["timeout_seconds"], binding["stage_limits"]["timeout_seconds"]
            )
            limits["max_output_tokens"] = min(
                limits["max_output_tokens"], binding["stage_limits"]["max_output_tokens"]
            )
            grants[stage_id] = {
                "identity": cap.identity,
                "permissions": cap.manifest["permissions"],
                "limits": limits,
                "policy_sha256": self.policy_sha256(cap),
                "resources": (resources or {}).get(stage_id, {}),
            }
        return grants

    def check_grant(self, binding, grant):
        cap = self.recheck(binding["identity"])
        expected = self.grants_for({"stage": binding})["stage"]
        if type(grant) is not dict or set(grant) != set(expected):
            raise ManifestError("capability grant contract")
        if (
            grant["identity"] != expected["identity"]
            or grant["policy_sha256"] != expected["policy_sha256"]
        ):
            raise ManifestError("capability identity or configuration changed")
        if grant["permissions"] != expected["permissions"]:
            raise ManifestError("capability permissions not approved")
        if type(grant["limits"]) is not dict or set(grant["limits"]) != set(expected["limits"]):
            raise ManifestError("capability grant limits")
        for key, ceiling in expected["limits"].items():
            minimum = (
                1
                if key
                in {
                    "timeout_seconds",
                    "max_input_bytes",
                    "max_output_bytes",
                    "max_input_items",
                    "max_invocations",
                }
                else 0
            )
            value = grant["limits"][key]
            if type(value) is not int or not minimum <= value <= ceiling:
                raise ManifestError("owner grant cannot widen capability limits")
        if type(grant["resources"]) is not dict:
            raise ManifestError("capability resource contract")
        if (
            "repository.read" not in permission_bits(cap.manifest["permissions"])
            and grant["resources"]
        ):
            raise ManifestError("undeclared capability resources")
        return cap

    def bind(self, spec, *, legacy_compatibility=False):
        result = {}
        for stage in spec.stages:
            cap = self.get(stage.operation, getattr(stage, "capability_version", None))
            m = cap.manifest
            requested_hash = getattr(stage, "capability_sha256", None)
            if requested_hash and requested_hash != cap.manifest_sha256:
                raise ManifestError("requested capability hash mismatch")
            if (
                m["execution"]["kind"] != stage.type
                or stage.limits.timeout_seconds > m["execution"]["timeout_seconds"]
            ):
                raise ManifestError("stage exceeds capability contract")
            legacy = (
                legacy_compatibility
                and stage.operation in LEGACY_OPERATIONS
                and not stage.capability_version
                and not stage.capability_sha256
            )
            if legacy:
                # PI-02 registrations checked the DAG's declared contract, not adapter
                # schemas. Preserve that boundary; runtime still checks BOTH contracts.
                result[stage.id] = {
                    "identity": cap.identity,
                    "manifest": m,
                    "legacy_contract": True,
                    "stage_limits": {
                        "timeout_seconds": stage.limits.timeout_seconds,
                        "max_output_tokens": stage.limits.max_output_tokens or 0,
                    },
                }
                continue
            for key, field in stage.output_schema.properties.items():
                if (
                    key not in m["outputs"]["properties"]
                    or m["outputs"]["properties"][key]["type"] != field.type
                ):
                    raise ManifestError("workflow output does not match capability contract")
            if set(m["outputs"].get("required", [])) - stage.output_schema.properties.keys():
                raise ManifestError("workflow omits required capability output")
            if set(stage.inputs) - m["inputs"].get("properties", {}).keys():
                raise ManifestError("workflow input outside capability contract")
            if set(m["inputs"].get("required", [])) - stage.inputs.keys():
                raise ManifestError("workflow omits required capability input")
            for key, value in stage.inputs.items():
                expected = m["inputs"]["properties"][key]
                if isinstance(value, str) and value.startswith("$input."):
                    if spec.inputs[value.split(".")[1]].type != expected["type"]:
                        raise ManifestError("workflow input reference type mismatch")
                elif isinstance(value, str) and value.startswith("$stage."):
                    _, producer, field = value.split(".")
                    selected = next(s for s in spec.stages if s.id == producer)
                    if selected.output_schema.properties[field].type != expected["type"]:
                        raise ManifestError("workflow dependency reference type mismatch")
                else:
                    validate(value, expected)
            result[stage.id] = {
                "identity": cap.identity,
                "manifest": m,
                "stage_limits": {
                    "timeout_seconds": stage.limits.timeout_seconds,
                    "max_output_tokens": stage.limits.max_output_tokens or 0,
                },
            }
        return result


def load_registry(directory=None, *, disabled=(), snapshots=(), limits=None):
    roots = [Path(__file__).parent / "manifests"]
    if directory is not None:
        roots.append(Path(directory))
    manifests = []
    for root in roots:
        if not root.is_dir() or root.is_symlink() or root.is_junction():
            raise ManifestError("manifest directory unavailable or linked")
        files = sorted(root.glob("*.yaml"))
        if len(files) + len(manifests) > 128:
            raise ManifestError("manifest count limit")
        for file in files:
            if (
                file.is_symlink()
                or file.is_junction()
                or not re.fullmatch(r"[a-z][a-z0-9_.@-]{0,110}\.yaml", file.name)
            ):
                raise ManifestError("invalid manifest filename or linked file")
            if file.stat().st_size > 65536:
                raise ManifestError("manifest size limit")
            m = parse(file.read_bytes())
            if file.name != f"{m.id}@{m.version}.yaml":
                raise ManifestError("manifest filename identity mismatch")
            manifests.append(m)
    return CapabilityRegistry(manifests, disabled=disabled, snapshots=snapshots, limits=limits)


@lru_cache(maxsize=1)
def default_registry():
    return load_registry()
