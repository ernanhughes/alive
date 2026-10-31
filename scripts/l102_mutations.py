# ruff: noqa: E501  (mutation patterns are exact source text)
"""L1-02 mutation receipts: break one authority guard at a time and require a behavioural kill.

A kill is a test FAILURE caused by the mutant. A collection or setup error is `invalid`, never a
kill, and a pattern that does not match exactly once is `invalid` too. A mutant that survives is
reported as `survived`; redundant guards are listed as such, not hidden.

    uv run python scripts/l102_mutations.py --output <outside-checkout>/receipts.json [id ...]
"""

import argparse
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

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
    ("M25", PRO, '            "endpoint": endpoint,' + NL, "", "review: exact endpoint"),
    (
        "M26",
        "alive/providers.py",
        "    return settings.alive_meta_url or (" + NL,
        "    return (" + NL,
        "provider: effective override destination",
    ),
    (
        "M27",
        "alive/providers.py",
        "follow_redirects=False",
        "follow_redirects=True",
        "provider: no redirects",
    ),
    (
        "M28",
        PRO,
        '    require(valid_endpoint, "analysis_requires_safe_https_endpoint")',
        '    require(True, "analysis_requires_safe_https_endpoint")',
        "review: safe HTTPS endpoint",
    ),
    (
        "M29",
        "alive/model_gateway.py",
        "        self.settings = deepcopy(settings)",
        "        self.settings = settings",
        "dispatch: immutable provider configuration",
    ),
    (
        "M30",
        "alive/providers.py",
        "        if destination is not None and url != destination.endpoint:",
        "        if False:",
        "dispatch: pinned endpoint equals owner-approved endpoint",
    ),
    (
        "M31",
        "alive/providers.py",
        "                if destination is not None and request.url != httpx.URL(destination.endpoint):",
        "                if False:",
        "dispatch: built request equals owner-approved endpoint",
    ),
    (
        "M32",
        "alive/providers.py",
        "                trust_env=False,",
        "                trust_env=True,",
        "transport: ignore environment routing and CA settings",
    ),
    (
        "M33",
        "alive/pi/gateway.py",
        "                    if req.destination is None or asdict(req.destination) != destination:",
        "                    if False:",
        "Pi preparation: destination matches invocation receipt",
    ),
    (
        "M34",
        RUN,
        '                    and call.input_json.get("model_destination")'
        + NL
        + "                    == {",
        "                    and {",
        "dispatch fence: destination matches immutable review",
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
COMPOUND.append(
    (
        "C04",
        [
            (
                "alive/providers.py",
                "        if destination is not None and url != destination.endpoint:",
                "        if False:",
            ),
            (
                "alive/providers.py",
                "                if destination is not None and request.url != httpx.URL(destination.endpoint):",
                "                if False:",
            ),
        ],
        "destination: pinned configuration and built HTTP request checks removed together",
    )
)

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
# Select the actual guard's behavioural probes, rather than replaying unrelated journeys for
# every mutant. Shared authority mutants retain their pre-existing defense-in-depth suites.
ANALYSIS = "tests/test_repository_analysis.py::"
UNITS = "tests/test_repository_analysis_units.py::"
TARGETS = {
    "M01": [
        "tests/test_analysis_reservation.py::test_reservation_guard_independently_refuses_changed_authority[outbound]"
    ],
    "M02": [
        "tests/test_analysis_reservation.py::test_reservation_guard_independently_refuses_changed_authority[model]"
    ],
    "M03": [
        "tests/test_analysis_reservation.py::test_reservation_guard_independently_refuses_changed_authority[role_contract]"
    ],
    "M04": [ANALYSIS + "test_the_reservation_alone_binds_the_model_input_to_the_stage[context]"],
    "M05": [
        ANALYSIS + "test_the_reservation_alone_binds_the_model_input_to_the_stage[implementation]"
    ],
    "M06": [ANALYSIS + "test_the_reservation_alone_binds_the_model_input_to_the_stage[inputs]"],
    **{
        i: [ANALYSIS + "test_the_dispatch_fence_refuses_a_call_that_no_longer_matches_the_approval"]
        for i in ("M07", "M08", "M09")
    },
    **{
        i: [ANALYSIS + "test_a_source_approved_only_for_local_inspection_cannot_be_disclosed"]
        for i in ("M10", "M10b", "M13")
    },
    "M11": [ANALYSIS + "test_changed_model_terms_or_source_refuse_before_any_dispatch"],
    "M12": [ANALYSIS + "test_context_beyond_the_profile_or_governor_ceiling_is_refused_at_review"],
    "M14": [ANALYSIS + "test_stage_output_cannot_smuggle_text_the_owner_never_approved"],
    "M15": [ANALYSIS + "test_the_analyzer_alone_refuses_a_different_source_identity"],
    "M16": [
        "tests/test_analysis_review_r2.py::test_T16_a_typed_role_without_a_workflow_claim_is_refused_even_with_a_live_inquiry"
    ],
    "M17": [ANALYSIS + "test_a_model_admission_needs_the_meta_provider_the_owner_started"],
    "M18": [ANALYSIS + "test_the_governor_must_be_explicitly_started_for_a_model_admission"],
    **{
        i: [UNITS + "test_each_citation_outcome_has_its_own_bounded_category"]
        for i in ("M19", "M20")
    },
    "M21": [
        "tests/test_analysis_review_r2.py::test_T21_fabricated_file_receives_a_refusal_classification_not_validity"
    ],
    "M22": [UNITS + "test_a_changed_file_digest_is_refused_before_any_finding_is_trusted"],
    "M23": [UNITS + "test_oversized_or_malformed_context_is_refused_not_truncated"],
    "M24": [ANALYSIS + "test_a_second_model_call_in_one_stage_is_refused"],
    "M25": [
        ANALYSIS + "test_changed_model_terms_or_source_refuse_before_any_dispatch[endpoint_path]"
    ],
    "M26": [ANALYSIS + "test_disclosure_names_the_effective_override_and_only_it_receives_source"],
    "M27": ["tests/test_provider_destination.py"],
    "M28": [ANALYSIS + "test_unsafe_endpoint_is_refused_before_review"],
    "M29": [ANALYSIS + "test_destination_cannot_change_after_the_dispatch_fence"],
    "M30": [
        "tests/test_provider_destination.py::test_authority_binds_the_actual_http_request[pinned_endpoint]"
    ],
    "M31": [
        "tests/test_provider_destination.py::test_authority_binds_the_actual_http_request[built_request]"
    ],
    "M32": [
        "tests/test_model_transport_environment.py::test_environment_proxy_cannot_intercept_model_request[HTTPS_PROXY]"
    ],
    "M33": [
        "tests/test_analysis_review_r2.py::test_invocation_destination_cannot_be_replaced_after_reservation[remove]"
    ],
    "M34": [
        "tests/test_analysis_review_r2.py::test_dispatch_fence_binds_destination_to_the_immutable_review"
    ],
    "C04": [
        "tests/test_provider_destination.py::test_authority_binds_the_actual_http_request[pinned_endpoint]"
    ],
    "C01": [ANALYSIS + "test_a_model_stage_without_outbound_approval_never_reaches_the_provider"],
    **{
        i: [ANALYSIS + "test_the_reservation_alone_refuses_a_late_model_or_contract_change"]
        for i in ("C02", "C03")
    },
}


def run(mutant, baseline, logs):
    ident, edits, guard = mutant
    started = time.monotonic()
    receipt = {"id": ident, "baseline": baseline, "guard": guard, "status": "invalid"}
    # git archive copies only the immutable baseline. No mutation ever touches ROOT, even if
    # this process is interrupted. TemporaryDirectory cleanup is confined to its own directory.
    with tempfile.TemporaryDirectory(prefix=f"alive-l102-{ident}-") as directory:
        import io
        import tarfile

        archive = subprocess.check_output(["git", "archive", baseline], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
            tree.extractall(directory, filter="data")
        isolated = pathlib.Path(directory)
        for rel, old, new in edits:
            path = isolated / rel
            text = path.read_text(encoding="utf-8")
            if text.count(old) != 1:
                return receipt | {"reason": f"pattern matched {text.count(old)} times in {rel}"}
            path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        env = dict(os.environ)
        env["PYTHONPATH"] = str(isolated)
        env.pop("ALIVE_TEST_REAL_PI", None)
        env.pop("ALIVE_TEST_ANALYSIS_POSTGRES_URL", None)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-x",
            "-p",
            "no:cacheprovider",
            *TARGETS.get(ident, TESTS),
            *EXTRA.get(ident, []),
        ]
        done = subprocess.run(
            command,
            cwd=isolated,
            env=env,
            capture_output=True,
            text=True,
        )
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"{ident}.txt").write_text(done.stdout + done.stderr, encoding="utf-8")
        lines = [x for x in done.stdout.splitlines() if x.startswith(("FAILED", "ERROR"))]
        if done.returncode == 0:
            status = "survived"
        elif (
            done.returncode == 1
            and lines
            and not any(x.startswith("ERROR") for x in lines)
            and ("AssertionError" in done.stdout or "Failed: DID NOT RAISE" in done.stdout)
        ):
            status = "killed"
        else:
            status = "invalid"
        return receipt | {
            "status": status,
            "returncode": done.returncode,
            "command": command,
            "failure": lines[:1],
            "log": f"{logs.name}/{ident}.txt",
            "seconds": round(time.monotonic() - started, 3),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--baseline", default="HEAD")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    baseline = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.baseline + "^{commit}"], cwd=ROOT, text=True
    ).strip()
    mutants = [(i, [(p, old, new)], guard) for i, p, old, new, guard in MUTANTS] + COMPOUND
    known = {m[0] for m in mutants}
    if set(args.ids) - known:
        parser.error("unknown mutant IDs: " + ", ".join(sorted(set(args.ids) - known)))
    before = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
    receipts = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for mutant in mutants:
        if not args.ids or mutant[0] in args.ids:
            result = run(mutant, baseline, args.output.parent / (args.output.stem + "-logs"))
            receipts.append(result)
            args.output.write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
            print(
                result["id"],
                result["status"],
                result.get("failure", result.get("reason", "")),
                flush=True,
            )
    after = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)
    if before != after:
        raise SystemExit(
            "production checkout status changed during campaign; inspect before continuing"
        )
