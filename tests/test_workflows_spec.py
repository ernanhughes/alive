"""ALIVE-PI-02A: workflow definitions are strict data, with one canonical identity."""

import copy
import importlib
import json
from pathlib import Path

import pytest

from alive.workflows import operations
from alive.workflows.spec import (
    MAX_DEFINITION_BYTES,
    MAX_STAGES,
    DefinitionError,
    canonical_bytes,
    check_activatable,
    definition_sha256,
    graph_of,
    parse_definition,
)

SEED = Path(__file__).resolve().parents[1] / "alive" / "workflows" / "builtin"
SEED_TEXT = (SEED / "research-review.v1.json").read_text(encoding="utf-8")


def seed():
    return json.loads(SEED_TEXT)


def stage(stage_id, operation="context.prepare", **over):
    base = {
        "id": stage_id,
        "title": stage_id.title(),
        "type": "deterministic",
        "operation": operation,
        "output_schema": {"properties": {"snapshot": {"type": "object"}}, "required": ["snapshot"]},
    }
    return base | over


def workflow(*stages, **over):
    base = {
        "schema_version": 1,
        "name": "demo-flow",
        "version": 1,
        "title": "Demo",
        "stages": list(stages),
    }
    return base | over


def refused(raw, fragment):
    with pytest.raises(DefinitionError) as error:
        parse_definition(raw)
    assert any(fragment in problem for problem in error.value.problems), error.value.problems


# --- the shipped definition ---------------------------------------------------------------------


def test_the_shipped_definition_is_valid_and_maps_to_real_operations():
    spec = parse_definition(SEED_TEXT)
    assert [s.id for s in spec.stages] == ["prepare", "analyze", "validate", "record"]
    assert [s.type for s in spec.stages] == [
        "deterministic",
        "pi_agent",
        "validation",
        "deterministic",
    ]
    graph = graph_of(json.loads(canonical_bytes(spec)))
    assert graph["edges"] == [
        {"from": "prepare", "to": "analyze"},
        {"from": "analyze", "to": "validate"},
        {"from": "validate", "to": "record"},
    ]
    available = {n["id"]: n["available"] for n in graph["nodes"]}
    assert available == {"prepare": True, "analyze": True, "validate": True, "record": False}


def test_a_definition_naming_an_unavailable_operation_cannot_be_activated():
    with pytest.raises(DefinitionError) as error:
        check_activatable(parse_definition(SEED_TEXT))
    assert "evidence.record" in str(error.value) and "unavailable" in str(error.value)


@pytest.mark.parametrize(
    "op", [o for o in operations.OPERATIONS.values() if o.binding], ids=lambda o: o.id
)
def test_every_available_operation_points_at_real_existing_code(op):
    module, attribute = op.binding.split(":")
    target = importlib.import_module(module)
    for part in attribute.split("."):
        target = getattr(target, part)  # AttributeError here means the registry lies
    assert callable(target)


def test_the_operation_set_is_closed():
    with pytest.raises(TypeError):
        operations.OPERATIONS["shell.run"] = operations.Operation(
            "shell.run", "deterministic", "x", "write", "os:system"
        )
    assert {o.kind for o in operations.OPERATIONS.values()} <= {
        "deterministic", "pi_agent", "validation", "approval_gate"
    }  # fmt: skip
    assert all(
        not o.available == bool(o.unavailable_reason) for o in operations.OPERATIONS.values()
    )


# --- one canonical identity ---------------------------------------------------------------------


def test_equivalent_spellings_share_one_canonical_form_and_hash():
    base = seed()
    reordered = json.loads(json.dumps(base))
    reordered["stages"][1]["depends_on"] = ["prepare"]
    reordered["stages"][0] = dict(reversed(list(base["stages"][0].items())))  # key order
    explicit_defaults = copy.deepcopy(base)
    explicit_defaults["stages"][0]["on_failure"] = "stop"
    explicit_defaults["stages"][0]["limits"] = {"timeout_seconds": 120, "max_attempts": 1}
    spaced = json.dumps(base, indent=8)
    digests = {
        definition_sha256(parse_definition(raw))
        for raw in (SEED_TEXT, reordered, explicit_defaults, spaced)
    }
    assert len(digests) == 1


