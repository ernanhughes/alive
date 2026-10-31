# ruff: noqa: E501  (mutation patterns are exact source text)
"""L1-02 mutation receipts: break one authority guard at a time and require a behavioural kill.

A kill is a test FAILURE caused by the mutant. A collection or setup error is `invalid`, never a
kill, and a pattern that does not match exactly once is `invalid` too. A mutant that survives is
reported as `survived`; redundant guards are listed as such, not hidden.

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
NL = "\n"
# (id, file, old text, new text, guard)
MUTANTS = [
    (
        "M01",
        CTX,
        "        grant.outbound_approved" + NL + "        and grant.models.get(role) == model" + NL,
        "        True" + NL + "        and grant.models.get(role) == model" + NL,
        "reservation: outbound approval (shared with runner.start)",
    ),
    (
        "M02",
        CTX,
        "        and grant.models.get(role) == model" + NL + "        and grant.role_contracts",
        "        and grant.role_contracts",
        "reservation: approved model identity",
    ),
    (
        "M03",
        CTX,
        "        == (role_contract(role) if analysis is None else analysis.contract)" + NL,
        "        == grant.role_contracts.get(role)" + NL,
        "reservation: role contract",
    ),
    (
        "M04",
        CTX,
        "        and context == (approved if analysis is None else analysis.context_for(analysis.inputs))"
        + NL,
        "",
        "reservation: exact context",
    ),
    (
        "M05",
        CTX,
        '        == ("cognition-role-v1" if analysis is None else analysis.implementation_id)' + NL,
        '        == capability["identity"]["implementation_id"]' + NL,
        "reservation: implementation identity",
    ),
    (
        "M06",
        CTX,
        "        stage.input_sha256"
        + NL
        + '        == digest({"role": role, "context": context} if analysis is None else analysis.inputs),'
        + NL,
        "        True," + NL,
        "reservation: stage input hash",
    ),
    (
        "M07",
        RUN,
        '        stored["instructions"] == INSTRUCTIONS' + NL + "        and ",
        "        True" + NL + "        and ",
        "fence: instructions",
    ),
    (
        "M08",
        RUN,
        '        and stored.get("context_sha256") == digest(stored["context"])' + NL,
        "",
        "fence: context digest",
    ),
    (
        "M09",
        RUN,
        '        and stored["context"]["source"]["source_sha256"] == resources["content_sha256"]'
        + NL,
        "",
        "fence: source digest",
    ),
    (
        "M10",
        SVC,
        "        for operation in profile.source_operations:"
        + NL
        + "            source = await custody.resolve(kernel, resources, operation)"
        + NL,
        '        source = await custody.resolve(kernel, resources, "repository.inspect")' + NL,
        "prepare: disclosure operation approved",
    ),
    (
        "M10b",
        SVC,
        "    for operation in profile.source_operations:"
        + NL
        + '        source = await custody.resolve(kernel, terms["source"]["resources"], operation)'
        + NL,
        '    source = await custody.resolve(kernel, terms["source"]["resources"], "repository.inspect")'
        + NL,
        "current_terms: disclosure operation approved (expected equivalent)",
    ),
    (
        "M11",
        SVC,
        '            current == terms["model_disclosure"]' + NL + "            and proposed.models",
        "            True" + NL + "            and proposed.models",
        "review: disclosure terms equal",
    ),
    (
        "M12",
        PRO,
        "        request <= config.request_tokens and request <= config.investigation_tokens," + NL,
        "        True," + NL,
        "review: Governor request ceiling",
    ),
    (
        "M13",
        API,
        "service.aware(a.expires_at) > service.now() and needed <= set(a.operations)",
        "service.aware(a.expires_at) > service.now()",
        "picker: only disclosure-approved sources",
    ),
    (
        "M14",
        ADP,
        "        all("
        + NL
        + '            approved.get(f["path"], {}).get("content") == f["content"]'
        + NL
        + '            and approved[f["path"]]["sha256"] == f["sha256"]'
        + NL
        + '            for f in inputs["files"]'
        + NL
        + "        ),"
        + NL,
        "        True," + NL,
        "analyze: bytes equal the approved capture",
    ),
    (
        "M15",
        ADP,
        '        and inputs["source_sha256"] == source.content_sha256' + NL,
        "",
        "analyze: source digest",
    ),
    (
        "M16",
        COG,
        "        if spec is not None and (workflow_claim is None or role != spec.role):" + NL,
        "        if False:" + NL,
        "cognition: typed role only inside a stage",
    ),
    (
        "M17",
        COG,
        '        require(not model or control.provider == "meta", "meta_provider_required")' + NL,
        "",
        "admission: meta provider",
    ),
    (
        "M18",
        COG,
        'self.mode == "running" and (self.worker is None or self.worker.done()),'
        + NL
        + '                "start_cognition_before_model_admission",',
        "True," + NL + '                "start_cognition_before_model_admission",',
        "admission: Cognition started",
    ),
    (
        "M19",
        VAL,
        "        if squash(evidence.quote) not in cited:" + NL,
        "        if False:" + NL,
        "validation: quotation match",
    ),
    (
        "M20",
        VAL,
        "    if not 1 <= evidence.line_start <= evidence.line_end <= len(lines):" + NL,
        "    if False:" + NL,
        "validation: line locator",
    ),
    ("M21", VAL, "    if source is None:" + NL, "    if False:" + NL, "validation: file exists"),
    (
        "M22",
        VAL,
        '            hashlib.sha256(item["content"].encode("utf-8")).hexdigest() == item["sha256"],'
        + NL,
        "            True," + NL,
        "validation: captured digest",
    ),
    (
        "M23",
        CON,
        '    require(total <= MAX_SOURCE_BYTES, "analysis_source_byte_ceiling")' + NL,
        "",
        "context: byte ceiling",
    ),
    (
        "M24",
        CTX,
        "        and stage.model_invocation_id is None," + NL,
        "        and True," + NL,
        "reservation: one model call per stage",
    ),
]
# Compound mutants remove EVERY layer that enforces one invariant, so a kill proves the tests
# notice when the invariant as a whole is gone (not just one of several redundant guards).
COMPOUND = [
    (
        "C01",
        [
            (
                CTX,
                "        grant.outbound_approved"
                + NL
                + "        and grant.models.get(role) == model"
                + NL,
                "        True" + NL + "        and grant.models.get(role) == model" + NL,
            ),
            (
                RUN,
                '                        grant.outbound_approved and self.k.settings.alive_model_transport == "pi",'
                + NL,
                '                        self.k.settings.alive_model_transport == "pi",' + NL,
            ),
        ],
        "outbound approval: reservation + runner.start",
    ),
    (
        "C02",
        [
            (
                CTX,
                "        and grant.models.get(role) == model"
                + NL
                + "        and grant.role_contracts",
                "        and grant.role_contracts",
            ),
            (
                SVC,
                '            current == terms["model_disclosure"]'
                + NL
                + '            and proposed.models == {ROLE: current["destination"]["model"]}'
                + NL,
                "            True" + NL,
            ),
        ],
        "model identity: reservation + current_terms",
    ),
    (
        "C03",
        [
            (
                CTX,
                "        == (role_contract(role) if analysis is None else analysis.contract)" + NL,
                "        == grant.role_contracts.get(role)" + NL,
            ),
            (
                SVC,
                '            current == terms["model_disclosure"]'
                + NL
                + '            and proposed.models == {ROLE: current["destination"]["model"]}'
                + NL
                + '            and proposed.role_contracts == {ROLE: current["role_contract_sha256"]}'
                + NL,
                "            True"
                + NL
                + '            and proposed.models == {ROLE: current["destination"]["model"]}'
                + NL,
            ),
        ],
        "role contract: reservation + current_terms",
    ),
]
# Guards shared with the PI-02 role path are also attacked by the existing workflow suites.
SHARED = [
    "tests/test_workflow_authority.py",
    "tests/test_workflow_r2_fence.py",
    "tests/test_workflow_transactions.py",
    "tests/test_workflow_r2_invariants.py",
]
EXTRA = {"C01": SHARED, "M01": SHARED, "M02": SHARED, "M05": SHARED, "M06": SHARED, "M24": SHARED}
TESTS = [
    "tests/test_repository_analysis.py",
    "tests/test_repository_analysis_units.py",
    "tests/test_owner_admission.py",
]


def run(mutant):
    ident, edits, guard = mutant
    originals = {}
    for rel, old, new in edits:
        path = ROOT / rel
        text = originals.setdefault(rel, path.read_text(encoding="utf-8"))
        if text.count(old) != 1:
            return ident, "invalid", f"pattern matched {text.count(old)} times", guard
    try:
        for rel, old, new in edits:
            path = ROOT / rel
            path.write_text(
                path.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8", newline=""
            )
        done = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                *TESTS,
                *EXTRA.get(ident, []),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        lines = [x for x in done.stdout.splitlines() if x.startswith(("FAILED", "ERROR"))]
        if done.returncode == 0:
            return ident, "survived", "", guard
        if any(x.startswith("ERROR") for x in lines):
            return ident, "invalid", " | ".join(lines[:1]), guard
        return ident, "killed", lines[0].split(" - ")[0][:110] if lines else "", guard
    finally:
        for rel, text in originals.items():
            (ROOT / rel).write_text(text, encoding="utf-8", newline="")


if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    for ident, rel, old, new, guard in MUTANTS:
        if not wanted or ident in wanted:
            print(*run((ident, [(rel, old, new)], guard)), sep=" | ", flush=True)
    for mutant in COMPOUND:
        if not wanted or mutant[0] in wanted:
            print(*run(mutant), sep=" | ", flush=True)
