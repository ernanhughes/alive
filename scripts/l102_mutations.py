# ruff: noqa: E501  (mutation patterns are exact source text)
"""L1-02 mutation receipts: break one authority guard at a time and require a behavioural kill.

A kill is a test FAILURE caused by the mutant. A collection or setup error is `invalid`, never a
kill. Guards that are deliberately redundant (a second layer catches the same case) are reported
as `survived` with the reason, not hidden.

    uv run python scripts/l102_mutations.py [id ...]
"""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CTX = "alive/workflows/context.py"
RUN = "alive/workflows/runner.py"
SVC = "alive/admission/service.py"
PRO = "alive/admission/profiles.py"
API = "alive/admission/api.py"
ADP = "alive/analysis/adapters.py"
VAL = "alive/analysis/validation.py"
COG = "alive/cognition.py"
CON = "alive/analysis/context.py"
# (id, file, old text, new text, guard)
MUTANTS = [
    (
        "M01",
        CTX,
        "        grant.outbound_approved\n        and grant.models.get(role) == model\n",
        "        True\n        and grant.models.get(role) == model\n",
        "reservation: outbound approval",
    ),
    (
        "M02",
        CTX,
        "        and grant.models.get(role) == model\n        and grant.role_contracts",
        "        and grant.role_contracts",
        "reservation: approved model identity",
    ),
    (
        "M03",
        CTX,
        "        == (role_contract(role) if analysis is None else analysis.contract)\n",
        "        == grant.role_contracts.get(role)\n",
        "reservation: role contract",
    ),
    (
        "M04",
        CTX,
        "        and context == (approved if analysis is None else analysis.context_for(analysis.inputs))\n",
        "",
        "reservation: exact context",
    ),
    (
        "M05",
        CTX,
        '        == ("cognition-role-v1" if analysis is None else analysis.implementation_id)\n',
        '        == capability["identity"]["implementation_id"]\n',
        "reservation: implementation identity",
    ),
    (
        "M06",
        CTX,
        '        stage.input_sha256\n        == digest({"role": role, "context": context} if analysis is None else analysis.inputs),\n',
        "        True,\n",
        "reservation: stage input hash",
    ),
    (
        "M07",
        RUN,
        '        stored["instructions"] == INSTRUCTIONS\n        and ',
        "        True\n        and ",
        "fence: instructions",
    ),
    (
        "M08",
        RUN,
        '        and stored.get("context_sha256") == digest(stored["context"])\n',
        "",
        "fence: context digest",
    ),
    (
        "M09",
        RUN,
        '        and stored["context"]["source"]["source_sha256"] == resources["content_sha256"]\n',
        "",
        "fence: source digest",
    ),
    (
        "M10",
        SVC,
        "    for operation in profile.source_operations:\n        source = await custody.resolve(kernel, resources, operation)\n",
        '    source = await custody.resolve(kernel, resources, "repository.inspect")\n',
        "prepare: disclosure operation approved",
    ),
    (
        "M11",
        SVC,
        '        require(\n            current == terms["model_disclosure"]\n            and proposed.models',
        "        require(\n            True\n            and proposed.models",
        "review: disclosure terms equal (redundant with the grant fields)",
    ),
    (
        "M12",
        PRO,
        "        request <= config.request_tokens and request <= config.investigation_tokens,\n",
        "        True,\n",
        "review: Governor request ceiling",
    ),
    (
        "M13",
        API,
        "                    and needed <= set(a.operations)\n",
        "",
        "picker: only disclosure-approved sources",
    ),
    (
        "M14",
        ADP,
        '        all(\n            approved.get(f["path"], {}).get("content") == f["content"]\n            and approved[f["path"]]["sha256"] == f["sha256"]\n            for f in inputs["files"]\n        ),\n',
        "        True,\n",
        "analyze: bytes equal the approved capture",
    ),
    (
        "M15",
        ADP,
        '        and inputs["source_sha256"] == source.content_sha256\n',
        "",
        "analyze: source digest",
    ),
    (
        "M16",
        COG,
        "        if spec is not None and (workflow_claim is None or role != spec.role):\n",
        "        if False:\n",
        "cognition: typed role only inside a stage",
    ),
    (
        "M17",
        COG,
        '            require(not model or control.provider == "meta", "meta_provider_required")\n',
        "",
        "admission: meta provider",
    ),
    (
        "M18",
        COG,
        '                self.mode == "running"\n                and (self.worker is None or self.worker.done()),\n                "start_cognition_before_model_admission",',
        '                True,\n                "start_cognition_before_model_admission",',
        "admission: Cognition started",
    ),
    (
        "M19",
        VAL,
        "        if squash(evidence.quote) not in cited:\n",
        "        if False:\n",
        "validation: quotation match",
    ),
    (
        "M20",
        VAL,
        "    if not 1 <= evidence.line_start <= evidence.line_end <= len(lines):\n",
        "    if False:\n",
        "validation: line locator",
    ),
    ("M21", VAL, "    if source is None:\n", "    if False:\n", "validation: file exists"),
    (
        "M22",
        VAL,
        '            hashlib.sha256(item["content"].encode("utf-8")).hexdigest() == item["sha256"],\n',
        "            True,\n",
        "validation: captured digest",
    ),
    (
        "M23",
        CON,
        '    require(total <= MAX_SOURCE_BYTES, "analysis_source_byte_ceiling")\n',
        "",
        "context: byte ceiling",
    ),
]
TESTS = [
    "tests/test_repository_analysis.py",
    "tests/test_repository_analysis_units.py",
    "tests/test_owner_admission.py",
]


def run(mutant):
    ident, rel, old, new, guard = mutant
    path = ROOT / rel
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        return ident, "invalid", f"pattern matched {source.count(old)} times", guard
    path.write_text(source.replace(old, new, 1), encoding="utf-8", newline="")
    try:
        done = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        lines = [x for x in done.stdout.splitlines() if x.startswith(("FAILED", "ERROR"))]
        if done.returncode == 0:
            return ident, "survived", "", guard
        if (
            any(x.startswith("ERROR") for x in lines)
            or "error" in done.stdout.lower().split("passed")[-1][:40]
        ):
            return ident, "invalid", " | ".join(lines[:1]), guard
        return ident, "killed", lines[0].split(" - ")[0][:110] if lines else "", guard
    finally:
        path.write_text(source, encoding="utf-8", newline="")


if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    for mutant in MUTANTS:
        if not wanted or mutant[0] in wanted:
            print(*run(mutant), sep=" | ", flush=True)
