"""F11-F16: small, local hardening of the manifest, registry and activation boundaries."""

import copy

import pytest
import yaml

from alive.capabilities.manifest import ManifestError, manifest_sha256, parse
from alive.capabilities.registry import CapabilityRegistry
from alive.workflows.examples import stage
from alive.workflows.spec import DefinitionError, check_activatable, parse_definition
from tests.conftest import MANIFESTS_DIR


def declared(**changes):
    value = yaml.safe_load((MANIFESTS_DIR / "context.prepare@1.0.0.yaml").read_text("utf-8"))
    return value | changes


def manifest(value):
    return parse(yaml.safe_dump(value, sort_keys=False, allow_unicode=True))


@pytest.mark.parametrize("escape", [r"\x7f", r"\x85", r"\x9f", r"\x00", r"\x1b", r"\x08"])
def test_every_control_character_is_refused_in_manifest_text(escape):
    # Written as a YAML escape in the file itself: dumping the character would let YAML turn
    # some of them (NEL, for one) into a line break before the check ever saw them.
    text = yaml.safe_dump(declared(description="PLACEHOLDER"), sort_keys=False)
    with pytest.raises(ManifestError):
        parse(text.replace("PLACEHOLDER", '"ok' + escape + '"'))
    assert parse(text.replace("PLACEHOLDER", '"ok"'))  # control: the same file without it parses


def test_ordinary_text_newline_and_tab_remain_allowed():
    assert manifest(declared(description="line one\n\tline two, with accents: é ü"))


def schema_with_enum(options):
    value = declared()
    value["inputs"] = {
        "type": "object",
        "additionalProperties": False,
        "required": [],
        "properties": {"mode": {"type": "string", "maxLength": 8, "enum": options}},
    }
    return value


def test_duplicate_enum_members_are_refused_rather_than_hashed_differently():
    assert manifest(schema_with_enum(["a", "b"]))
    with pytest.raises(ManifestError):
        manifest(schema_with_enum(["a", "a"]))


def test_equivalent_enum_orderings_keep_one_identity():
    first = manifest(schema_with_enum(["a", "b"]))
    second = manifest(schema_with_enum(["b", "a"]))
    assert manifest_sha256(first) == manifest_sha256(second)


def test_a_stale_disable_entry_fails_closed_and_names_the_entry():
    # Ignoring it would let a typo leave a capability enabled, so startup must stop.
    with pytest.raises(ManifestError, match="context.prepar "):
        CapabilityRegistry([manifest(declared())], disabled=("context.prepar",))
    with pytest.raises(ManifestError, match="remove the entry"):
        CapabilityRegistry([manifest(declared())], disabled=("gone.capability",))


def versioned(*versions, disabled=()):
    return CapabilityRegistry([manifest(declared(version=v)) for v in versions], disabled=disabled)


def definition(pin=None):
    raw = {
        "schema_version": 1,
        "name": "activation-probe",
        "version": 1,
        "title": "Activation probe",
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
        "stages": [
            stage(
                "prepare",
                "context.prepare",
                "deterministic",
                {"context": "object", "claims": "array", "sources": "array"},
            )
        ],
    }
    if pin:
        raw["stages"][0] = copy.deepcopy(raw["stages"][0]) | {"capability_version": pin}
    return raw


def activatable(registry, pin=None):
    spec = parse_definition(definition(pin), operations=registry.operations)
    check_activatable(spec, registry.operations)


def test_activation_judges_a_pinned_stage_by_the_version_it_pins():
    # Since PI-03C, an unpinned stage of a legacy operation means its original 1.0.0 (see
    # `bind`), so disabling only a newer version leaves it runnable; the pin is judged by the
    # version it names.
    newest_disabled = versioned("1.0.0", "2.0.0", disabled=("context.prepare@2.0.0",))
    activatable(newest_disabled, pin="1.0.0")  # the pinned version runs even though 2.0.0 does not
    activatable(newest_disabled)  # unpinned means 1.0.0 for this operation

    original_disabled = versioned("1.0.0", "2.0.0", disabled=("context.prepare@1.0.0",))
    with pytest.raises(DefinitionError, match="unavailable"):
        activatable(original_disabled)  # unpinned means 1.0.0, which is disabled
    with pytest.raises(DefinitionError, match="unavailable"):
        activatable(original_disabled, pin="1.0.0")  # used to pass activation and fail at runtime
    activatable(original_disabled, pin="2.0.0")  # an explicit pin to an enabled version
    with pytest.raises(DefinitionError, match="unavailable"):
        activatable(versioned("1.0.0"), pin="9.9.9")  # a version that is not installed


def test_the_public_operation_listing_discloses_no_internal_import_paths(client):
    body = client.get("/api/v1/workflow-operations").json()
    assert body["operations"] and all("binding" not in o for o in body["operations"])
    assert "alive." not in str(body)
