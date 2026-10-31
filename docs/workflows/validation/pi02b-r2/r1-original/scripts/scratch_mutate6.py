import os, sys, shutil, subprocess, json

ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
path = os.path.join(ROOT, "alive", "workflows", "runner.py")
SUITES = [
    "tests/test_workflow_authority.py",
    "tests/test_workflow_cancellation.py",
    "tests/test_workflow_execution.py",
    "tests/test_workflow_transactions.py",
]
cases = [
    (
        "B1 dispatch fence: model not compared",
        '                and grant.models.get(call.role) == call.model\n                and call.input_json["context"] == approved,',
        '                and call.input_json["context"] == approved,',
    ),
    (
        "B2 dispatch fence: context not compared",
        '                and grant.models.get(call.role) == call.model\n                and call.input_json["context"] == approved,',
        "                and grant.models.get(call.role) == call.model,",
    ),
    (
        "B3 dispatch fence: reservation status not required",
        '                and call.status == "reserved"\n                and call.investigation_id == run.investigation_id\n                and grant.models',
        "                and call.investigation_id == run.investigation_id\n                and grant.models",
    ),
    (
        "B4 dispatch fence: stage must be RUNNING dropped",
        "                and stage.state == states.RUNNING\n                and stage.model_invocation_id == call.id",
        "                and stage.model_invocation_id == call.id",
    ),
    (
        "B5 dispatch fence: invocation-stage link dropped",
        '                and stage.model_invocation_id == call.id\n                and call.status == "reserved"',
        '                and call.status == "reserved"',
    ),
]
res = []
for name, old, new in cases:
    orig = open(path, encoding="utf-8", newline="").read()
    text = orig.replace("\r\n", "\n")
    nl = "\r\n" if "\r\n" in orig else "\n"
    if old not in text:
        print("PATTERN_MISSING", name)
        res.append((name, "PATTERN_MISSING"))
        continue
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(
            text.replace(old, new, 1).replace("\n", nl)
        )
        out = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-W",
                "ignore",
                "--tb=line",
                *SUITES,
            ],
            cwd=ROOT,
            env=dict(os.environ, ALIVE_META_API_KEY="", CI="true"),
            capture_output=True,
            text=True,
        )
        failed = [l[:110] for l in out.stdout.splitlines() if l.startswith("FAILED")]
        r = (
            "CAUGHT"
            if failed
            else ("SURVIVED" if out.returncode == 0 else f"INVALID rc={out.returncode}")
        )
        print(r, name, failed[:1], flush=True)
        res.append((name, r))
    finally:
        shutil.move(path + ".bak", path)
json.dump(
    res, open(r"C:\Projects\alive-pi02b-r1-evidence\dispatch-fence-mutations.json", "w"), indent=1
)
