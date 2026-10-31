"""Bounded citation input contracts, separate from semantic or outcome labels."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Locator(Strict):
    kind: Literal["none", "file_lines", "section", "text_span", "page"]
    start: int = Field(ge=0, le=1000000)
    end: int = Field(ge=0, le=1000000)
    quote: str = Field(max_length=512)


class Reference(Strict):
    id: str = Field(max_length=256)
    item: str = Field(min_length=1, max_length=256)
    sha256: str = Field(min_length=64, max_length=64)
    locator: Locator


class Finding(Strict):
    id: str = Field(min_length=1, max_length=80)
    claim: str = Field(max_length=512)
    evidence: list[Reference] = Field(max_length=4)


class Batch(Strict):
    source_ref: str = Field(min_length=1, max_length=36)
    source_sha256: str = Field(min_length=64, max_length=64)
    scoped_sha256: str = Field(min_length=64, max_length=64)
    findings: list[Finding] = Field(max_length=8)


def input_schema():
    """Inline the finite Pydantic schema into PI-03A's non-executable schema subset."""
    full = Batch.model_json_schema()
    definitions = full.get("$defs", {})

    def inline(value):
        if "$ref" in value:
            return inline(definitions[value["$ref"].split("/")[-1]])
        result = {k: v for k, v in value.items() if k not in {"title", "$defs"}}
        if result.get("type") == "object":
            result["properties"] = {k: inline(v) for k, v in result["properties"].items()}
        elif result.get("type") == "array":
            result["items"] = inline(result["items"])
        elif result.get("type") == "string":
            result.setdefault("maxLength", 64)
        return result

    return inline(full)
