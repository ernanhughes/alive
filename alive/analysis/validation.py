"""Independent checks of a model's citations against the captured files.

These establish only that a cited file, line range and quotation exist in the approved capture.
They do not establish that the model's claim is true; no finding is ever marked verified.
"""

import hashlib
import re

from alive.analysis.contracts import RepositoryAnalysis
from alive.workflows.context import digest, require

REFERENCE_CONTRACT = "repository-citation-existence/v1"


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def check_evidence(evidence, files):
    """Every outcome is a distinct bounded category."""
    source = files.get(evidence.file)
    if source is None:
        return {"status": "unknown_file", "file": evidence.file}
    lines = source["content"].split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not 1 <= evidence.line_start <= evidence.line_end <= len(lines):
        return {"status": "invalid_locator", "file": evidence.file, "line_count": len(lines)}
    base = {
        "file": evidence.file,
        "file_sha256": source["sha256"],
        "line_start": evidence.line_start,
        "line_end": evidence.line_end,
    }
    if evidence.quote:
        cited = squash(" ".join(lines[evidence.line_start - 1 : evidence.line_end]))
        if squash(evidence.quote) not in cited:
            return base | {"status": "quote_mismatch"}
        return base | {"status": "quote_matches"}
    return base | {"status": "locator_valid", "quote_checked": False}


OK = {"quote_matches", "locator_valid"}


def validate_analysis(analysis, inputs):
    """Return (result, assessment) shaped for the existing result.record dependency contract."""
    parsed = RepositoryAnalysis.model_validate(analysis)
    files = {}
    for item in inputs["files"]:
        require(
            hashlib.sha256(item["content"].encode("utf-8")).hexdigest() == item["sha256"],
            "captured_file_digest_changed",
        )
        files[item["path"]] = item
    findings = []
    for finding in parsed.findings:
        checks = [check_evidence(e, files) for e in finding.evidence]
        supported = all(c["status"] in OK for c in checks)
        findings.append(
            {
                "finding_id": finding.finding_id,
                "model_assessment": finding.model_dump(mode="json", exclude={"finding_id"}),
                "reference_check": {
                    "contract": REFERENCE_CONTRACT,
                    "status": "references_valid" if supported else "unsupported_reference",
                    "evidence": checks,
                },
                "verification": "none",
            }
        )
    ids = [f["finding_id"] for f in findings]
    require(len(set(ids)) == len(ids), "duplicate_finding_id")
    valid = sum(f["reference_check"]["status"] == "references_valid" for f in findings)
    result = {
        "schema": "repository-analysis-result/v1",
        "objective": inputs["objective"],
        "source": {
            "source_ref": inputs["source_ref"],
            "source_sha256": inputs["source_sha256"],
            "scoped_sha256": inputs["scoped_sha256"],
            "files": [
                {"path": f["path"], "sha256": f["sha256"], "bytes": f["bytes"]}
                for f in inputs["files"]
            ],
            "omitted": inputs["omitted"],
        },
        "summary": parsed.summary,
        "findings": findings,
        "unresolved_questions": parsed.unresolved_questions,
        "analysis_sha256": digest(parsed.model_dump(mode="json")),
    }
    assessment = {
        "contract": REFERENCE_CONTRACT,
        "reference_identity_status": "all_valid" if valid == len(findings) else "some_unsupported",
        "findings_total": len(findings),
        "findings_with_valid_references": valid,
        "findings_with_unsupported_references": len(findings) - valid,
        "semantic_status": "unverified",
        "independent_verification": False,
    }
    from alive.analysis.report import render

    result["report_markdown"] = render(result, assessment)
    return result, assessment
