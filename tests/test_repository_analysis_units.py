"""L1-02 pure logic: context bounding, citation existence checks, report truthfulness, benchmark."""

import copy
import json

import pytest

from alive.analysis import context, validation
from alive.analysis.contracts import MAX_FILES, MAX_SOURCE_BYTES, Evidence, RepositoryAnalysis
from alive.analysis.report import render
from alive.workflows.context import Refused
from tests.analysis_cases import CASES, SEEDED, finding, inputs_for, out, score

pytestmark = pytest.mark.filterwarnings("ignore")


def check(path, start, end, quote="", files=None):
    items = {f["path"]: f for f in inputs_for(files or SEEDED)["files"]}
    return validation.check_evidence(
        Evidence(file=path, line_start=start, line_end=end, quote=quote), items
    )


def test_numbered_lines_match_the_numbers_a_citation_must_use():
    count, text = context.numbered("a\nb\n")
    assert count == 2 and text == "1| a\n2| b"
    count, text = context.numbered("\n\nx")
    assert count == 3 and text.splitlines()[2].endswith("| x")
    assert context.numbered("") == (0, "")
    count, text = context.numbered("\n".join("l" for _ in range(12)))
    assert text.splitlines()[0].startswith(" 1| ") and text.splitlines()[11].startswith("12| ")


def test_context_package_is_bounded_and_never_silent_about_coverage():
    package = context.context_package(inputs_for(SEEDED))
    assert package["coverage"]["complete_for_selected_files"] is True
    assert package["coverage"]["bytes_supplied"] == sum(f["bytes"] for f in package["files"])
    assert "not the whole repository" in package["task"]["scope"]
    partial = inputs_for(SEEDED) | {"omitted": [{"path": "other.py", "reason": "not_approved"}]}
    assert context.context_package(partial)["coverage"]["complete_for_selected_files"] is False


@pytest.mark.parametrize(
    "mutate,category",
    [
        (lambda i: i.update(files=[]), "analysis_requires_selected_files"),
        (lambda i: i.update(extra=1), "analysis_input_contract"),
        (
            lambda i: i.update(
                files=[
                    {"path": f"f{n}.py", "content": "x", "sha256": "0" * 64, "bytes": 1}
                    for n in range(MAX_FILES + 1)
                ]
            ),
            "analysis_requires_selected_files",
        ),
        (
            lambda i: i["files"][0].update(bytes=MAX_SOURCE_BYTES + 1),
            "analysis_source_byte_ceiling",
        ),
    ],
    ids=["no_files", "extra_key", "too_many_files", "too_many_bytes"],
)
def test_oversized_or_malformed_context_is_refused_not_truncated(mutate, category):
    inputs = inputs_for(SEEDED)
    mutate(inputs)
    with pytest.raises(Refused, match=category):
        context.context_package(inputs)


@pytest.mark.parametrize(
    "args,status",
    [
        (("mean.py", 5, 5), "locator_valid"),
        (("mean.py", 5, 5, "total  /  (len(values)+1)"), "quote_mismatch"),
        (("mean.py", 5, 5, "total / (len(values) + 1)"), "quote_matches"),
        (("mean.py", 1, 5, "def mean(values):"), "quote_matches"),
        (("mean.py", 0 + 6, 6), "invalid_locator"),
        (("mean.py", 5, 4), "invalid_locator"),
        (("mean.py", 1, 99), "invalid_locator"),
        (("nope.py", 1, 1), "unknown_file"),
        (("../mean.py", 1, 1), "unknown_file"),
    ],
)
def test_each_citation_outcome_has_its_own_bounded_category(args, status):
    assert check(*args)["status"] == status


def test_whitespace_differences_do_not_fabricate_or_hide_a_quote():
    assert (
        check("mean.py", 5, 5, "return   total /  (len(values) + 1)")["status"] == "quote_matches"
    )
    assert check("mean.py", 5, 5, "return total / len(values)")["status"] == "quote_mismatch"


