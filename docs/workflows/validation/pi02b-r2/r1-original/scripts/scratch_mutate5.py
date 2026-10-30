import os, sys, shutil, subprocess, json
ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
path = os.path.join(ROOT, "alive", "workflows", "runner.py")
EV = r"C:\Projects\alive-pi02b-r1-evidence"
def run_f(label):
    out = subprocess.run([sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider","-W","ignore","--tb=line","tests/test_review_r1.py","-k","test_f_evidence"],cwd=ROOT,env=dict(os.environ,ALIVE_META_API_KEY="",CI="true"),capture_output=True,text=True)
    res = {t: json.load(open(f"{EV}/probe-f_{t}.json"))["http"] for t in ("event_output","artifact_content","artifact_hash_rebuilt","swap_output_ref")}
    print(label, res, flush=True)
    json.dump(res, open(f"{EV}/f-matrix-{label}.json","w"))
run_f("baseline")
for label, old, new in (("A7v", '        and digest(event.payload["output"]) == stage.output_sha256,\n', '        and True,\n'),
                        ("A8v", '            and digest(artifact.content) == output["sha256"]\n', '            and True\n')):
    orig = open(path, encoding="utf-8", newline="").read()
    text = orig.replace("\r\n", "\n"); nl = "\r\n" if "\r\n" in orig else "\n"
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new, 1).replace("\n", nl))
        run_f(label)
    finally:
        shutil.move(path + ".bak", path)
run_f("restored")