def test_set_like_lists_are_order_insensitive_but_meaning_changes_the_hash():
    a = workflow(stage("a"), stage("b"), stage("c", depends_on=["a", "b"]))
    b = workflow(stage("a"), stage("b"), stage("c", depends_on=["b", "a"]))
    assert definition_sha256(parse_definition(a)) == definition_sha256(parse_definition(b))
    c = workflow(stage("a"), stage("b"), stage("c", depends_on=["a"]))
    assert definition_sha256(parse_definition(a)) != definition_sha256(parse_definition(c))
    renamed = workflow(stage("a"), stage("b"), stage("c", depends_on=["a", "b"]), version=2)
    assert definition_sha256(parse_definition(a)) != definition_sha256(parse_definition(renamed))


def test_schema_version_is_separate_from_the_workflow_version():
    spec = parse_definition(workflow(stage("a"), version=7))
    assert (spec.schema_version, spec.version) == (1, 7)
    refused(workflow(stage("a"), schema_version=2), "schema_version")


def test_duplicate_json_keys_are_refused_not_silently_merged():
    text = SEED_TEXT.replace(
        '"name": "research-review",', '"name": "research-review", "name": "other-flow",'
    )
    refused(text, "duplicate key")


# --- structure ----------------------------------------------------------------------------------


def test_cycles_are_refused_with_the_path():
    refused(
        workflow(
            stage("a", depends_on=["c"]), stage("b", depends_on=["a"]), stage("c", depends_on=["b"])
        ),
        "dependency cycle",
    )
    refused(workflow(stage("a", depends_on=["a"])), "depends on itself")


def test_duplicate_stage_ids_are_refused():
    refused(workflow(stage("a"), stage("a")), "duplicate stage id")


def test_unknown_dependencies_and_operations_are_refused():
    refused(workflow(stage("a", depends_on=["ghost"])), "unknown stage")
    refused(workflow(stage("a", operation="shell.run")), "unknown operation")
    refused(workflow(stage("a", operation="")), "unknown operation")


def test_a_stage_type_must_match_its_operation_kind():
    refused(workflow(stage("a", type="validation")), "is a deterministic operation, not validation")
    refused(
        workflow(stage("a", operation="cognition.role", type="deterministic")),
        "is a pi_agent operation",
    )


def test_references_must_resolve_to_declared_inputs_and_upstream_fields():
    refused(workflow(stage("a", inputs={"x": "$input.nope"})), "not a declared workflow input")
    refused(
        workflow(stage("a"), stage("b", inputs={"x": "$stage.a.snapshot"})), "does not depend on"
    )
    refused(
        workflow(stage("a"), stage("b", depends_on=["a"], inputs={"x": "$stage.a.missing"})),
        "declares no output field",
    )
    refused(workflow(stage("a", inputs={"x": "$stage.ghost.f"})), "does not name a stage output")
    ok = workflow(stage("a"), stage("b", depends_on=["a"], inputs={"x": "$stage.a.snapshot"}))
    assert parse_definition(ok).stages[1].inputs == {"x": "$stage.a.snapshot"}


def test_transitive_dependencies_may_be_referenced():
    chain = workflow(
        stage("a"),
        stage("b", depends_on=["a"]),
        stage("c", depends_on=["b"], inputs={"x": "$stage.a.snapshot"}),
    )
    assert parse_definition(chain)


def test_model_stages_must_declare_limits_and_fit_the_workflow_budget():
    llm = stage("a", operation="cognition.role", type="pi_agent")
    refused(workflow(llm), "max_output_tokens")
    llm = stage(
        "a", operation="cognition.role", type="pi_agent", limits={"max_output_tokens": 1024}
    )
    refused(workflow(llm, limits={"max_model_calls": 0}), "max_model_calls")
    refused(workflow(llm, limits={"max_total_output_tokens": 512}), "max_total_output_tokens")
    assert parse_definition(workflow(llm))


