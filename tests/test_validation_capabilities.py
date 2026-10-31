"""Controlled evidence, refusal controls and exact taxonomy for PI-03C primitives."""

import asyncio
import copy
import json
from types import SimpleNamespace as NS

import pytest
from pydantic import ValidationError

from alive.sources.custody import ApprovedSource
from alive.validation import adapters
from alive.workflows.context import Refused


def source(text="alpha\r\nbeta\n", *, kind="repository", ref="a" * 36):
    digest = adapters.sha(text)
    if kind == "repository":
        content = {"files": [{"path": "a.py", "content": text, "sha256": digest}], "omitted": []}
    elif kind in {"document", "browser"}:
        content = {
            "sections": [{"index": 0, "text": text, "sha256": digest, "truncated": False}],
            "omitted": [],
            "truncated": False,
        }
    else:
        content = {
            "items": [{"memory_id": "memory-a", "content": text, "content_sha256": digest}],
            "omitted": [],
        }
    blob = json.dumps(content).encode()
    return ApprovedSource(
        ref,
        "approval",
        kind,
        "Synthetic",
        "owner_internal",
        adapters.sha(blob.decode()),
        "b" * 64,
        "c" * 64,
        "2026-01-01T00:00:00Z",
        "2099-01-01T00:00:00Z",
        blob,
    )


def inputs(capture, *, locator="file_lines", start=1, end=2, quote="alpha\nbeta"):
    item = (
        "a.py"
        if capture.source_type == "repository"
        else "0"
        if capture.source_type in {"document", "browser"}
        else "memory-a"
    )
    entry = adapters.index(capture)[item]
    return {
        "source_ref": capture.source_ref,
        "source_sha256": capture.content_sha256,
        "scoped_sha256": capture.scoped_sha256,
        "findings": [
            {
                "id": "F1",
                "claim": "An unverified claim",
                "evidence": [
                    {
                        "id": entry["id"],
                        "item": item,
                        "sha256": entry["sha256"],
                        "locator": {"kind": locator, "start": start, "end": end, "quote": quote},
                    }
                ],
            }
        ],
    }


def ctx(capture, data=None):
    return NS(
        resources=capture,
        inputs=data or inputs(capture),
        limits={"max_source_bytes": 65536, "max_files": 64},
    )


def run(capture, data=None, *, locate=True):
    result = asyncio.run((adapters.locators if locate else adapters.references)(ctx(capture, data)))
    return result.output["records"]


def dependency(records, implementation=adapters.LOCATOR_IMPL):
    return {
        "implementation": implementation,
        "validation_status": "passed",
        "output": {"records": records},
    }


def compose(records, *, actual=None):
    return asyncio.run(
        adapters.compose(
            NS(
                inputs={"records": records},
                dependencies={
                    "validate": dependency(records if actual is None else actual),
                },
            )
        )
    )


def test_exact_capture_locator_does_not_establish_semantics_or_outcome():
    captured = source()
    records = run(captured)
    assert records["findings"][0]["evidence"][0]["locator_status"] == "quote_matches"
    assert records["findings"][0]["evidence"][0]["reference_status"] == "identity_valid"
    assert records["validation"] == adapters.taxonomy()
    assert records["validation"]["semantic_support"] == "unverified"
    assert records["validation"]["independent_verification"] is False
    assert records["validation"]["task_outcome"] == "unknown"
    report = compose(records).output
    assert report["result"]["records"] == records
    assert "An unverified claim" in report["result"]["report_markdown"]
    assert "Omitted evidence:" in report["result"]["report_markdown"]


