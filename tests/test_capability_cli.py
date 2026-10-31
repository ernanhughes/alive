"""Authoring tooling: reports what the catalogue would do, never imports an implementation."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from alive.capabilities.cli import main

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "alive/capabilities/manifests"


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def declared(**changes):
    value = yaml.safe_load((MANIFESTS / "context.prepare@1.0.0.yaml").read_text(encoding="utf-8"))
    value.update(changes)
    return value


def write(tmp_path, value):
    path = tmp_path / f"{value['id']}@{value['version']}.yaml"
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    return path


def test_list_and_doctor_report_unavailable_without_failing(capsys):
    code, out, _ = run(capsys, "list", "--json")
    assert code == 0
    by_id = {c["id"]: c for c in json.loads(out)}
    assert by_id["repository.inspect"]["status"] == "available"
    assert by_id["memory.retrieve"]["status"] == "unavailable"
    assert run(capsys, "doctor")[0] == 0


def test_inspect_by_id_and_version(capsys):
    code, out, _ = run(capsys, "inspect", "repository.inspect@1.0.0")
    assert code == 0 and json.loads(out)["implementation"]["id"] == "repository-inspector-v1"
    assert run(capsys, "inspect", "missing.thing")[0] == 1


def test_a_new_declaration_reusing_trusted_code_validates_and_reports_its_hash(tmp_path, capsys):
    path = write(tmp_path, declared(id="context.review"))
    code, out, _ = run(capsys, "validate", str(path), "--json")
    report = json.loads(out)
    assert code == 0 and report["usable_in_workflow"] and len(report["manifest_sha256"]) == 64
    assert "owner grant" in report["note"]


def test_missing_implementation_is_discoverable_not_usable(tmp_path, capsys):
    value = declared(id="context.pending")
    value["implementation"]["id"] = "not-installed-v1"
    code, out, _ = run(capsys, "validate", str(write(tmp_path, value)), "--json")
    report = json.loads(out)
    assert code == 1 and report["status"] == "unavailable" and not report["usable_in_workflow"]


def test_duplicate_identity_with_different_content_is_refused(tmp_path, capsys):
    value = declared(description="A different declaration")
    code, _, err = run(capsys, "validate", str(write(tmp_path, value)))
    assert code == 1 and "duplicate" in err


def test_identical_installed_manifest_revalidates(tmp_path, capsys):
    copy = tmp_path / "context.prepare@1.0.0.yaml"
    shutil.copy(MANIFESTS / "context.prepare@1.0.0.yaml", copy)
    assert run(capsys, "validate", str(copy))[0] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"implementation": {"provider": "builtin", "id": "x", "module": "os:system"}},
        {"permissions": {"filesystem": {"mode": "read_only", "roots": ["/"]}}},
        {"unknown_field": 1},
        {"version": "1.0"},
    ],
)
def test_hostile_declarations_are_refused(tmp_path, capsys, change):
    value = declared(id="context.hostile") | change
    assert run(capsys, "validate", str(write(tmp_path, value)))[0] == 1


def test_filename_must_match_identity_and_links_are_refused(tmp_path, capsys):
    wrong = tmp_path / "other.yaml"
    wrong.write_text(yaml.safe_dump(declared(id="context.review")), encoding="utf-8")
    assert run(capsys, "validate", str(wrong))[0] == 1
    assert run(capsys, "validate", str(tmp_path / "absent@1.0.0.yaml"))[0] == 1


def test_validation_never_imports_implementation_code(tmp_path):
    # A clean interpreter: this process already imported the adapters via the app fixtures.
    path = write(tmp_path, declared(id="context.review"))
    code = chr(10).join(
        [
            "import sys",
            "from alive.capabilities.cli import main",
            f"status = main(['validate', {str(path)!r}])",
            "names = ('alive.workflows.adapters', 'alive.society')",
            "loaded = [m for m in names if m in sys.modules]",
            "print(status, loaded)",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, check=True
    )
    assert result.stdout.strip().endswith("0 []"), result.stdout
