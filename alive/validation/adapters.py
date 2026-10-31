"""PI-03C adapters over custody-checked captures and actual trusted stage dependencies."""

import hashlib
import json
import math

from alive.analysis.contracts import Evidence
from alive.analysis.validation import check_evidence
from alive.capabilities.repository import relative_path
from alive.capabilities.source_adapters import provenance, source_id
from alive.validation.contracts import Batch
from alive.workflows.adapters import StageResult
from alive.workflows.context import require

REFERENCE_IMPL = "captured-references-v1"
LOCATOR_IMPL = "captured-locators-v1"
COMPARE_IMPL = "captured-claims-compare-v1"
VALIDATORS = frozenset({REFERENCE_IMPL, LOCATOR_IMPL, COMPARE_IMPL})
OBSERVATION_CHARS = 512


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def newline(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def taxonomy():
    return {
        "contract": "valid",
        "structural": "valid",
        "semantic_support": "unverified",
        "independent_verification": False,
        "task_outcome": "unknown",
    }


def index(source):
    content = source.content
    if source.source_type == "repository":
        entries = [(f["path"], f["content"], f["sha256"], False) for f in content["files"]]
    elif source.source_type in {"document", "browser"}:
        entries = [
            (str(s["index"]), s["text"], s["sha256"], s["truncated"]) for s in content["sections"]
        ]
    elif source.source_type == "collection":
        entries = [
            (i["memory_id"], i["content"], i["content_sha256"], False) for i in content["items"]
        ]
    else:
        raise ValueError("unsupported_validation_source")
    require(len({e[0] for e in entries}) == len(entries), "duplicate_captured_item")
    require(
        all(sha(text) == digest for _, text, digest, _ in entries), "captured_item_hash_mismatch"
    )
    return {
        key: {
            "text": text,
            "sha256": digest,
            "truncated": cut,
            "id": source_id(source, key, digest),
        }
        for key, text, digest, cut in entries
    }


def locate(reference, item, source_type):
    locator = reference.locator
    text = newline(item["text"])
    if locator.kind == "none":
        return "missing_locator", None
    if locator.kind == "page":
        return "unsupported_locator_kind", None  # no approved capture has page coordinates
    if locator.kind == "file_lines":
        if source_type != "repository":
            return "unsupported_locator_kind", None
        if not 1 <= locator.start <= locator.end:
            return "invalid_locator", None
        # Reuse the existing line-bound implementation; retain L1-02's quotation policy unchanged.
        checked = check_evidence(
            Evidence(file=reference.item, line_start=locator.start, line_end=locator.end, quote=""),
            {
                reference.item: {"content": text, "sha256": item["sha256"]},
            },
        )
        if checked["status"] != "locator_valid":
            return "invalid_locator", None
        selected = "\n".join(text.split("\n")[locator.start - 1 : locator.end])
    elif locator.kind == "section":
        if source_type not in {"document", "browser"}:
            return "unsupported_locator_kind", None
        if locator.start != int(reference.item) or locator.end != locator.start:
            return "invalid_locator", None
        selected = text
    else:
        if not 0 <= locator.start < locator.end <= len(text):
            return "invalid_locator", None
        selected = text[locator.start : locator.end]
    if locator.quote and newline(locator.quote) not in selected:
        return "quote_mismatch", None
    return ("quote_matches" if locator.quote else "locator_valid"), selected


def assess(ctx, *, locators):
    batch = Batch.model_validate(ctx.inputs)
    source = ctx.resources
    require(
        source is not None
        and batch.source_ref == source.source_ref
        and batch.source_sha256 == source.content_sha256
        and batch.scoped_sha256 == source.scoped_sha256,
        "validation_source_identity",
    )
    require(len(source.blob) <= ctx.limits["max_source_bytes"], "validation_source_byte_limit")
    require(len({f.id for f in batch.findings}) == len(batch.findings), "duplicate_finding_id")
    items = index(source)
    findings, observations = [], {}
    for finding in batch.findings:
        checked, used = [], set()
        for ref in finding.evidence:
            if source.source_type == "repository":
                relative_path(ref.item)  # refuses traversal rather than normalizing it into scope
            item = items.get(ref.item)
            status = (
                "missing_reference"
                if not ref.id
                else "duplicate_reference"
                if ref.id in used
                else "unknown_reference"
                if item is None or ref.id != item["id"]
                else "hash_mismatch"
                if ref.sha256 != item["sha256"]
                else "identity_valid"
            )
            used.add(ref.id)
            locator_status, selected = ("not_run", None)
            if status == "identity_valid":
                if locators:
                    locator_status, selected = locate(ref, item, source.source_type)
                # Full captured identity may be compared by hash even if the display is bounded.
                text = item["text"] if selected is None else selected
                if not locators or selected is not None:
                    observations[ref.id] = {
                        "id": ref.id,
                        "item": ref.item,
                        "sha256": item["sha256"],
                        "text": text[:OBSERVATION_CHARS],
                        "text_sha256": sha(text),
                        "truncated": item["truncated"] or len(text) > OBSERVATION_CHARS,
                        "locator_status": locator_status,
                    }
            checked.append(
                ref.model_dump() | {"reference_status": status, "locator_status": locator_status}
            )
        findings.append(
            {
                "id": finding.id,
                "claim": finding.claim,
                "evidence": checked,
                "missing_evidence": not checked,
            }
        )
    content = source.content
    records = {
        "schema": "captured-validation/v1",
        "procedure": "locators" if locators else "references",
        "source": {
            "source_ref": source.source_ref,
            "source_sha256": source.content_sha256,
            "scoped_sha256": source.scoped_sha256,
            "scope_sha256": source.scope_sha256,
            "approval_id": source.approval_id,
            "source_type": source.source_type,
        },
        "findings": findings,
        "observations": list(observations.values()),
        "omitted": content.get("omitted", []),
        "truncated_at_capture": content.get("truncated", False),
        "provenance": provenance(source),
        "validation": taxonomy(),
        "newline_policy": "CRLF_and_CR_to_LF_for_locators;_hashes_cover_original_capture",
        "quote_policy": "exact_substring_after_newline_normalization;_no_whitespace_squashing",
    }
    return StageResult({"records": records}, tuple(observations), "passed")


async def references(ctx):
    return assess(ctx, locators=False)


async def locators(ctx):
    return assess(ctx, locators=True)


def trusted_records(ctx, value, implementations=VALIDATORS):
    require(
        any(
            entry["implementation"] in implementations
            and entry["validation_status"] == "passed"
            and entry["output"] == {"records": value}
            for entry in ctx.dependencies.values()
        ),
        "trusted_validation_dependency_required",
    )
    require(
        value.get("schema") == "captured-validation/v1" and value["validation"] == taxonomy(),
        "validation_status_changed",
    )


def observation(records, identifier):
    values = [v for v in records["observations"] if v["id"] == identifier]
    require(len(values) == 1, "comparison_reference_unresolved")
    return values[0]


def fields(text, names):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate_comparison_field")
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("nonfinite_comparison_value")

    parsed = json.loads(text, object_pairs_hook=unique, parse_constant=reject_constant)
    require(
        type(parsed) is dict
        and names
        and len(set(names)) == len(names)
        and all(name in parsed for name in names),
        "comparison_field_missing",
    )
    values = [parsed[name] for name in names]
    require(
        all(
            (type(v) in (str, int, float, bool) or v is None)
            and (type(v) is not float or math.isfinite(v))
            for v in values
        ),
        "comparison_field_type",
    )
    return [(type(v).__name__, v) for v in values]  # True and 1 are distinct exact values


async def compare(ctx):
    inputs = ctx.inputs
    left, right = inputs["left"], inputs["right"]
    for records in (left, right):
        trusted_records(ctx, records, {REFERENCE_IMPL, LOCATOR_IMPL})
    a, b = observation(left, inputs["left_id"]), observation(right, inputs["right_id"])
    mode, status = inputs["mode"], "not_comparable"
    require(mode == "normalized_fields" or inputs["fields"] == [], "unexpected_comparison_fields")
    if mode in {"exact", "changed"}:
        key = "sha256" if mode == "changed" else "text_sha256"
        equal = a[key] == b[key]
        status = (
            ("unchanged" if equal else "changed")
            if mode == "changed"
            else ("equal" if equal else "different")
        )
    elif not a["truncated"] and not b["truncated"]:
        if mode == "text_span":
            if all(v["locator_status"] in {"quote_matches", "locator_valid"} for v in (a, b)):
                status = "equal" if a["text"] == b["text"] else "different"
        else:
            try:
                status = (
                    "equal"
                    if fields(a["text"], inputs["fields"]) == fields(b["text"], inputs["fields"])
                    else "different"
                )
            except (ValueError, TypeError):
                status = "not_comparable"
    records = {
        "schema": "captured-validation/v1",
        "procedure": "controlled-comparison/v1",
        "sources": [left["source"], right["source"]],
        "findings": [],
        "observations": [a, b],
        "comparison": {
            "mode": mode,
            "fields": inputs["fields"],
            "status": status,
            "left_id": a["id"],
            "right_id": b["id"],
        },
        "omitted": left["omitted"] + right["omitted"],
        "truncated_at_capture": left["truncated_at_capture"] or right["truncated_at_capture"],
        "provenance": [left["provenance"], right["provenance"]],
        "validation": taxonomy(),
    }
    return StageResult({"records": records}, (a["id"], b["id"]), "passed")


async def compose(ctx):
    records = ctx.inputs["records"]
    trusted_records(ctx, records)
    lines = [
        "# Evidence report",
        "",
        "Semantic support: unverified. Independent verification: none. Task outcome: unknown.",
    ]
    for finding in records["findings"]:
        lines += [f"\n## {finding['id']}", finding["claim"]]
        if finding["missing_evidence"]:
            lines.append("Missing evidence.")
        for ref in finding["evidence"]:
            lines.append(
                f"- {ref['item']}: {ref['reference_status']}; locator: {ref['locator_status']}"
            )
    if "comparison" in records:
        lines.append(
            "\nControlled comparison: " + json.dumps(records["comparison"], sort_keys=True)
        )
    for value in records["observations"]:
        if value["truncated"]:
            lines.append("Displayed evidence truncated: " + value["id"])
    lines.append(f"\nOmitted evidence: {json.dumps(records['omitted'], sort_keys=True)}")
    lines.append(f"Truncated at capture: {records['truncated_at_capture']}")
    report = "\n".join(lines)
    require(len(report.encode()) <= 16384, "validation_report_byte_limit")
    result = {"records": records, "report_markdown": report}
    return StageResult(
        {"result": result, "assessment": taxonomy() | {"contract": "captured-report/v1"}},
        tuple(v["id"] for v in records["observations"]),
        "passed",
    )
