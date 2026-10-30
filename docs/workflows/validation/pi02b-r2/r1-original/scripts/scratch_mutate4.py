import os, sys, shutil, subprocess
ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
path = os.path.join(ROOT, "alive", "workflows", "runner.py")
name = "A14 slot not released on success"
old = '            run.finished_at, run.terminal_reason = now(), "required_stages_completed"\n            execution.slot = None'
new = '            run.finished_at, run.terminal_reason = now(), "required_stages_completed"'
orig = open(path, encoding="utf-8", newline="").read()
text = orig.replace("\r\n", "\n"); nl = "\r\n" if "\r\n" in orig else "\n"
print("pattern present:", old in text)
print([l for l in text.splitlines() if "execution.slot" in l])
shutil.copy(path, path + ".bak")
try:
    open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new, 1).replace("\n", nl))
    out = subprocess.run([sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider","-W","ignore","--tb=line","tests/test_review_r1.py","-k","test_h_second"],cwd=ROOT,env=dict(os.environ,ALIVE_META_API_KEY="",CI="true"),capture_output=True,text=True)
    print("A14 under probe-H rc", out.returncode, out.stdout.strip().splitlines()[-3:])
finally:
    shutil.move(path + ".bak", path)
