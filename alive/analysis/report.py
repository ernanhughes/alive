"""Human-readable report from the validated structure only. Rendered as text, never as markup."""


def _lines(items, empty):
    return items or [empty]


def render(result, assessment):
    supported = [
        f for f in result["findings"] if f["reference_check"]["status"] == "references_valid"
    ]
    unsupported = [f for f in result["findings"] if f not in supported]
    out = [
        "# Repository analysis",
        "",
        "## Investigation objective",
        result["objective"],
        "",
        "## Approved source scope",
        f"Source {result['source']['source_ref']} (digest {result['source']['source_sha256']}).",
        "Files supplied to the model: "
        + (", ".join(f["path"] for f in result["source"]["files"]) or "none")
        + ".",
        "Omitted: "
        + (", ".join(f"{o['path']} ({o['reason']})" for o in result["source"]["omitted"]) or "none")
        + ".",
        "This analysis covers only those files, not the whole repository.",
        "",
        "## Model summary (model assessment, not verified)",
        result["summary"] or "The model provided no summary.",
        "",
        "## Findings whose citations exist in the captured files",
    ]
    out += _lines([], "No findings with valid citations.") if not supported else []
    for f in supported:
        out += finding_lines(f)
    out += ["", "## Unsupported hypotheses (a citation did not match the captured files)"]
    out += _lines([], "None.") if not unsupported else []
    for f in unsupported:
        out += finding_lines(f)
    out += ["", "## Unresolved questions"]
    out += [f"- {q}" for q in _lines(result["unresolved_questions"], "None stated.")]
    out += [
        "",
        "## Validation status",
        f"Citation existence: {assessment['findings_with_valid_references']} of "
        f"{assessment['findings_total']} findings have citations that match the captured files.",
        "A matching citation shows the cited lines exist. It does not show the model is right.",
        "Independent verification: none performed. Semantic status: unverified.",
    ]
    return "\n".join(out)


def finding_lines(f):
    m = f["model_assessment"]
    out = [
        "",
        f"### {f['finding_id']}: {m['title']}",
        f"Model-assessed severity: {m['severity']}; category: {m['category']}.",
        m["explanation"],
        "Evidence:",
    ]
    for c in f["reference_check"]["evidence"]:
        if "line_start" in c:
            out.append(f"- {c['file']}:{c['line_start']}-{c['line_end']} ({c['status']})")
        else:
            out.append(f"- {c['file']} ({c['status']})")
    out.append(f"Uncertainty: {m['uncertainty'] or 'not stated'}")
    out.append(f"Suggested verification: {m['suggested_verification'] or 'not stated'}")
    return out
