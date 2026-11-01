"""Deterministic completeness and non-overwriting patches; never executes supplied code."""

from collections import Counter
from copy import deepcopy

from pydantic import TypeAdapter, ValidationError

from alive.analysis.validation import OK, check_evidence
from alive.task_review.contracts import Case, Repair, Review, Value, parse_json
from alive.workflows.context import digest


def validate(candidate, contract, files, items):
    data = candidate if isinstance(candidate, dict) else {}
    errors, accepted = [], {}

    def error(field, code, **details):
        errors.append({"field": field, "code": code, **details})

    try:
        Review.model_validate(candidate)
        schema_valid = True
    except ValidationError:
        schema_valid = False
    for name, spec in Review.model_fields.items():
        if name not in data:
            error(name, "missing_field")
            continue
        if name == "predictions":
            continue
        try:
            TypeAdapter(spec.rebuild_annotation()).validate_python(data[name], strict=True)
        except ValidationError:
            error(name, "malformed_field")
            continue
        accepted[name] = deepcopy(data[name])
    for name in data.keys() - Review.model_fields.keys():
        error(name, "unexpected_field")
    for name, expected in (("contract_version", 1), ("contract_sha256", contract["sha256"])):
        if name in accepted and (type(data[name]) is not type(expected) or data[name] != expected):
            accepted.pop(name)
            error(name, "contract_mismatch")
    declared = contract["case_ids"]
    rows = data.get("predictions")
    valid_cases = {}
    if not isinstance(rows, list) or len(rows) > 8:
        if "predictions" in data:
            error("predictions", "malformed_field")
        rows = []
    counts = Counter(
        r.get("case_id") for r in rows if isinstance(r, dict) and isinstance(r.get("case_id"), str)
    )
    for ref in declared:
        if ref not in counts:
            error("predictions", "missing_case", case_id=ref)
    for ref, count in counts.items():
        if ref not in declared:
            error("predictions", "unexpected_case", case_id=ref)
        if count > 1:
            error("predictions", "duplicate_case", case_id=ref)
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
            error("predictions", "malformed_case")
            continue
        ref = row["case_id"]
        if ref not in declared or counts[ref] != 1:
            continue
        kept = {"case_id": ref}
        for name in ("observed", "required"):
            try:
                value = TypeAdapter(Value).validate_python(row.get(name), strict=True)
                if value.status == "predicted":
                    text = value.value
                    if text.startswith("ERROR:"):
                        if not text[6:].isidentifier():
                            raise ValueError()
                    else:
                        parse_json(text)
                kept[name] = deepcopy(row[name])
            except (ValidationError, ValueError):
                error("predictions", "malformed_prediction", case_id=ref, part=name)
        if row.keys() - Case.model_fields.keys():
            error("predictions", "unexpected_case_field", case_id=ref)
        valid_cases[ref] = kept
    allowed_ids = {i["id"] for i in items}
    valid_refs = []
    for ref in accepted.get("reference_ids", []):
        if ref not in allowed_ids:
            error("reference_ids", "reference_not_supplied", reference=ref)
        else:
            valid_refs.append(ref)
    if "reference_ids" in accepted:
        accepted["reference_ids"] = valid_refs
    valid_citations = []
    for citation in accepted.get("citations", []):
        from alive.analysis.contracts import Evidence

        if check_evidence(Evidence.model_validate(citation), files)["status"] not in OK:
            error("citations", "unsupported_reference", reference=citation)
        else:
            valid_citations.append(citation)
    if "citations" in accepted:
        accepted["citations"] = valid_citations
    if files and accepted.get("defect", {}).get("status") == "determined" and not valid_citations:
        error("citations", "missing_evidence_reference")
    accepted["predictions"] = valid_cases
    unknown = any(
        v.get("status") == "undetermined"
        for c in valid_cases.values()
        for v in (c.get("observed", {}), c.get("required", {}))
    )
    unknown |= (
        data.get("defect", {}).get("status") == "undetermined"
        if isinstance(data.get("defect"), dict)
        else False
    )
    return {
        "schema_valid": schema_valid,
        "task_complete": not errors and schema_valid,
        "semantically_verified": False,
        "semantic_status": "unverified",
        "all_cases_addressed": set(valid_cases) == set(declared)
        and all(len(c) == 3 for c in valid_cases.values())
        and not any(
            e["code"] in ("duplicate_case", "unexpected_case", "malformed_case") for e in errors
        ),
        "contains_undetermined": bool(unknown),
        "errors": errors,
        "accepted": accepted,
        "allowed_repair_fields": sorted({e["field"] for e in errors}),
    }


def patch(original, repair, contract, files, items, *, original_sha256=None):
    before = validate(original, contract, files, items)

    def check(condition):
        if not condition:
            raise ValueError("repair_conflict")

    try:
        parsed = Repair.model_validate(repair)
        check(parsed.contract_sha256 == contract["sha256"])
        check(parsed.original_sha256 == (original_sha256 or digest(original)))
        check(set(parsed.changes) <= set(before["allowed_repair_fields"]))
        merged = deepcopy(original) if isinstance(original, dict) else {}
        for key, value in parsed.changes.items():
            if key not in Review.model_fields and value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        after = validate(merged, contract, files, items)
        for name, kept in before["accepted"].items():
            if name == "predictions":
                for ref, fields in kept.items():
                    new = after["accepted"][name].get(ref, {})
                    check(all(new.get(k) == v for k, v in fields.items()))
            elif name in ("citations", "reference_ids"):
                check(all(v in merged.get(name, []) for v in kept))
            else:
                check(merged.get(name) == kept)
        return merged, after, None
    except (ValidationError, ValueError, TypeError, KeyError):
        return original, before, "repair_refused_identity_or_accepted_content_changed"