def test_no_automatic_retries_and_skip_is_for_side_effect_free_stages_only():
    refused(workflow(stage("a", limits={"max_attempts": 2})), "max_attempts")
    refused(
        workflow(stage("a", operation="evidence.record", on_failure="skip")),
        "only side-effect-free stages may be skipped",
    )
    assert parse_definition(
        workflow(
            stage(
                "a", operation="evidence.validate_references", type="validation", on_failure="skip"
            )
        )
    )
    gate = stage(
        "g", operation="approval.request", type="approval_gate", on_failure="wait_for_approval"
    )
    refused(workflow(gate), "approval gate can only stop")


def test_limits_on_size_and_count():
    refused(workflow(*[stage(f"s{i}") for i in range(MAX_STAGES + 1)]), "stages")
    refused("x" * (MAX_DEFINITION_BYTES + 1), "limit")
    oversized = workflow(stage("a"))
    oversized["notes"] = "z" * (MAX_DEFINITION_BYTES + 1)
    refused(oversized, "limit")  # a dict is measured too, before it is validated
    refused(json.dumps(oversized), "limit")
    big = workflow(stage("a"), description="y" * 2000)
    refused(big, "description")
    refused(workflow(stage("a", depends_on=[f"d{i}" for i in range(9)])), "depends_on")
    refused("[]", "JSON object")
    refused("{not json", "not valid JSON")


# --- data, not code -----------------------------------------------------------------------------

EXECUTABLE_KEYS = [
    "shell",
    "command",
    "cmd",
    "import",
    "class_path",
    "code",
    "script",
    "exec",
    "eval",
    "capability",
    "url",
    "path",
]


@pytest.mark.parametrize("key", EXECUTABLE_KEYS)
def test_unknown_keys_cannot_carry_code_anywhere(key):
    top = workflow(stage("a"))
    top[key] = "anything"
    refused(top, "Extra inputs are not permitted")
    nested = workflow(stage("a", **{key: "anything"}))
    refused(nested, "Extra inputs are not permitted")
    limits = workflow(stage("a", limits={key: 1}))
    refused(limits, "Extra inputs are not permitted")


@pytest.mark.parametrize(
    "value",
    [
        "${HOME}",
        "{{ config }}",
        "$(id)",
        "`id`",
        "<script>alert(1)</script>",
        "a\\nb",
        "x{y}",
        "$input",
        "$stage.a",
        "$input.A",
        "$input.a.b.c",
        "$ input.x",
    ],
)
def test_input_strings_cannot_be_templates_or_malformed_references(value):
    refused(workflow(stage("a", inputs={"x": value})), "input 'x'")


def test_plain_literals_are_allowed():
    spec = parse_definition(
        workflow(
            stage("a", inputs={"role": "proposer", "n": 3, "flag": True, "pi": 0.5, "none": None})
        )
    )
    assert spec.stages[0].inputs["role"] == "proposer"


@pytest.mark.parametrize(
    "title",
    [
        'A"] --> B["x',
        "x[y]",
        "a;b",
        "a|b",
        "a#b",
        "<b>x</b>",
        "a`b",
        "a\nb",
        "${x}",
        "javascript:alert(1)\n",
        "click A call f()",
        "a=b",
        "a{b}",
        "a\\b",
    ],
)
def test_titles_cannot_inject_diagram_syntax(title):
    refused(workflow(stage("a", title=title)), "title")


def test_output_schemas_are_a_tiny_subset_without_references():
    for bad in (
        {"properties": {"x": {"$ref": "#/definitions/y"}}},
        {"type": "object", "properties": {"x": {"type": "string", "pattern": ".*"}}},
        {"type": "array", "properties": {"x": {"type": "string"}}},
        {"properties": {}},
        {"properties": {"Bad-Name": {"type": "string"}}},
        {"properties": {"x": {"type": "string"}}, "required": ["y"]},
    ):
        with pytest.raises(DefinitionError):
            parse_definition(workflow(stage("a", output_schema=bad)))
