"""Restricted YAML capability/v1 declarations. Loading never imports adapter code."""

import hashlib
import re
import unicodedata
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from yaml.events import (
    AliasEvent,
    MappingEndEvent,
    MappingStartEvent,
    SequenceEndEvent,
    SequenceStartEvent,
)

from alive.capabilities.contracts import canonical_schema, json_bytes, schema

ID = r"^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$"
VERSION = r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$"
MAX_BYTES = 65536


class ManifestError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Implementation(Strict):
    provider: Literal["builtin"]
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,79}$")
    interface: Literal["stage-context/v1"] = "stage-context/v1"
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Filesystem(Strict):
    mode: Literal["none", "read_only"]
    roots: list[Literal["authorized_repository"]] = Field(default_factory=list, max_length=1)


class Network(Strict):
    mode: Literal["none", "governed_pi"]


class Process(Strict):
    mode: Literal["none"]


class Permissions(Strict):
    filesystem: Filesystem
    network: Network
    process: Process
    evidence: Literal["none", "approved_context"]
    persistence: Literal["none", "workflow_result"]


class Execution(Strict):
    kind: Literal["deterministic", "pi_agent", "validation", "approval_gate"]
    side_effects: Literal["none", "read", "write"]
    timeout_seconds: int = Field(ge=1, le=3600)
    max_input_bytes: int = Field(ge=1, le=MAX_BYTES)
    max_output_bytes: int = Field(ge=1, le=MAX_BYTES)
    max_input_items: int = Field(ge=1, le=32)
    max_invocations: int = Field(ge=1, le=1)
    retry_policy: Literal["none"]
    max_files: int = Field(default=0, ge=0, le=64)
    max_source_bytes: int = Field(default=0, ge=0, le=MAX_BYTES)
    max_model_calls: int = Field(default=0, ge=0, le=8)
    max_output_tokens: int = Field(default=0, ge=0, le=16384)


class Presentation(Strict):
    category: str = Field(pattern=r"^[a-z][a-z0-9-]{0,31}$")
    icon: str = Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")
    tags: list[str] = Field(max_length=12)

    @field_validator("tags")
    @classmethod
    def tags_are_data(cls, value):
        if len(set(value)) != len(value) or any(
            not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", v) for v in value
        ):
            raise ValueError("invalid tags")
        return sorted(value)


class Manifest(Strict):
    schema_version: int = Field(ge=1, le=1)
    id: str = Field(pattern=ID, max_length=64)
    version: str = Field(pattern=VERSION, max_length=32)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    implementation: Implementation
    execution: Execution
    permissions: Permissions
    inputs: dict
    outputs: dict
    presentation: Presentation
    deprecated: bool = False
    supported_source_types: list[str] = Field(default_factory=list, max_length=12)
    examples: list[dict] = Field(default_factory=list, max_length=4)

    @field_validator("inputs", "outputs")
    @classmethod
    def contract(cls, value):
        schema(value)
        if value["type"] != "object" or value["additionalProperties"]:
            raise ValueError("root contract must be a closed object")
        return canonical_schema(value)


class Loader(yaml.SafeLoader):
    # YAML 1.2-style JSON scalars only: yes/on, dates, hex and sexagesimal stay strings.
    yaml_implicit_resolvers = {}

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if type(key) is not str or key == "<<" or key in result:
                raise ManifestError("duplicate, merge or non-string mapping key")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


Loader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))
Loader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^-?(?:0|[1-9][0-9]*)$"), list("-0123456789")
)
Loader.add_implicit_resolver("tag:yaml.org,2002:null", re.compile(r"^null$"), ["n"])


def _bounded(value, depth=0):
    if depth > 16:
        raise ManifestError("manifest nesting limit")
    if type(value) is dict:
        if len(value) > 64:
            raise ManifestError("manifest mapping limit")
        for key, item in value.items():
            _bounded(key, depth + 1)
            _bounded(item, depth + 1)
    elif type(value) is list:
        if len(value) > 256:
            raise ManifestError("manifest sequence limit")
        for item in value:
            _bounded(item, depth + 1)
    elif type(value) is str:
        if (
            len(value) > 4096
            or any(s in value for s in ("${", "{{", "{%"))
            # Every control character (C0, DEL and C1), except newline and tab.
            or any(unicodedata.category(c) == "Cc" and c not in "\n\t" for c in value)
        ):
            raise ManifestError("manifest text or interpolation refused")
    elif type(value) not in (int, bool, type(None)):
        raise ManifestError("unsupported manifest value")


def parse(raw):
    try:
        data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        if len(data) > MAX_BYTES:
            raise ManifestError("manifest size limit")
        text = data.decode("utf-8")
        depth = 0
        for count, event in enumerate(yaml.parse(text, Loader=Loader), 1):
            if (
                count > 8192
                or isinstance(event, AliasEvent)
                or getattr(event, "anchor", None) is not None
                or getattr(event, "tag", None) is not None
            ):
                raise ManifestError("YAML tags, aliases, anchors or event limit refused")
            if isinstance(event, (MappingStartEvent, SequenceStartEvent)):
                depth += 1
                if depth > 16:
                    raise ManifestError("manifest nesting limit")
            elif isinstance(event, (MappingEndEvent, SequenceEndEvent)):
                depth -= 1
        value = yaml.load(text, Loader=Loader)
        _bounded(value)
        manifest = Manifest.model_validate(value)
        if manifest.permissions.filesystem.roots != (
            ["authorized_repository"] if manifest.permissions.filesystem.mode == "read_only" else []
        ):
            raise ManifestError("filesystem permission contract")
        for example in manifest.examples:
            from alive.capabilities.contracts import validate

            validate(example, manifest.inputs)
        return manifest
    except ManifestError:
        raise
    except (ValueError, TypeError, yaml.YAMLError, RecursionError, UnicodeError) as error:
        if isinstance(error, ValidationError):
            locations = [".".join(map(str, e["loc"])) for e in error.errors()]
            raise ManifestError("invalid manifest fields: " + ", ".join(locations)) from None
        raise ManifestError("invalid capability manifest") from None


def canonical_bytes(manifest):
    return json_bytes(manifest.model_dump(mode="json"))


def manifest_sha256(manifest):
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()