@pytest.mark.parametrize("field", ["source_ref", "source_sha256", "scoped_sha256"])
def test_source_substitution_is_refused_after_successful_control(field):
    captured = source()
    assert run(captured)["findings"]
    data = inputs(captured)
    data[field] = "f" * len(data[field])
    with pytest.raises(Refused, match="validation_source_identity"):
        run(captured, data)


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("id", "", "missing_reference"),
        ("id", "fabricated", "unknown_reference"),
        ("item", "ghost.py", "unknown_reference"),
        ("sha256", "0" * 64, "hash_mismatch"),
    ],
)
def test_each_reference_failure_is_classified(field, value, status):
    captured = source()
    data = inputs(captured)
    data["findings"][0]["evidence"][0][field] = value
    result = run(captured, data)
    assert result["findings"][0]["evidence"][0]["reference_status"] == status
    assert result["observations"] == []


@pytest.mark.parametrize(
    "kind,start,end,quote,expected",
    [
        ("file_lines", 0, 1, "", "invalid_locator"),
        ("file_lines", 2, 1, "", "invalid_locator"),
        ("file_lines", 1, 99, "", "invalid_locator"),
        ("file_lines", 1, 2, "alpha beta", "quote_mismatch"),
        ("file_lines", 1, 2, "alpha\r\nbeta", "quote_matches"),
        ("file_lines", 1, 1, "", "locator_valid"),
        ("text_span", 0, 5, "alpha", "quote_matches"),
        ("text_span", 0, 100, "", "invalid_locator"),
        ("page", 1, 1, "", "unsupported_locator_kind"),
        ("none", 0, 0, "", "missing_locator"),
    ],
)
def test_locator_bounds_newlines_exact_quotes_and_unsupported_pages(
    kind, start, end, quote, expected
):
    captured = source()
    data = inputs(captured, locator=kind, start=start, end=end, quote=quote)
    result = run(captured, data)
    assert result["findings"][0]["evidence"][0]["locator_status"] == expected
    if expected not in {"quote_matches", "locator_valid"}:
        assert result["observations"] == []


@pytest.mark.parametrize("kind", ["document", "browser", "collection"])
def test_existing_source_identities_are_reused_without_filesystem_or_page_invention(kind):
    captured = source(kind=kind)
    data = inputs(
        captured,
        locator="section" if kind != "collection" else "text_span",
        start=0,
        end=0 if kind != "collection" else 5,
        quote="alpha",
    )
    result = run(captured, data)
    assert result["findings"][0]["evidence"][0]["locator_status"] == "quote_matches"
    data["findings"][0]["evidence"][0]["locator"]["kind"] = "page"
    assert (
        run(captured, data)["findings"][0]["evidence"][0]["locator_status"]
        == "unsupported_locator_kind"
    )


def test_duplicate_ids_missing_evidence_and_paths_are_explicit():
    captured = source()
    data = inputs(captured)
    data["findings"][0]["evidence"] *= 2
    assert (
        run(captured, data)["findings"][0]["evidence"][1]["reference_status"]
        == "duplicate_reference"
    )
    data["findings"][0]["evidence"] = []
    assert run(captured, data)["findings"][0]["missing_evidence"] is True
    data["findings"] *= 2
    with pytest.raises(Refused, match="duplicate_finding_id"):
        run(captured, data)
    data = inputs(captured)
    data["findings"][0]["evidence"][0]["item"] = "../outside.py"
    with pytest.raises(ValueError):
        run(captured, data)


def test_contract_and_source_byte_limits_cannot_be_widened():
    captured = source()
    data = inputs(captured)
    data["findings"][0]["verified"] = True
    with pytest.raises(ValidationError):
        run(captured, data)
    with pytest.raises(Refused, match="validation_source_byte_limit"):
        asyncio.run(
            adapters.references(
                NS(
                    resources=captured,
                    inputs=inputs(captured),
                    limits={"max_source_bytes": 1, "max_files": 64},
                )
            )
        )


def test_capture_item_hash_and_bounded_observation_are_not_silently_truncated():
    captured = source("x" * 1000)
    records = run(captured, inputs(captured, locator="none", quote=""), locate=False)
    assert records["observations"][0]["truncated"] is True
    assert len(records["observations"][0]["text"]) == 512
    from dataclasses import replace

    content = captured.content
    content["files"][0]["sha256"] = "0" * 64
    fake = replace(captured, blob=json.dumps(content).encode())
    with pytest.raises(Refused, match="captured_item_hash_mismatch"):
        adapters.index(fake)