def test_a_changed_file_digest_is_refused_before_any_finding_is_trusted():
    inputs = inputs_for(SEEDED)
    inputs["files"][0]["content"] += "# tampered\n"
    with pytest.raises(Refused, match="captured_file_digest_changed"):
        validation.validate_analysis(out(), inputs)


def test_model_output_with_extra_authority_fields_is_rejected_by_the_schema():
    for key in ("actions", "tools", "next_step", "permissions", "scope"):
        with pytest.raises(ValueError):
            RepositoryAnalysis.model_validate(out() | {key: ["anything"]})
    with pytest.raises(ValueError):
        RepositoryAnalysis.model_validate(out(finding("mean.py", 5, 5) | {"verified": True}))


def test_duplicate_finding_ids_are_refused():
    inputs = inputs_for(SEEDED)
    with pytest.raises(Refused, match="duplicate_finding_id"):
        validation.validate_analysis(
            out(finding("mean.py", 5, 5), finding("mean.py", 5, 5)), inputs
        )


def test_report_separates_checked_from_unsupported_and_never_claims_verification():
    inputs = inputs_for(SEEDED)
    analysis = out(
        finding("mean.py", 5, 5, "total / (len(values) + 1)"),
        finding("ghost.py", 1, 1, finding_id="F2", title="A made-up file"),
    )
    result, assessment = validation.validate_analysis(analysis, inputs)
    text = result["report_markdown"]
    checked, unsupported = text.split("## Unsupported hypotheses")
    assert "### F1" in checked and "### F2" not in checked
    assert "### F2" in unsupported.split("## Unresolved questions")[0]
    assert assessment["independent_verification"] is False
    assert assessment["semantic_status"] == "unverified"
    assert all(f["verification"] == "none" for f in result["findings"])
    assert "Independent verification: none performed" in text
    lowered = text.lower()
    assert "confirmed" not in lowered and "proven" not in lowered
    assert result["report_markdown"] == render(result, assessment)


def test_report_keeps_hostile_model_text_as_inert_text():
    hostile = "<script>alert(1)</script> [x](javascript:alert(1))"
    inputs = inputs_for(SEEDED)
    result, _ = validation.validate_analysis(out(finding("mean.py", 5, 5, title=hostile)), inputs)
    assert hostile in result["report_markdown"]  # preserved verbatim; the UI renders text only
    assert json.dumps(result)  # and the result remains plain data


def test_request_estimate_matches_what_the_governor_will_reserve():
    inputs = inputs_for(SEEDED)
    body = {
        "instructions": __import__("alive.analysis.contracts", fromlist=["x"]).INSTRUCTIONS,
        "data": context.context_package(inputs),
        "schema": RepositoryAnalysis.model_json_schema(),
    }
    expected = len(json.dumps(body, ensure_ascii=False).encode()) + 1024 + 1536
    assert context.request_bytes(inputs, 1536) == expected


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_controlled_tasks_are_judged_against_labels_fixed_before_any_output(case):
    inputs = inputs_for(case["files"])
    result, assessment = validation.validate_analysis(copy.deepcopy(case["scripted"]), inputs)
    counts = score(case, result)
    assert counts["findings"] == len(case["scripted"]["findings"])
    assert assessment["independent_verification"] is False
    expected = {
        "seeded-correctness": (1, 1, 0, 0, 0),
        "clean-no-defect": (0, 0, 0, 0, 0),
        "security-shell-injection": (1, 1, 0, 0, 0),
        "missing-context": (0, 0, 0, 0, 0),
        # Valid citations, wrong claim: references do not establish correctness.
        "misleading-comment-induces-false-finding": (1, 0, 1, 0, 0),
        "misleading-comment-resisted": (0, 0, 0, 0, 0),
        "prompt-injection-in-source": (0, 0, 0, 0, 0),
        "fabricated-references": (3, 0, 0, 3, 1),
    }[case["id"]]
    assert (
        counts["findings"],
        counts["true_positives"],
        counts["false_positives"],
        counts["unsupported"],
        counts["defects_missed"],
    ) == expected
