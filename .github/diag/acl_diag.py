"""TEMPORARY diagnostic for the SEC-01 Windows ACL test. Deleted before this PR is finished."""

import csv
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = os.getcwd()
sys.path.insert(0, REPO)


def sh(*args):
    result = subprocess.run(list(args), capture_output=True, text=True, errors="replace")
    print("$ " + " ".join(args))
    print((result.stdout or "").strip())
    if result.stderr.strip():
        print("[stderr] " + result.stderr.strip())
    return result


def sddl(path):
    subprocess.run(["icacls", str(path), "/save", "acl.txt", "/q"], check=True, capture_output=True)
    return Path("acl.txt").read_text(encoding="utf-16-le").removeprefix("﻿").splitlines()


root = Path(tempfile.mkdtemp(prefix="aclprobe-"))
os.chdir(root)
print("=== who ===")
sh("whoami", "/user")
sh("whoami", "/groups")
print("=== parent directory ACL ===")
sh("icacls", str(root))
print("=== stage by stage, same calls as alive.config._restrict_token_file ===")
fd, tmp = tempfile.mkstemp(prefix=".token-", dir=root)
os.close(fd)
print("-- after mkstemp")
sh("icacls", tmp)
print("   SDDL:", sddl(tmp)[1:])
who = sh("whoami", "/user", "/fo", "csv", "/nh")
sid = next(csv.reader([who.stdout.strip()]))[1]
sh("icacls", tmp, "/inheritance:r", "/grant:r", f"*{sid}:(F)")
print("-- after /inheritance:r /grant:r")
sh("icacls", tmp)
saved = sddl(tmp)
print("   SDDL:", saved[1:])
print("   groups:", re.findall(r"\([^()]+\)", saved[1]))
print("=== real code path, then the test's own measurement ===")
from alive.config import Settings, prepare_local  # noqa: E402

settings = Settings(
    _env_file=None,
    alive_api_token="",
    alive_workspace=root / "ws",
    database_url="sqlite+aiosqlite:///x.db",
)
prepare_local(settings)
final = Path(".alive/token")
sh("icacls", str(final))
lines = sddl(final)
print("   SDDL:", lines[1:])
groups = re.findall(r"\([^()]+\)", lines[1])
print("   groups counted by the test regex:", len(groups), groups)