def comparison(a, b, mode="exact", fields=None, *, dependencies=None):
    return asyncio.run(
        adapters.compare(
            NS(
                inputs={
                    "left": a,
                    "right": b,
                    "left_id": a["observations"][0]["id"],
                    "right_id": b["observations"][0]["id"],
                    "mode": mode,
                    "fields": fields or [],
                },
                dependencies=dependencies or {"a": dependency(a), "b": dependency(b)},
            )
        )
    ).output["records"]


@pytest.mark.parametrize(
    "left,right,mode,fields,status",
    [
        ("same", "same", "exact", [], "equal"),
        ("a", "b", "exact", [], "different"),
        ("a", "b", "changed", [], "changed"),
        ("a", "a", "changed", [], "unchanged"),
        ('{"a":1,"b":2}', '{"b":2,"a":1}', "normalized_fields", ["a", "b"], "equal"),
        ('{"a":true}', '{"a":1}', "normalized_fields", ["a"], "different"),
        ('{"a":NaN}', '{"a":null}', "normalized_fields", ["a"], "not_comparable"),
        ('{"a":1,"a":2}', '{"a":2}', "normalized_fields", ["a"], "not_comparable"),
    ],
)
def test_controlled_comparison_is_not_semantic_entailment(left, right, mode, fields, status):
    a, b = source(left), source(right, ref="b" * 36)
    first = run(a, inputs(a, locator="none", quote=""), locate=False)
    second = run(b, inputs(b, locator="none", quote=""), locate=False)
    result = comparison(first, second, mode, fields)
    assert result["comparison"]["status"] == status
    assert result["validation"] == adapters.taxonomy()
    assert result["sources"] == [first["source"], second["source"]]
    assert result["compared_findings"] == {"left": first["findings"], "right": second["findings"]}


def test_composer_and_comparison_refuse_self_certification_with_live_controls():
    records = run(source())
    assert compose(records).validation_status == "passed"
    forged = copy.deepcopy(records)
    forged["validation"]["semantic_support"] = "verified"
    with pytest.raises(Refused, match="trusted_validation_dependency_required"):
        compose(forged, actual=records)
    with pytest.raises(Refused, match="trusted_validation_dependency_required"):
        comparison(
            records,
            records,
            dependencies={
                "fake": {
                    "implementation": "cognition-role-v1",
                    "validation_status": "passed",
                    "output": {"records": records},
                }
            },
        )


def test_a_false_claim_with_a_valid_citation_remains_unverified():
    captured = source("answer = 1\n")
    data = inputs(captured, start=1, end=1, quote="answer = 1")
    data["findings"][0]["claim"] = "This assigns answer the value 99."
    records = run(captured, data)
    assert records["findings"][0]["evidence"][0]["locator_status"] == "quote_matches"
    report = compose(records).output
    assert report["assessment"]["semantic_support"] == "unverified"
    assert report["assessment"]["independent_verification"] is False
    assert report["assessment"]["task_outcome"] == "unknown"


def test_lowered_repository_file_ceiling_is_enforced_with_a_live_control():
    captured = source()
    assert run(captured)["findings"]
    request = ctx(captured)
    request.limits["max_files"] = 0
    with pytest.raises(Refused, match="validation_file_limit"):
        asyncio.run(adapters.references(request))


@pytest.mark.parametrize("field", ["locator", "verification"])
def test_dependency_identity_distinguishes_json_booleans_and_numbers(field):
    records = run(source())
    assert compose(records).validation_status == "passed"
    forged = copy.deepcopy(records)
    if field == "locator":
        forged["findings"][0]["evidence"][0]["locator"]["start"] = True
    else:
        forged["validation"]["independent_verification"] = 0
    with pytest.raises(Refused, match="trusted_validation_dependency_required"):
        compose(forged, actual=records)
