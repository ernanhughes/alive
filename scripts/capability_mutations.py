# ruff: noqa: E501  (the mutation table holds long guard strings verbatim)
"""Replay PI-03A capability-governance mutations in a temporary copy of the repository only.

Each mutant weakens exactly one guard. It is KILLED only if the named behavioural test passes on
the baseline, then fails with a test failure (not a collection, setup or syntax error) on the
mutant. SURVIVED mutants are reported honestly and are never counted as kills.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REG = "alive/capabilities/registry.py"
EXE = "alive/capabilities/execution.py"
REPO = "alive/capabilities/repository.py"
BND = "alive/capabilities/bindings.py"
RUN = "alive/workflows/runner.py"
E2E = "tests/test_capability_repository_execution.py::"
CONTRACT = "tests/test_capability_contract_enforcement.py::"
REGISTRY = "tests/test_capability_registry.py"
READER = "tests/test_capability_repository.py::"
TIMEOUT_TEST = CONTRACT + "test_stage_may_not_exceed_the_capability_timeout_or_pin_another_hash"

# id, title, file, guard text (must occur exactly once), weakened text, behavioural test
CASES = [
    (
        # A changed manifest is refused by three independent checks: the identity compare at
        # recheck, the identity compare at the grant check, and the policy hash (which embeds the
        # identity). Removing any one or two is an equivalent mutant (defence in depth), so all
        # three are removed together.
        "C1",
        "changed manifest identity refused at recheck, grant check and policy hash (compound)",
        [REG, REG],
        [
            "if not cap.executable or cap.identity != identity:",
            '            grant["identity"] != expected["identity"]\n'
            '            or grant["policy_sha256"] != expected["policy_sha256"]\n',
        ],
        ["if not cap.executable:", "            False\n"],
        E2E
        + "test_pinned_identity_refuses_a_changed_or_disabled_catalogue_but_history_survives"
        + "[tampered_manifest]",
    ),
    (
        "C2",
        "owner grant must carry the current configuration (policy) hash",
        REG,
        '            or grant["policy_sha256"] != expected["policy_sha256"]\n',
        "",
        E2E + "test_configuration_loosened_after_the_grant_is_not_silently_accepted",
    ),
    (
        "C3",
        "owner grant permissions must equal the declaration",
        REG,
        'if grant["permissions"] != expected["permissions"]:',
        "if False:",
        CONTRACT + "test_grant_cannot_change_permissions_or_widen_limits",
    ),
    (
        "C4",
        "owner grant cannot widen a capability limit",
        REG,
        "if type(value) is not int or not minimum <= value <= ceiling:",
        "if type(value) is not int:",
        CONTRACT + "test_grant_cannot_change_permissions_or_widen_limits",
    ),
    (
        "C5",
        "manifest permissions cannot exceed the implementation ceiling",
        REG,
        "not requested <= impl.permission_ceiling\n",
        "False\n",
        REGISTRY,
    ),
    (
        "C6",
        "deployment configuration cannot widen a manifest limit",
        REG,
        "if not minimum <= value <= effective[field]:",
        "if False:",
        CONTRACT + "test_deployment_configuration_may_narrow_but_never_widen_a_manifest_limit",
    ),
    (
        "C7",
        "unavailable/disabled capability must not resolve an adapter",
        REG,
        '        if not cap.executable:\n            raise ValueError("capability unavailable")',
        '        if False:\n            raise ValueError("capability unavailable")',
        REGISTRY,
    ),
    (
        "C8",
        "stage cannot exceed the capability timeout",
        REG,
        'or stage.limits.timeout_seconds > m["execution"]["timeout_seconds"]',
        "or False",
        TIMEOUT_TEST,
    ),
    (
        "C9",
        "stage-pinned manifest hash must match",
        REG,
        "if requested_hash and requested_hash != cap.manifest_sha256:",
        "if False:",
        TIMEOUT_TEST,
    ),
    (
        "C10",
        "output must match the exact output contract",
        EXE,
        '    validate(result.output, cap.manifest["outputs"])\n',
        "    pass\n",
        CONTRACT + "test_output_outside_the_declared_contract_is_refused",
    ),
    (
        "C11",
        "output size ceiling",
        EXE,
        'require(len(blob) <= grant["limits"]["max_output_bytes"], "capability_output_limit")',
        "pass",
        CONTRACT + "test_output_size_ceiling_and_result_type_are_enforced",
    ),
    (
        "C12",
        "input must match the exact input contract",
        EXE,
        '    validate(context.inputs, manifest["inputs"])\n',
        "    pass\n",
        CONTRACT + "test_input_outside_the_declared_contract_is_refused_before_invocation",
    ),
    (
        "C13",
        "writer permission needed for an artifact",
        EXE,
        'result.artifact is None or grant["permissions"]["persistence"] == "workflow_result"',
        "True",
        CONTRACT + "test_a_capability_without_the_writer_permission_cannot_return_an_artifact",
    ),
    (
        "C14",
        "reader snapshot hash must equal the owner-approved hash",
        REPO,
        'and resources["snapshot_sha256"] == snapshot.sha256,',
        ",",
        READER + "test_reader_requires_exact_owner_scope[hash]",
    ),
    (
        "C15",
        "requested paths must equal the owner-approved paths",
        REPO,
        'and sorted(names) == resources["paths"],',
        ",",
        READER + "test_reader_requires_exact_owner_scope[paths]",
    ),
    (
        "C16",
        "hardlink aliases are refused",
        REPO,
        'require(before.st_nlink == 1, "repository_hardlink_refused")',
        "pass",
        READER + "test_hardlink_cannot_alias_an_unapproved_file",
    ),
    (
        "C17",
        "secret and ignored paths are never opened",
        REPO,
        "if _ignored(name, patterns):",
        "if False:",
        READER + "test_secret_and_ignored_paths_are_never_opened",
    ),
    (
        "C18",
        "binding hash in the owner grant must equal the retained binding",
        BND,
        "grant.capability_binding_sha256 == row.snapshot_sha256",
        "True",
        E2E + "test_execution_is_refused_without_exact_capability_authority[wrong_hash]",
    ),
    (
        "C19",
        "runner requires an executable capability",
        RUN,
        "registry.get(stage.operation, stage.capability_version).executable\n",
        "True\n",
        CONTRACT + "test_runner_checks_the_pinned_version_not_merely_the_latest",
    ),
]


TRUSTED_PY = "alive/capabilities/trusted.py"
STORE = "alive/workflows/store.py"
RES = "tests/test_capability_resolution.py::"
LEG = "tests/test_capability_legacy_adoption.py::"
AUTH = "tests/test_capability_registry_authority.py::"
REUSE = "tests/test_capability_reuse_lifecycle.py::"
HARD = "tests/test_capability_hardening.py::"
API = "tests/test_capability_catalog_api.py::"
PINNED_OLDER = (
    RES + "test_a_pinned_older_version_runs_its_own_implementation_while_a_newer_one_exists"
)

# R-series: the independent reviewer's survivors. F-series: one mutant per R2 correction.
CASES += [
    ("R1", "runtime resolves 'latest' instead of the pinned identity", EXE,
     "callback = registry.adapter_for(cap.identity)",
     'callback = registry.adapter(cap.identity["id"], None)', PINNED_OLDER),
    ("R1b", "adapter_for skips the identity/fingerprint recheck", REG,
     '        self.recheck(identity)\n        return self.adapter(identity["id"], identity["version"])',
     '        return self.adapter(identity["id"], identity["version"])',
     RES + "test_a_changed_implementation_mapping_makes_a_pinned_identity_refuse"),
    ("R2", "legacy adoption no longer limited to legacy operations", REG,
     "                and stage.operation in LEGACY_OPERATIONS\n", "",
     LEG + "test_adoption_is_limited_to_legacy_operations_even_for_a_historical_row"),
    ("R3", "legacy adoption accepts a stage that pins a capability version", REG,
     "                and not stage.capability_version\n", "",
     LEG + "test_a_historical_definition_that_pins_a_capability_is_not_adopted"),
    ("R4", "fingerprint ignores the reviewed source bytes", TRUSTED_PY,
     '            hasher.update((ROOT / path).read_bytes().replace(b"\\r\\n", b"\\n"))\n',
     "            pass\n",
     RES + "test_actual_source_bytes_change_the_fingerprint_but_line_endings_do_not"),
    ("R5", "bind ignores the stage's version pin", REG,
     'cap = self.get(stage.operation, getattr(stage, "capability_version", None))',
     "cap = self.get(stage.operation, None)", PINNED_OLDER),
    ("R6", "workflow references ignore the manifest hash", "alive/capabilities/api.py",
     'for key in ("id", "version", "manifest_sha256", "implementation_sha256")',
     'for key in ("id", "version", "implementation_sha256")',
     API + "test_references_need_the_full_retained_identity[manifest]"),
    ("R6b", "workflow references ignore the implementation fingerprint",
     "alive/capabilities/api.py",
     'for key in ("id", "version", "manifest_sha256", "implementation_sha256")',
     'for key in ("id", "version", "manifest_sha256")',
     API + "test_references_need_the_full_retained_identity[implementation]"),
    ("F2a", "fingerprint ignores which adapter the allowlist selects", TRUSTED_PY,
     '                    "adapter": self.adapter,\n', "",
     RES + "test_every_field_that_selects_code_changes_the_fingerprint"),
    ("F2b", "fingerprint ignores traits", TRUSTED_PY,
     '                    "traits": sorted(self.traits),\n', "",
     REUSE + "test_a_trait_change_changes_the_fingerprint"),
    ("F3a", "an oversize .gitignore is no longer named", REPO,
     'too_large = str(error) == "repository_file_size_limit"', "too_large = False",
     READER + "test_oversize_gitignore_fails_closed_with_a_named_reason"),
    ("F3b", "Windows device names are accepted as paths", REPO,
     '        and not any(\n            part.split(".")[0].rstrip(" ").casefold() in DEVICE_NAMES for part in path.parts\n        ),\n',
     "        and True,\n",
     READER + "test_windows_device_names_are_refused_on_every_platform"),
    ("F4a", "every new definition may use the legacy contract", STORE,
     "adopt_legacy=digest in LEGACY_DEFINITION_SHA256", "adopt_legacy=True",
     LEG + "test_a_new_definition_must_meet_the_full_capability_contract"),
    ("F4b", "a pre-existing row is no longer adopted", STORE,
     "await bind_definition(session, kernel, existing, spec, adopt_legacy=True)",
     "await bind_definition(session, kernel, existing, spec, adopt_legacy=False)",
     LEG + "test_a_genuinely_historical_definition_is_adopted_under_its_original_contract"),
    ("F6", "the graph route consults the default catalogue", "alive/workflows/api.py",
     '**graph_of(view["definition"], operations=registry_for(kernel()).operations),',
     '**graph_of(view["definition"]),',
     AUTH + "test_a_yaml_only_capability_is_consistent_across_every_surface"),
    ("F7", "a run without a snapshot is read through today's catalogue", BND,
     "    if not stages:\n        return None\n",
     "    if not stages:\n        return dict(registry_for(kernel).operations)\n",
     AUTH + "test_a_pi02_run_without_a_snapshot_stays_inspectable_after_its_operation_is_removed"),
    ("F8a", "the artifact route no longer needs the result-writer trait", RUN,
     'and "result.writer" in traits  # the retained implementation, not the operation id',
     "and True",
     REUSE + "test_only_a_stage_whose_implementation_writes_results_serves_an_artifact"),
    ("F8b", "record accepts any dependency as independent validation", "alive/workflows/adapters.py",
     '"validation.independent" in traits_of(item["implementation"])', "True",
     REUSE + "test_record_accepts_a_dependency_by_what_it_ran_not_by_its_operation_id"),
    ("F8c", "reference identity is claimed without the implementation trait", STORE,
     'and ({"model.role", "validation.reference-identity"} & set(traits))', "and True",
     REUSE + "test_prepare_compare_and_record_work_under_new_ids"),
    ("F9a", "stage output reaches the generic feed", "alive/kernel.py",
     'if event_type == "workflow.stage.result" and isinstance(payload, dict):', "if False:",
     E2E + "test_stage_output_stays_in_run_history_but_not_in_the_generic_feed"),
    ("F9b", "the REST event feed is not instance scoped", "alive/app.py",
     ".where(Event.instance_id == kernel.instance_id, Event.sequence_number > after)",
     ".where(Event.sequence_number > after)",
     E2E + "test_the_generic_feed_is_scoped_to_this_instance"),
    ("F9c", "the WebSocket feed is not instance scoped", "alive/app.py",
     "                                Event.instance_id == kernel.instance_id,\n"
     "                                Event.sequence_number > cursor,\n",
     "                                Event.sequence_number > cursor,\n",
     E2E + "test_the_generic_feed_is_scoped_to_this_instance"),
    ("F11", "DEL and C1 control characters are accepted in manifest text",
     "alive/capabilities/manifest.py",
     'unicodedata.category(c) == "Cc" and c not in "\\n\\t"',
     'ord(c) < 32 and c not in "\\n\\t"',
     HARD + "test_every_control_character_is_refused_in_manifest_text"),
    ("F12", "duplicate enum members are accepted", "alive/capabilities/contracts.py",
     "            and len({json_bytes(v) for v in options}) == len(options),\n",
     "            and True,\n",
     HARD + "test_duplicate_enum_members_are_refused_rather_than_hashed_differently"),
    ("F15", "activation judges a pinned stage by the newest version", "alive/workflows/spec.py",
     "return dict(operation.executable_versions).get(stage.capability_version, False)",
     "return operation.executable",
     HARD + "test_activation_judges_a_pinned_stage_by_the_version_it_pins"),
]  # fmt: skip


CUSTODY = "alive/sources/custody.py"
ADAPTERS = "alive/capabilities/source_adapters.py"
CT = "tests/test_source_custody.py::"
SC = "tests/test_source_capabilities.py::"
RECHECK = CT + "test_every_custody_fact_is_rechecked_at_the_moment_of_use"
SAME_DIGEST = (
    'require(digest(capture.content) == capture.content_sha256, "source_content_changed")\n'
)

# S-series: the load-bearing PI-03B guards (source custody, scope, provenance, hash stability).
CASES += [
    ("S1", "approval no longer requires the owner to restate the exact digest", CUSTODY,
     'require(confirm_sha256 == capture.content_sha256, "source_digest_mismatch")', "pass",
     CT + "test_nothing_is_usable_until_the_owner_approves_the_exact_digest"),
    ("S2", "use no longer compares the grant's digest with the capture and approval", CUSTODY,
     'approval.content_sha256 == capture.content_sha256 == resources["content_sha256"],', "True,",
     RECHECK),
    ("S3", "a withdrawn approval can still be used", CUSTODY,
     'require(approval.withdrawn_at is None, "source_withdrawn")', "pass", RECHECK),
    ("S4", "an expired approval can still be used", CUSTODY,
     'require(aware(approval.expires_at) > now(), "source_approval_expired")', "pass", RECHECK),
    ("S5", "an operation the owner did not approve can run", CUSTODY,
     'require(operation in list(approval.operations), "source_operation_not_approved")', "pass",
     RECHECK),
    ("S6", "an approval from another instance can be used", CUSTODY,
     "approval.instance_id == capture.instance_id == kernel.instance_id,", "True,",
     CT + "test_custody_is_instance_scoped"),
    ("S7", "use no longer compares the grant's scope hash", CUSTODY,
     'approval.scope_sha256 == resources["scope_sha256"] == digest(approval.scope),', "True,",
     RECHECK),
    ("S8", "content altered under the application is not detected at use", CUSTODY,
     "        " + SAME_DIGEST + "        scoped = apply_scope(",
     "        scoped = apply_scope(",
     CT + "test_content_changed_underneath_the_application_is_detected"),
    ("S9", "the approved scope is ignored: everything captured is returned", CUSTODY,
     "kept = {**content, listing: [i for i in content[listing] if str(i[key]) in allowed]}",
     "kept = dict(content)",
     CT + "test_approval_resolves_to_exactly_the_approved_scope"),
    ("S10", "approval no longer re-verifies the stored content's own digest", CUSTODY,
     "        " + SAME_DIGEST + "        scope = checked_scope(",
     "        scope = checked_scope(",
     CT + "test_content_changed_underneath_the_application_is_detected"),
    ("S11", "a reused request id with other scope is not a conflict", CUSTODY,
     "                and existing.scope_sha256 == digest(scope),\n", "                and True,\n",
     CT + "test_approval_is_idempotent_by_request_and_a_reused_id_with_other_terms_conflicts"),
    ("S12", "an approval scope may name items that were never captured", CUSTODY,
     "        and set(items) <= set(names),\n", "        and True,\n",
     CT + "test_approval_terms_are_bounded_and_validated"),
    ("S13", "a memory changed since approval is returned instead of omitted", CUSTODY,
     'elif hashlib.sha256(row.content.encode()).hexdigest() != item["content_sha256"]:',
     "elif False:",
     SC + "test_collection_retrieval_uses_live_memories_and_omits_changed_ones"),
    # The type is checked twice with the same category: by the runner seam and by the adapter. Either
    # alone is an equivalent mutant (defence in depth), so both are removed together.
    ("S15", "a capability can read a source of a type it does not support (runner AND adapter)",
     [EXE, ADAPTERS],
     ['resources.source_type in manifest["supported_source_types"], "source_type_not_supported"',
      'require(source.source_type == "repository", "source_type_not_supported")'],
     ['True, "source_type_not_supported"', "pass"],
     SC + "test_a_source_type_mismatch_is_refused"),
    ("S16", "a stage can read a source other than the one the grant names", EXE,
     'context.inputs.get("source_ref") == resources.source_ref, "source_ref_not_approved"',
     'True, "source_ref_not_approved"',
     SC + "test_a_stage_cannot_name_a_different_source_than_the_one_approved"),
    ("S17", "a path outside the approved scope is skipped instead of refused", ADAPTERS,
     'require(set(names) <= set(files) | omitted_paths, "source_path_not_approved")', "pass",
     SC + "test_repository_refuses_every_out_of_scope_read"),
    ("S18", "the owner-approved per-call byte limit is ignored", ADAPTERS,
     'require(sum(f["bytes"] for f in chosen) <= limits["max_source_bytes"], "source_byte_limit")',
     "pass",
     SC + "test_a_read_over_the_owner_approved_byte_limit_is_refused_not_truncated"),
    ("S19", "a different parser build is accepted for an approved extraction", ADAPTERS,
     'require(content["parser"] == parser_identity(), "parser_fingerprint_mismatch")', "pass",
     SC + "test_a_changed_parser_build_requires_recapture"),
    ("S20", "browser content claims it is an instruction", ADAPTERS,
     '"content_is_instructions": False,', '"content_is_instructions": True,',
     SC + "test_browser_text_is_returned_as_inert_untrusted_data"),
    ("S21", "retrieved content is labelled verified", ADAPTERS,
     '"semantic_status": "unverified",', '"semantic_status": "verified",',
     SC + "test_repository_lists_and_reads_exactly_the_approved_scope"),
    ("S22", "a partial extraction reports itself complete", ADAPTERS,
     'complete = not remaining and not content["truncated"] and not any(s["truncated"] for s in shown)',
     "complete = True",
     SC + "test_document_extraction_is_windowed_located_and_honest_about_completeness"),
    ("S23", "the sources permission changes every earlier manifest's hash",
     "alive/capabilities/manifest.py",
     'if data.get("sources") == "none":', "if False:",
     "tests/test_source_capability_seam.py::test_every_earlier_manifest_keeps_its_exact_hash"),
    ("S24", "a grant may not carry source resources", REG,
     'not {"repository.read", "source.read"} & permission_bits(cap.manifest["permissions"])',
     'not {"repository.read"} & permission_bits(cap.manifest["permissions"])',
     SC + "test_repository_lists_and_reads_exactly_the_approved_scope"),
]  # fmt: skip


def run(command, scratch, env):
    return subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="mutant ids, for example C1 C10")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/capabilities/validation/mutations.json"
    )
    parser.add_argument(
        "--merge", action="store_true", help="replace only the selected receipts in --output"
    )
    args = parser.parse_args()
    selected = [c for c in CASES if not args.only or c[0] in args.only]
    if not selected:
        parser.error("unknown or empty mutation selection")
    receipts, baselines = [], {}
    kept = []
    if args.merge and args.output.exists():
        kept = [
            r
            for r in json.loads(args.output.read_text(encoding="utf-8"))["mutants"]
            if r["id"] not in {c[0] for c in selected}
        ]
    with tempfile.TemporaryDirectory(prefix="alive-capability-mutations-") as directory:
        scratch = Path(directory)
        for name in ("alive", "tests", "scripts", "config", "fixtures", "migrations"):
            shutil.copytree(
                ROOT / name, scratch / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        for name in ("pyproject.toml", "alembic.ini"):
            shutil.copyfile(ROOT / name, scratch / name)
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "CI": "true",
            "ALIVE_META_API_KEY": "",
            "ALIVE_EMBEDDING_ENABLED": "false",
            "ALIVE_PI_RUNTIME_DIR": str(ROOT / "pi-runtime"),
        }
        for key, title, path, before, after, test in selected:
            # A compound mutant supplies parallel lists; a simple one a single file and guard.
            paths, befores, afters = (
                (path, before, after) if isinstance(path, list) else ([path], [before], [after])
            )
            targets = [scratch / p for p in paths]
            originals = {t: t.read_text(encoding="utf-8") for t in targets}
            for t, b in zip(targets, befores, strict=True):
                assert originals[t].count(b) == 1, (key, "pattern missing or ambiguous")
            original = originals[targets[0]]
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                test,
            ]
            if test not in baselines:
                baseline = run(command, scratch, env)
                assert baseline.returncode == 0, (key, "BASELINE_FAILED", baseline.stdout)
                baselines[test] = "PASS"
            try:
                for t, b, a in zip(targets, befores, afters, strict=True):
                    t.write_text(t.read_text(encoding="utf-8").replace(b, a, 1), encoding="utf-8")
                changed = run(command, scratch, env)
            finally:
                for t, text in originals.items():
                    t.write_text(text, encoding="utf-8")
            out = changed.stdout
            valid = (
                changed.returncode == 1
                and "FAILED " in out
                and "ERROR at" not in out
                and "ERROR collecting" not in out
                and "SyntaxError" not in out
            )
            result = "KILLED" if valid else "SURVIVED" if changed.returncode == 0 else "INVALID"
            receipts.append(
                {
                    "id": key,
                    "mutation": title,
                    "files": paths,
                    "target": test,
                    "baseline": "PASS",
                    "result": result,
                    "modified_guards": [b.strip() for b in befores],
                    "replacements": [a.strip() for a in afters],
                    "assertion": out[-1500:],
                    "returncode": changed.returncode,
                    "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
                }
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            order = {c[0]: i for i, c in enumerate(CASES)}
            merged = sorted([*kept, *receipts], key=lambda r: order[r["id"]])
            args.output.write_text(
                json.dumps({"mutants": merged}, indent=2) + "\n", encoding="utf-8"
            )
            print(f"{key} {result}: {test}", flush=True)
    everything = [*kept, *receipts]
    counts = {
        r: sum(x["result"] == r for x in everything) for r in ("KILLED", "SURVIVED", "INVALID")
    }
    print(counts, flush=True)
    sys.exit(1 if counts["INVALID"] else 0)


if __name__ == "__main__":
    main()
