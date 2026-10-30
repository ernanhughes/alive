"""Workflow definitions are DATA: a strict, versioned, canonicalisable specification (ALIVE-PI-02A).

A definition names stages, their dependencies and the *closed* set of operations they may use. It
carries no code: unknown keys are rejected (so `shell`, `command`, `import`, `class_path`, `code`
cannot ride along), strings cannot hold templates or markup, and every reference is a typed pointer.

Nothing here executes anything. `parse_definition` validates, `canonical_bytes` fixes the exact
bytes that are hashed and stored, so equivalent spellings of one definition have one identity.
"""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from alive.workflows.operations import OPERATIONS

SCHEMA_VERSION = 1  # the shape of this document; independent of a workflow's own `version`
MAX_STAGES = 32
MAX_DEFINITION_BYTES = 64 * 1024
MAX_DEPENDENCIES = 8
MAX_INPUTS = 16
MAX_PROPERTIES = 16

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{2,63}$")
STAGE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
REF_RE = re.compile(r"^\$(input|stage)(\.[a-z][a-z0-9_]{0,31}){1,2}$")
# Display text ends up in diagrams and pages: no markup, templating, escapes or control characters.
FORBIDDEN_TEXT = re.compile(r"[<>`{}$\\\x00-\x1f\x7f]")
# Titles are drawn inside diagram nodes, so they get an allowlist, not a denylist: no quotes,
# brackets, semicolons, pipes, hashes or anything else a diagram language treats as syntax.
TITLE_CHARS = re.compile(r"^[\w .,:'&+/?!%-]+$")

StageType = Literal["deterministic", "pi_agent", "validation", "approval_gate"]
ValueType = Literal["string", "number", "integer", "boolean", "array", "object"]


