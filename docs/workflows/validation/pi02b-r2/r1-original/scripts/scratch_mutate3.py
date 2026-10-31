import os, sys, shutil, subprocess

ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
path = os.path.join(ROOT, "alive", "workflows", "runner.py")
cases = {
    "A7v (result hash check removed)": (
        '        and digest(event.payload["output"]) == stage.output_sha256,\n',
        "        and True,\n",
    ),
    "A8v (artifact hash check removed)": (
        '            and digest(artifact.content) == output["sha256"]\n',
        "            and True\n",
    ),
}
for name, (old, new) in cases.items():
    orig = open(path, encoding="utf-8", newline="").read()
    text = orig.replace("\r\n", "\n")
    nl = "\r\n" if "\r\n" in orig else "\n"
    assert old in text, name
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(
            text.replace(old, new, 1).replace("\n", nl)
        )
        for label, tests in (
            (
                "author",
                [
                    "tests/test_workflow_authority.py",
                    "tests/test_workflow_cancellation.py",
                    "tests/test_workflow_execution.py",
                    "tests/test_workflow_transactions.py",
                ],
            ),
            ("probe-F", ["tests/test_review_r1.py", "-k", "test_f_evidence"]),
        ):
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
                    *tests,
                ],
                cwd=ROOT,
                env=dict(os.environ, ALIVE_META_API_KEY="", CI="true"),
                capture_output=True,
                text=True,
            )
            print(
                name,
                label,
                "rc",
                out.returncode,
                [l[:120] for l in out.stdout.splitlines() if l.startswith("FAILED")][:4],
                out.stdout.strip().splitlines()[-1][:100],
                flush=True,
            )
    finally:
        shutil.move(path + ".bak", path)
