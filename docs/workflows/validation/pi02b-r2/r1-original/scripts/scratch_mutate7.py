import os, sys, shutil, subprocess, json

ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
path = os.path.join(ROOT, "alive", "workflows", "runner.py")
EV = r"C:\Projects\alive-pi02b-r1-evidence"


def run(label):
    out = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-W",
            "ignore",
            "--tb=line",
            "tests/test_review_r1.py",
            "-k",
            "test_j_binding",
        ],
        cwd=ROOT,
        env=dict(os.environ, ALIVE_META_API_KEY="", CI="true"),
        capture_output=True,
        text=True,
    )
    res = {}
    for t in ("model", "context", "status", "stage_state", "stage_link"):
        try:
            res[t] = json.load(open(f"{EV}/probe-j_{t}.json"))["upstream_calls"]
        except Exception as e:
            res[t] = "ERR"
    print(label, "rc", out.returncode, res, flush=True)
    json.dump(res, open(f"{EV}/j-matrix-{label}.json", "w"))


run("baseline")
cases = [
    (
        "B1",
        '                and grant.models.get(call.role) == call.model\n                and call.input_json["context"] == approved,',
        '                and call.input_json["context"] == approved,',
    ),
    (
        "B2",
        '                and grant.models.get(call.role) == call.model\n                and call.input_json["context"] == approved,',
        "                and grant.models.get(call.role) == call.model,",
    ),
    (
        "B3",
        '                and call.status == "reserved"\n                and call.investigation_id == run.investigation_id\n                and grant.models',
        "                and call.investigation_id == run.investigation_id\n                and grant.models",
    ),
    (
        "B4",
        "                and stage.state == states.RUNNING\n                and stage.model_invocation_id == call.id",
        "                and stage.model_invocation_id == call.id",
    ),
    (
        "B5",
        '                and stage.model_invocation_id == call.id\n                and call.status == "reserved"',
        '                and call.status == "reserved"',
    ),
]
for label, old, new in cases:
    orig = open(path, encoding="utf-8", newline="").read()
    text = orig.replace("\r\n", "\n")
    nl = "\r\n" if "\r\n" in orig else "\n"
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(
            text.replace(old, new, 1).replace("\n", nl)
        )
        run(label)
    finally:
        shutil.move(path + ".bak", path)