class DefinitionError(ValueError):
    """A definition was refused. `problems` lists every reason, safe to show to the owner."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def safe_text(value, label, limit, *, title=False):
    if not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be 1-{limit} characters")
    if title and not TITLE_CHARS.match(value):
        raise ValueError(f"{label} may use letters, digits, spaces and . , : ' & + / ? ! % -")
    if FORBIDDEN_TEXT.search(value):
        raise ValueError(f"{label} may not contain markup, templating or control characters")
    return value


class InputSpec(Strict):
    type: ValueType
    required: bool = True


class PropertySpec(Strict):
    type: ValueType


class OutputSchema(Strict):
    """A deliberately tiny JSON-Schema subset: one object of typed fields. No `$ref`, no nesting."""

    type: Literal["object"] = "object"
    properties: dict[str, PropertySpec] = Field(min_length=1, max_length=MAX_PROPERTIES)
    required: list[str] = Field(default_factory=list, max_length=MAX_PROPERTIES)

    @field_validator("properties")
    @classmethod
    def property_names(cls, value):
        for name in value:
            if not FIELD_RE.match(name):
                raise ValueError(f"invalid property name {name!r}")
        return value


class StageLimits(Strict):
    timeout_seconds: int = Field(default=120, ge=1, le=900)
    max_output_tokens: int | None = Field(default=None, ge=64, le=4096)
    max_attempts: Literal[1] = 1  # PI-02 never retries an AI stage automatically


class StageSpec(Strict):
    id: str
    title: str
    type: StageType
    operation: str
    depends_on: list[str] = Field(default_factory=list, max_length=MAX_DEPENDENCIES)
    inputs: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=MAX_INPUTS
    )
    output_schema: OutputSchema
    limits: StageLimits = Field(default_factory=StageLimits)
    on_failure: Literal["stop", "skip", "wait_for_approval"] = "stop"

    @field_validator("id")
    @classmethod
    def stage_id(cls, value):
        if not STAGE_ID_RE.match(value):
            raise ValueError("stage id must match ^[a-z][a-z0-9_]{0,31}$")
        return value

    @field_validator("title")
    @classmethod
    def title_text(cls, value):
        return safe_text(value, "title", 80, title=True)

    @field_validator("inputs")
    @classmethod
    def input_values(cls, value):
        for name, item in value.items():
            if not FIELD_RE.match(name):
                raise ValueError(f"invalid input name {name!r}")
            if isinstance(item, str):
                if item.startswith("$"):
                    if not REF_RE.match(item):
                        raise ValueError(f"input {name!r}: not a valid reference")
                elif len(item) > 256 or FORBIDDEN_TEXT.search(item):
                    raise ValueError(f"input {name!r}: literal strings must be short plain text")
        return value


class WorkflowLimits(Strict):
    max_wall_seconds: int = Field(default=900, ge=1, le=3600)
    max_model_calls: int = Field(default=1, ge=0, le=8)
    max_total_output_tokens: int = Field(default=4096, ge=0, le=16384)


class WorkflowSpec(Strict):
    schema_version: Literal[1] = SCHEMA_VERSION
    name: str
    version: int = Field(ge=1, le=1_000_000)
    title: str
    description: str = ""
    inputs: dict[str, InputSpec] = Field(default_factory=dict, max_length=MAX_INPUTS)
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)
    stages: list[StageSpec] = Field(min_length=1, max_length=MAX_STAGES)

    @field_validator("name")
    @classmethod
    def workflow_name(cls, value):
        if not NAME_RE.match(value):
            raise ValueError("name must match ^[a-z][a-z0-9-]{2,63}$")
        return value

    @field_validator("title")
    @classmethod
    def title_text(cls, value):
        return safe_text(value, "title", 120, title=True)

    @field_validator("description")
    @classmethod
    def description_text(cls, value):
        return safe_text(value, "description", 1000) if value else value

    @field_validator("inputs")
    @classmethod
    def input_names(cls, value):
        for name in value:
            if not FIELD_RE.match(name):
                raise ValueError(f"invalid workflow input name {name!r}")
        return value


# --- parsing ------------------------------------------------------------------------------------


def _no_duplicate_keys(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise DefinitionError([f"duplicate key {key!r} (two spellings of one definition)"])
        seen[key] = value
    return seen


def parse_definition(raw):
    """Parse and structurally validate a definition. Accepts JSON text/bytes or a plain dict."""
    if isinstance(raw, dict):
        data = raw
        size = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    else:
        blob = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        size = len(blob)
        if size > MAX_DEFINITION_BYTES:
            raise DefinitionError(
                [f"definition is {size} bytes; the limit is {MAX_DEFINITION_BYTES}"]
            )
        try:
            data = json.loads(blob.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
        except (UnicodeDecodeError, ValueError, RecursionError) as exc:
            if isinstance(exc, DefinitionError):
                raise
            raise DefinitionError(["definition is not valid JSON"]) from None
    if size > MAX_DEFINITION_BYTES:
        raise DefinitionError([f"definition is {size} bytes; the limit is {MAX_DEFINITION_BYTES}"])
    if not isinstance(data, dict):
        raise DefinitionError(["definition must be a JSON object"])
    try:
        spec = WorkflowSpec.model_validate(data)
    except ValidationError as exc:
        raise DefinitionError(
            f"{'.'.join(str(p) for p in err['loc']) or 'definition'}: {err['msg']}"
            for err in exc.errors()
        ) from None
    check_structure(spec)
    return spec


# --- structure: the graph, references and the closed operation set -------------------------------


def check_structure(spec, operations=OPERATIONS):
    problems = []
    ids = [stage.id for stage in spec.stages]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"duplicate stage id {dup!r}")
    by_id = {stage.id: stage for stage in spec.stages}

    for stage in spec.stages:
        where = f"stage {stage.id!r}"
        operation = operations.get(stage.operation)
        if operation is None:
            problems.append(f"{where}: unknown operation {stage.operation!r}")
        else:
            if operation.kind != stage.type:
                problems.append(
                    f"{where}: operation {stage.operation!r} is a {operation.kind} operation, "
                    f"not {stage.type}"
                )
            if stage.on_failure == "skip" and operation.side_effects != "none":
                problems.append(f"{where}: only side-effect-free stages may be skipped")
        if stage.type == "pi_agent" and stage.limits.max_output_tokens is None:
            problems.append(f"{where}: a pi_agent stage must declare limits.max_output_tokens")
        if stage.type == "approval_gate" and stage.on_failure != "stop":
            problems.append(f"{where}: an approval gate can only stop")
        missing_required = set(stage.output_schema.required) - set(stage.output_schema.properties)
        if missing_required:
            problems.append(
                f"{where}: required fields not in properties: {sorted(missing_required)}"
            )
        if len(set(stage.depends_on)) != len(stage.depends_on):
            problems.append(f"{where}: repeated dependency")
        for dep in stage.depends_on:
            if dep == stage.id:
                problems.append(f"{where}: depends on itself")
            elif dep not in by_id:
                problems.append(f"{where}: depends on unknown stage {dep!r}")

    cycle = _find_cycle(by_id)
    if cycle:
        problems.append("dependency cycle: " + " -> ".join(cycle))
    else:
        ancestors = _ancestors(by_id)
        for stage in spec.stages:
            for name, value in stage.inputs.items():
                problems.extend(_check_ref(spec, by_id, ancestors, stage, name, value))

    model_calls = sum(1 for s in spec.stages if s.type == "pi_agent")
    if model_calls > spec.limits.max_model_calls:
        problems.append(
            f"{model_calls} pi_agent stages but limits.max_model_calls is "
            f"{spec.limits.max_model_calls}"
        )
    tokens = sum(s.limits.max_output_tokens or 0 for s in spec.stages if s.type == "pi_agent")
    if tokens > spec.limits.max_total_output_tokens:
        problems.append(
            f"pi_agent stages may emit {tokens} tokens but limits.max_total_output_tokens is "
            f"{spec.limits.max_total_output_tokens}"
        )
    if problems:
        raise DefinitionError(problems)


def _find_cycle(by_id):
    state, path = {}, []

    def visit(node):
        state[node] = 1
        path.append(node)
        for dep in by_id[node].depends_on:
            if dep not in by_id:
                continue
            if state.get(dep) == 1:
                return path[path.index(dep) :] + [dep]
            if dep not in state and (found := visit(dep)):
                return found
        path.pop()
        state[node] = 2
        return None

    for node in by_id:
        if node not in state and (found := visit(node)):
            return found
    return None


def _ancestors(by_id):
    """Every stage reachable through depends_on, per stage (the graph is known acyclic here)."""
    cache = {}

    def collect(node):
        if node not in cache:
            found = set()
            for dep in by_id[node].depends_on:
                if dep in by_id:
                    found |= {dep} | collect(dep)
            cache[node] = found
        return cache[node]

    return {node: collect(node) for node in by_id}


def _check_ref(spec, by_id, ancestors, stage, name, value):
    if not (isinstance(value, str) and value.startswith("$")):
        return []
    where = f"stage {stage.id!r} input {name!r}"
    parts = value[1:].split(".")
    if parts[0] == "input":
        if len(parts) != 2 or parts[1] not in spec.inputs:
            return [f"{where}: {value!r} is not a declared workflow input"]
        return []
    if len(parts) != 3 or parts[1] not in by_id:
        return [f"{where}: {value!r} does not name a stage output field"]
    producer, field = parts[1], parts[2]
    if producer not in ancestors[stage.id]:
        return [f"{where}: {value!r} reads stage {producer!r}, which it does not depend on"]
    if field not in by_id[producer].output_schema.properties:
        return [f"{where}: stage {producer!r} declares no output field {field!r}"]
    return []


def check_activatable(spec, operations=OPERATIONS):
    """A definition may only become `active` if every operation it names can actually run."""
    unavailable = sorted(
        {s.operation for s in spec.stages if not operations[s.operation].available}
    )
    if unavailable:
        raise DefinitionError(
            [
                f"operation {name!r} is unavailable: {operations[name].unavailable_reason}"
                for name in unavailable
            ]
        )


# --- canonical form and identity ----------------------------------------------------------------


def canonical_dict(spec):
    """One spelling per meaning: defaults filled in, set-like lists and keys sorted."""
    data = spec.model_dump(mode="json")
    for stage in data["stages"]:
        stage["depends_on"] = sorted(stage["depends_on"])
        stage["output_schema"]["required"] = sorted(stage["output_schema"]["required"])
    return data


def canonical_bytes(spec):
    return json.dumps(
        canonical_dict(spec), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def definition_sha256(spec):
    return hashlib.sha256(canonical_bytes(spec)).hexdigest()


def hash_of_stored(definition_json):
    """Recompute the identity of a stored definition (integrity check on read)."""
    blob = json.dumps(
        definition_json, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def graph_of(spec_dict, operations=OPERATIONS):
    """Nodes and edges for a viewer: plain data. The viewer escapes text; nothing is rendered."""
    nodes = []
    for stage in spec_dict["stages"]:
        operation = operations.get(stage["operation"])
        nodes.append(
            {
                "id": stage["id"],
                "title": stage["title"],
                "type": stage["type"],
                "operation": stage["operation"],
                "available": bool(operation and operation.available),
            }
        )
    edges = [
        {"from": dep, "to": stage["id"]}
        for stage in spec_dict["stages"]
        for dep in stage["depends_on"]
    ]
    return {"nodes": nodes, "edges": edges}
