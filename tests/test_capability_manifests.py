"""Fast parser/contract tests; no database, subprocess, model or network required."""

import copy
from pathlib import Path

import pytest
import yaml

from alive.capabilities.contracts import ContractError, validate
from alive.capabilities.manifest import ManifestError, canonical_bytes, manifest_sha256, parse

ROOT = Path(__file__).resolve().parents[1] / "alive/capabilities/manifests"


def document():
    return yaml.safe_load((ROOT / "context.prepare@1.0.0.yaml").read_text(encoding="utf-8"))


def encode(value):
    return yaml.safe_dump(value, sort_keys=False).encode()


def test_all_legacy_contracts_are_valid_and_canonical():
    for path in ROOT.glob("*.yaml"):
        m = parse(path.read_bytes())
        assert path.name == f"{m.id}@{m.version}.yaml"
        assert canonical_bytes(parse(canonical_bytes(m))) == canonical_bytes(m)


def test_order_whitespace_and_set_like_required_fields_do_not_change_identity():
    value = document()
    original = manifest_sha256(parse(encode(value)))
    value["outputs"]["required"].reverse()
    other = yaml.safe_dump(value, sort_keys=True)
    assert manifest_sha256(parse("# explanation\n" + other)) == original


@pytest.mark.parametrize(
    "field", ["permissions", "implementation", "inputs", "outputs", "execution"]
)
def test_contract_changes_change_identity(field):
    value = document()
    before = manifest_sha256(parse(encode(value)))
    if field == "permissions":
        value[field]["network"]["mode"] = "governed_pi"
    elif field == "implementation":
        value[field]["id"] = "different-reviewed-implementation"
    elif field == "execution":
        value[field]["max_output_bytes"] -= 1
    else:
        value[field]["properties"]["new_field"] = {"type": "boolean"}
    assert manifest_sha256(parse(encode(value))) != before


@pytest.mark.parametrize(
    "payload",
    [
        b"!!python/object/apply:os.system ['echo forbidden']",
        b"schema_version: 1\nschema_version: 1",
        b"root: &root {value: 1}\nother: *root",
        b"root: &root [*root]",
        b"root: {<<: {value: 1}}",
        b"---\na: 1\n---\na: 2",
        b"root: " + b"[" * 30 + b"1" + b"]" * 30,
        b"x" * 65537,
        b"\xff\xfea\x00:\x00 \x001\x00",
        b"root: !custom value",
    ],
    ids=[
        "python-tag",
        "duplicate",
        "anchor",
        "recursive-alias",
        "merge",
        "documents",
        "depth",
        "size",
        "encoding",
        "custom-tag",
    ],
)
def test_yaml_features_cannot_construct_code_or_unbounded_data(payload, monkeypatch):
    import os

    calls = []
    monkeypatch.setattr(os, "system", lambda *args: calls.append(args))
    with pytest.raises(ManifestError):
        parse(payload)
    assert calls == []


@pytest.mark.parametrize(
    "change",
    [
        {"command": "echo forbidden"},
        {"python_import": "os.system"},
        {"schema_version": True},
        {"schema_version": "1"},
        {"version": "latest"},
        {"version": "01.0.0"},
        {"description": "${ALIVE_API_TOKEN}"},
        {"description": "{{ expression }}"},
        {"deprecated": "yes"},
        {"id": "../../escape"},
    ],
)
def test_strict_fields_versions_and_no_interpolation(change):
    value = document() | change
    with pytest.raises(ManifestError):
        parse(encode(value))


def test_implementation_ids_are_not_imports_and_unknown_schema_keywords_are_refused():
    value = document()
    value["implementation"]["id"] = "os:system"
    with pytest.raises(ManifestError):
        parse(encode(value))
    value = document()
    value["outputs"]["$ref"] = "file:///private"
    with pytest.raises(ManifestError):
        parse(encode(value))


def test_output_contract_refuses_unknown_fields_and_wrong_types():
    contract = {
        "type": "object",
        "additionalProperties": False,
        "required": ["count"],
        "properties": {"count": {"type": "integer"}},
    }
    validate({"count": 1}, contract)
    for value in ({"count": True}, {"count": "1"}, {"count": 1, "extra": 2}, {}):
        with pytest.raises(ContractError):
            validate(value, contract)


def test_schema_arrays_strings_and_nested_unknown_fields_are_bounded():
    value = document()
    value["outputs"] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "maxItems": 2,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name"],
                    "properties": {"name": {"type": "string", "maxLength": 4}},
                },
            }
        },
    }
    contract = parse(encode(value)).outputs
    validate({"items": [{"name": "okay"}]}, contract)
    for item in (
        {"items": [{"name": "large"}]},
        {"items": [{"name": "x", "extra": 1}]},
        {"items": [{"name": "x"}] * 3},
    ):
        with pytest.raises(ContractError):
            validate(item, contract)
    invalid = copy.deepcopy(value)
    del invalid["outputs"]["properties"]["items"]["maxItems"]
    with pytest.raises(ManifestError):
        parse(encode(invalid))
