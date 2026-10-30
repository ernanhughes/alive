import os, sys, shutil, subprocess, importlib.util
spec = importlib.util.spec_from_file_location("m", "scratch_mutate.py")
src = open("scratch_mutate.py", encoding="utf-8").read().split("results = []")[0]
ns = {}
exec(src, ns)
MUT = {m[0].split()[0]: m for m in ns["MUTANTS"]}
ROOT = ns["ROOT"]
PROBE = ["tests/test_review_r1.py"]
plan = {"A4": ["-k", "configuration"], "A15": ["-k", "expire_deadline"], "A1": ["-k", "duplicate"],
        "A14": ["-k", "duplicate or b_"], "A7": [], "A8": [], "A12": ["-k", "b_"], "A13": ["-k", "b_"],
        "A10": ["-k", "b_"], "A9": ["-k", "b_"]}
for key, sel in plan.items():
    name, path, old, new = MUT[key]
    orig = open(path, encoding="utf-8", newline="").read()
    text = orig.replace("\r\n", "\n")
    nl = "\r\n" if "\r\n" in orig else "\n"
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(text.replace(old, new, 1).replace("\n", nl))
        out = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-W", "ignore",
                              "--tb=line", *PROBE, *sel], cwd=ROOT,
                             env=dict(os.environ, ALIVE_META_API_KEY="", CI="true"), capture_output=True, text=True)
        tail = [l for l in out.stdout.splitlines() if l.startswith("FAILED") or " passed" in l or " failed" in l or "error" in l.lower()]
        print(key, name, "rc", out.returncode, tail[:3], flush=True)
    finally:
        shutil.move(path + ".bak", path)
