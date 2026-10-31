"""A bounded JSON-schema subset. No references, expressions or executable validators."""

import json
import math
import re

FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TYPES = {
    "object": lambda x: type(x) is dict,
    "array": lambda x: type(x) is list,
    "string": lambda x: type(x) is str,
    "integer": lambda x: type(x) is int,
    "number": lambda x: type(x) in (int, float) and math.isfinite(x),
    "boolean": lambda x: type(x) is bool,
}
KEYS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "minLength",
    "maxLength",
    "enum",
    "minimum",
    "maximum",
}


class ContractError(ValueError):
    pass


def check(condition, category):
    if not condition:
        raise ContractError(category)


def schema(value, depth=0):
    check(type(value) is dict and depth <= 8 and set(value) <= KEYS, "schema_shape")
    kind = value.get("type")
    check(kind in TYPES, "schema_type")
    allowed = {"type", "enum"}
    if kind == "object":
        allowed |= {"properties", "required", "additionalProperties"}
        check(type(value.get("additionalProperties")) is bool, "schema_additional_properties")
        properties, required = value.get("properties", {}), value.get("required", [])
        check(type(properties) is dict and len(properties) <= 32, "schema_properties")
        check(all(type(k) is str and FIELD.fullmatch(k) for k in properties), "schema_fields")
        check(
            type(required) is list
            and len(required) <= 32
            and all(type(k) is str for k in required)
            and len(set(required)) == len(required)
            and set(required) <= properties.keys(),
            "schema_required",
        )
        for child in properties.values():
            schema(child, depth + 1)
    elif kind == "array":
        allowed |= {"items", "minItems", "maxItems"}
        check(
            type(value.get("maxItems")) is int and 0 <= value["maxItems"] <= 256,
            "schema_array_bound",
        )
        check(
            type(value.get("minItems", 0)) is int
            and 0 <= value.get("minItems", 0) <= value["maxItems"],
            "schema_array_minimum",
        )
        schema(value.get("items"), depth + 1)
    elif kind == "string":
        allowed |= {"minLength", "maxLength"}
        check(
            type(value.get("maxLength")) is int and 0 <= value["maxLength"] <= 65536,
            "schema_string_bound",
        )
        check(
            type(value.get("minLength", 0)) is int
            and 0 <= value.get("minLength", 0) <= value["maxLength"],
            "schema_string_minimum",
        )
    elif kind in {"integer", "number"}:
        allowed |= {"minimum", "maximum"}
        for key in ("minimum", "maximum"):
            if key in value:
                check(
                    type(value[key]) in (int, float) and math.isfinite(value[key]),
                    "schema_numeric_bound",
                )
        if "minimum" in value and "maximum" in value:
            check(value["minimum"] <= value["maximum"], "schema_numeric_range")
    check(set(value) <= allowed, "schema_keyword_for_type")
    if "enum" in value:
        options = value["enum"]
        check(
            type(options) is list
            and 1 <= len(options) <= 32
            and kind in {"string", "number", "integer", "boolean"}
            and all(TYPES[kind](v) for v in options)
            # Duplicates are semantically equal but would hash differently.
            and len({json_bytes(v) for v in options}) == len(options),
            "schema_enum",
        )


def validate(value, contract, depth=0):
    check(depth <= 16 and TYPES[contract["type"]](value), "contract_type")
    if "enum" in contract:
        check(value in contract["enum"], "contract_enum")
    kind = contract["type"]
    if kind == "object":
        properties = contract.get("properties", {})
        check(set(contract.get("required", [])) <= value.keys(), "contract_required")
        check(
            contract["additionalProperties"] or set(value) <= properties.keys(),
            "contract_unknown_field",
        )
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], depth + 1)
    elif kind == "array":
        check(contract.get("minItems", 0) <= len(value) <= contract["maxItems"], "contract_items")
        for item in value:
            validate(item, contract["items"], depth + 1)
    elif kind == "string":
        check(
            contract.get("minLength", 0) <= len(value) <= contract["maxLength"],
            "contract_string_length",
        )
    elif kind in {"integer", "number"}:
        check(
            ("minimum" not in contract or value >= contract["minimum"])
            and ("maximum" not in contract or value <= contract["maximum"]),
            "contract_numeric_range",
        )


def json_bytes(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def canonical_schema(value):
    result = {key: canonical_schema(v) if isinstance(v, dict) else v for key, v in value.items()}
    for key in ("required", "enum"):
        if key in result:
            result[key] = sorted(result[key], key=lambda v: json_bytes(v))
    return result
