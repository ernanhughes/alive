"""Fast catalogue tests: discovery is never executable or owner authority."""

import json
from pathlib import Path

import pytest
import yaml

from alive.capabilities.manifest import ManifestError, parse
from alive.capabilities.registry import CapabilityRegistry, default_registry, load_registry

ROOT = Path(__file__).resolve().parents[1] / "alive/capabilities/manifests"


def declared(**changes):
    value = yaml.safe_load((ROOT / "context.prepare@1.0.0.yaml").read_text(encoding="utf-8"))
    value.update(changes)
    return value


def manifest(value):
    return parse(yaml.safe_dump(value, sort_keys=False))


def test_legacy_metadata_does_not_claim_a_governed_adapter_exists():
    registry = default_registry()
    cap = registry.get("memory.retrieve")
    assert registry.operations["memory.retrieve"].available
    assert not cap.executable and not registry.operations["memory.retrieve"].executable
    assert registry.get("context.prepare").executable
    with pytest.raises(ValueError):
        registry.adapter("memory.retrieve")


def test_another_declaration_reuses_trusted_code_without_engine_or_registry_edits():
    registry = CapabilityRegistry([manifest(declared()), manifest(declared(id="context.review"))])
    assert registry.get("context.review").executable
    assert registry.adapter("context.review") is registry.adapter("context.prepare")
    assert registry.get("context.review").identity["id"] == "context.review"


def test_unknown_implementation_is_discoverable_but_not_executable():
    value = declared()
    value["implementation"]["id"] = "not-installed-v1"
    registry = CapabilityRegistry([manifest(value)])
    assert registry.list()[0].status == "unavailable"
    with pytest.raises(ValueError):
        registry.adapter("context.prepare")


def test_manifest_cannot_expand_or_hide_implementation_permissions():
    for mode in ("governed_pi",):
        value = declared()
        value["permissions"]["network"]["mode"] = mode
        with pytest.raises(ManifestError, match="ceiling"):
            CapabilityRegistry([manifest(value)])
    value = declared()
    value["permissions"]["evidence"] = "none"
    with pytest.raises(ManifestError, match="ceiling"):
        CapabilityRegistry([manifest(value)])


def test_wrong_fingerprint_is_unavailable_and_does_not_resolve_code():
    value = declared()
    value["implementation"]["sha256"] = "0" * 64
    registry = CapabilityRegistry([manifest(value)])
    assert registry.get("context.prepare").status == "incompatible"
    with pytest.raises(ValueError):
        registry.adapter("context.prepare")


def test_disabled_and_changed_capabilities_do_not_rebind_an_old_identity():
    original = CapabilityRegistry([manifest(declared())])
    identity = original.get("context.prepare").identity
    for registry in (
        CapabilityRegistry([manifest(declared())], disabled=["context.prepare"]),
        CapabilityRegistry([manifest(declared(description="Revised declaration"))]),
        CapabilityRegistry([manifest(declared(version="2.0.0"))]),
    ):
        with pytest.raises(ValueError):
            registry.recheck(identity)
    assert original.recheck(identity).identity == identity


def test_version_selection_does_not_mutate_previously_captured_identity():
    registry = CapabilityRegistry([manifest(declared()), manifest(declared(version="1.1.0"))])
    identity = registry.get("context.prepare", "1.0.0").identity
    assert registry.get("context.prepare").identity["version"] == "1.1.0"
    assert registry.recheck(identity).identity["version"] == "1.0.0"
    with pytest.raises(ManifestError, match="duplicate"):
        CapabilityRegistry([manifest(declared()), manifest(declared())])


def test_registry_and_returned_metadata_cannot_change_installed_contract():
    registry = CapabilityRegistry([manifest(declared())])
    before = registry.get("context.prepare").identity
    exposed = registry.get("context.prepare").manifest
    exposed["implementation"]["id"] = "different-id"
    assert registry.get("context.prepare").identity == before
    with pytest.raises(TypeError):
        registry.operations["other"] = None
    with pytest.raises(TypeError):
        registry.operations = {}
    assert "authorized_repository" not in json.dumps(registry.get("context.prepare").public_view())


def test_directory_loading_refuses_collisions_and_filename_identity_mismatch(tmp_path):
    p = tmp_path / "context.prepare@1.0.0.yaml"
    p.write_text(yaml.safe_dump(declared()), encoding="utf-8")
    with pytest.raises(ManifestError, match="duplicate"):
        load_registry(tmp_path)
    p.unlink()
    (tmp_path / "wrong@1.0.0.yaml").write_text(yaml.safe_dump(declared()), encoding="utf-8")
    with pytest.raises(ManifestError, match="filename"):
        load_registry(tmp_path)
