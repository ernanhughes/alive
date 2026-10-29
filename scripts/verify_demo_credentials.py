#!/usr/bin/env python3
"""Verify that the local ALIVE demo credential agrees everywhere it is used.

The check is intentionally read-only unless ``--fix`` is passed. It never prints a
token value. Exit status is 1 when any check fails.

Typical use from the checkout that launches the demo:

    uv run python scripts/verify_demo_credentials.py
    uv run python scripts/verify_demo_credentials.py --require-live
    uv run python scripts/verify_demo_credentials.py --root C:\\path\\to\\worktree
"""

from __future__ import annotations

import argparse
import csv
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BROAD_TRUSTEES = {
    "WD": "Everyone",
    "BU": "Users",
    "AU": "Authenticated Users",
    "AN": "Anonymous",
    "GU": "Guests",
    "IU": "Interactive Users",
    "RC": "Restricted Code",
    "AC": "All Application Packages",
    "S-1-1-0": "Everyone",
    "S-1-5-11": "Authenticated Users",
    "S-1-5-32-545": "Users",
    "S-1-5-32-546": "Guests",
    "S-1-5-7": "Anonymous",
    "S-1-5-4": "Interactive Users",
    "S-1-15-2-1": "All Application Packages",
    "S-1-15-2-2": "All Restricted Application Packages",
}
ACE_PATTERN = re.compile(r"\(([A-Za-z]+);([^;]*);([^;]*);([^;]*);([^;]*);([^)]*)\)")


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


def redact(text: str, token: str | None = None) -> str:
    text = re.sub(r"(?i)(ALIVE_API_TOKEN\s*[=:]\s*)([^\s,}]+)", r"\1<redacted>", text)
    if token:
        text = text.replace(token, "<redacted>")
    return text


def read_env_token(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    for line in lines:
        match = re.match(r"^\s*(?:export\s+)?ALIVE_API_TOKEN\s*=\s*(.*?)\s*$", line, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value
    return None


def read_file_token(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError):
        return None


def valid_token(value: str | None) -> bool:
    return bool(
        value
        and len(value) >= 24
        and value.isascii()
        and all(33 <= ord(character) <= 126 for character in value)
    )


def same_token(left: str | None, right: str | None) -> bool:
    return bool(
        left
        and right
        and hmac.compare_digest(left.encode("ascii", "replace"), right.encode("ascii", "replace"))
    )


def current_sid() -> str | None:
    if os.name != "nt":
        return None
    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return next(csv.reader([result.stdout.strip()]))[1].strip()
    except (OSError, subprocess.SubprocessError, StopIteration, IndexError):
        return None


def read_saved_dacl(path: Path) -> str | None:
    if os.name != "nt":
        return None
    with tempfile.TemporaryDirectory() as directory:
        saved = Path(directory) / "acl.txt"
        try:
            subprocess.run(
                ["icacls", str(path), "/save", str(saved), "/q"],
                capture_output=True,
                timeout=10,
                check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        raw = saved.read_bytes()
        if raw.startswith(b"\xff\xfe"):
            text = raw[2:].decode("utf-16-le")
        elif raw.startswith(b"\xfe\xff"):
            text = raw[2:].decode("utf-16-be")
        else:
            try:
                text = raw.decode("utf-16-le")
            except UnicodeDecodeError:
                text = raw.decode("utf-8", "replace")
        lines = text.splitlines()
        return lines[1] if len(lines) > 1 else None


def dacl_trustees(dacl: str) -> list[str]:
    return [match.group(6) for match in ACE_PATTERN.finditer(dacl)]


def private_dacl(dacl: str, sid: str | None) -> tuple[bool, str]:
    if not dacl.startswith("D:P"):
        return False, "DACL is not protected"
    trustees = dacl_trustees(dacl)
    broad = [BROAD_TRUSTEES[trustee] for trustee in trustees if trustee in BROAD_TRUSTEES]
    if broad:
        return False, "DACL grants broad principals: " + ", ".join(sorted(set(broad)))
    owner_present = bool(
        sid and (sid in trustees or "OW" in trustees or ("LA" in trustees and sid.endswith("-500")))
    )
    if not owner_present:
        return False, "DACL has no full-control ACE for the current owner"
    return True, "protected owner-only DACL"


def check_permissions(path: Path, label: str) -> Check:
    if not path.is_file():
        return Check(label, "FAIL", "file does not exist")
    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            return Check(label, "FAIL", f"mode {mode:o} is accessible by group/other")
        return Check(label, "PASS", f"mode {mode:o}")
    dacl = read_saved_dacl(path)
    if dacl is None:
        return Check(label, "FAIL", "could not read the Windows DACL")
    ok, detail = private_dacl(dacl, current_sid())
    return Check(label, "PASS" if ok else "FAIL", detail)


def extension_port(root: Path) -> int | None:
    config = root / "extension" / "config.js"
    if not config.is_file():
        return None
    match = re.search(
        r"DEFAULT_BACKEND\s*=\s*['\"]http://127\.0\.0\.1:(\d+)", config.read_text("utf-8")
    )
    return int(match.group(1)) if match else None


def compose_config(root: Path) -> tuple[dict | None, str | None]:
    if shutil.which("docker") is None:
        return None, "Docker CLI not found"
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return None, redact(str(error))
    if result.returncode != 0:
        return None, redact((result.stderr or result.stdout).strip())
    try:
        return json.loads(result.stdout), None
    except json.JSONDecodeError:
        return None, "docker compose config did not return JSON"


def compose_environment(config: dict) -> dict[str, str]:
    environment = config.get("services", {}).get("app", {}).get("environment", {})
    if isinstance(environment, list):
        return dict(item.split("=", 1) for item in environment if "=" in item)
    if isinstance(environment, dict):
        return {str(key): "" if value is None else str(value) for key, value in environment.items()}
    return {}


def compose_host_port(config: dict) -> int | None:
    ports = config.get("services", {}).get("app", {}).get("ports", [])
    for entry in ports:
        if isinstance(entry, dict):
            published = entry.get("published") or entry.get("host_port")
            target = str(entry.get("target", "8000"))
            if published and target == "8000":
                return int(published)
        elif isinstance(entry, str):
            parts = entry.rsplit(":", 2)
            if len(parts) >= 2 and parts[-1] == "8000":
                return int(parts[-2])
    return None


def docker_containers() -> tuple[list[dict], str | None]:
    if shutil.which("docker") is None:
        return [], "Docker CLI not found"
    try:
        listed = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as error:
        return [], redact(str(error))
    if listed.returncode != 0:
        return [], redact((listed.stderr or listed.stdout).strip())
    containers: list[dict] = []
    for identifier in listed.stdout.split():
        try:
            inspected = subprocess.run(
                ["docker", "inspect", identifier],
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return [], redact(str(error))
        if inspected.returncode != 0:
            continue
        try:
            data = json.loads(inspected.stdout)
        except json.JSONDecodeError:
            continue
        containers.extend(data if isinstance(data, list) else [data])
    return containers, None


def container_labels(container: dict) -> dict[str, str]:
    return container.get("Config", {}).get("Labels") or {}


def container_environment(container: dict) -> dict[str, str]:
    return dict(
        item.split("=", 1) for item in container.get("Config", {}).get("Env", []) if "=" in item
    )


def container_token(container: dict) -> str | None:
    return container_environment(container).get("ALIVE_API_TOKEN")


def container_published_port(container: dict) -> int | None:
    ports = container.get("NetworkSettings", {}).get("Ports") or {}
    for key, bindings in ports.items():
        if key.startswith("8000/") and bindings and isinstance(bindings[0], dict):
            try:
                return int(bindings[0].get("HostPort", ""))
            except (TypeError, ValueError):
                return None
    return None


def check_containers(
    containers: list[dict],
    local_token: str,
    root: Path,
    strict: bool,
    expected_port: int | None,
    project_name: str | None = None,
) -> list[Check]:
    relevant = [
        container
        for container in containers
        if container_labels(container).get("com.docker.compose.service") == "app"
        or container_token(container)
    ]
    if not relevant:
        return [Check("running containers", "WARN", "no running ALIVE container found")]
    checks: list[Check] = []
    current = os.path.normcase(str(root.resolve()))
    for container in relevant:
        labels = container_labels(container)
        name = str(container.get("Name", "?")).lstrip("/")
        project = labels.get("com.docker.compose.project", "?")
        workdir = labels.get("com.docker.compose.project.working_dir", "")
        token = container_token(container)
        port = container_published_port(container)
        if token and same_token(token, local_token):
            checks.append(Check(f"container {name}", "PASS", f"project {project} uses this token"))
        elif token:
            belongs = bool(
                (project_name and project == project_name)
                or (workdir and os.path.normcase(str(Path(workdir).resolve())) == current)
            )
            status = "FAIL" if strict and belongs else "WARN"
            checks.append(
                Check(
                    f"container {name}",
                    status,
                    f"project {project} from {workdir or 'an unknown checkout'} uses a "
                    "different ALIVE_API_TOKEN; stop it or run scripts/init.ps1 in that checkout",
                )
            )
        else:
            checks.append(
                Check(
                    f"container {name}",
                    "WARN",
                    f"project {project} has no ALIVE_API_TOKEN in its environment",
                )
            )
        if workdir and os.path.normcase(str(Path(workdir).resolve())) != current:
            checks.append(
                Check(
                    f"container {name} checkout",
                    "WARN",
                    f"started from a different checkout: {workdir}",
                )
            )
        if port and expected_port and port != expected_port:
            checks.append(
                Check(
                    f"container {name} port",
                    "WARN",
                    f"publishes {port}; the extension expects {expected_port}",
                )
            )
    return checks


def http_status(url: str, token: str | None, timeout: float = 3.0) -> int | None:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def check_live(
    base_url: str,
    token: str,
    wait_seconds: int,
    require_live: bool,
    expected_port: int | None,
) -> list[Check]:
    endpoint = base_url.rstrip("/") + "/api/v1/alive"
    deadline = time.monotonic() + max(wait_seconds, 0)
    status = http_status(endpoint, None)
    while status is None and time.monotonic() < deadline:
        time.sleep(1)
        status = http_status(endpoint, None)
    if status is None:
        return [
            Check(
                "live server",
                "FAIL" if require_live else "WARN",
                f"not reachable at {base_url}",
            )
        ]
    checks = []
    if status in (401, 403):
        checks.append(Check("live server unauthenticated", "PASS", f"HTTP {status}"))
    else:
        checks.append(
            Check(
                "live server unauthenticated",
                "FAIL",
                f"returned HTTP {status}; protected access must be denied",
            )
        )
    authenticated = http_status(endpoint, token)
    if authenticated == 200:
        checks.append(Check("live server token", "PASS", "the .env token authenticates"))
    elif authenticated in (401, 403):
        checks.append(
            Check(
                "live server token",
                "FAIL",
                f"HTTP {authenticated}; the server uses a different token or was started "
                "before the token changed",
            )
        )
    else:
        checks.append(
            Check(
                "live server token",
                "FAIL",
                f"unexpected HTTP {authenticated}; the database or runtime may not be ready",
            )
        )
    rejected = http_status(endpoint, secrets.token_urlsafe(32))
    if rejected == 200:
        checks.append(Check("live server invalid token", "FAIL", "an invalid token was accepted"))
    elif rejected in (401, 403):
        checks.append(Check("live server invalid token", "PASS", f"HTTP {rejected}"))
    else:
        checks.append(Check("live server invalid token", "WARN", f"unexpected HTTP {rejected}"))
    if expected_port and expected_port not in (80, 443):
        from urllib.parse import urlsplit

        actual_port = urlsplit(base_url).port
        if actual_port and actual_port != expected_port:
            checks.append(
                Check(
                    "live server port",
                    "WARN",
                    f"probing {actual_port}; compose publishes {expected_port}",
                )
            )
    return checks


def check_application(root: Path, file_token: str) -> list[Check]:
    previous = Path.cwd()
    os.chdir(root)
    try:
        sys.path.insert(0, str(root))
        from alive.config import Settings, prepare_local

        loaded = prepare_local(Settings())
    except Exception as error:  # noqa: BLE001 - report a sanitized startup failure
        return [Check("application token loader", "FAIL", redact(str(error), file_token))]
    finally:
        os.chdir(previous)
    if same_token(loaded, file_token):
        return [Check("application token loader", "PASS", "loads the .env token")]
    return [
        Check(
            "application token loader",
            "FAIL",
            "loads a different token; check for an ALIVE_API_TOKEN environment override",
        )
    ]


def run_fix(root: Path) -> str | None:
    if os.name != "nt" or shutil.which("pwsh") is None:
        return "--fix requires Windows PowerShell (pwsh) and scripts/init.ps1"
    script = root / "scripts" / "init.ps1"
    if not script.is_file():
        return f"{script} is missing"
    try:
        result = subprocess.run(
            [shutil.which("pwsh"), "-NoProfile", "-File", str(script), "-NoClipboard"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return str(error)
    if result.returncode != 0:
        return redact((result.stderr or result.stdout).strip())
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-url", default="")
    parser.add_argument("--no-app", action="store_true", help="skip the app token-loader check")
    parser.add_argument("--no-docker", action="store_true", help="skip compose/container checks")
    parser.add_argument("--no-containers", action="store_true", help="skip running containers")
    parser.add_argument("--no-http", action="store_true", help="skip live HTTP probes")
    parser.add_argument("--no-permissions", action="store_true", help="skip file ACL checks")
    parser.add_argument(
        "--strict-containers",
        action="store_true",
        help="fail when a running container uses a different token",
    )
    parser.add_argument(
        "--require-live",
        action="store_true",
        help="fail when the server is not reachable instead of warning",
    )
    parser.add_argument("--wait", type=int, default=0, help="seconds to wait for the server")
    parser.add_argument("--fix", action="store_true", help="run scripts/init.ps1 first")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    checks: list[Check] = []
    if args.fix:
        error = run_fix(root)
        if error:
            print(f"[FAIL] fix: {error}")
            return 1

    env_path = root / ".env"
    token_path = root / ".alive" / "token"
    env_token = read_env_token(env_path)
    file_token = read_file_token(token_path)

    if env_token is None:
        checks.append(Check(".env token", "FAIL", f"{env_path} has no ALIVE_API_TOKEN"))
    elif not valid_token(env_token):
        checks.append(Check(".env token", "FAIL", "must be at least 24 visible ASCII characters"))
    else:
        checks.append(Check(".env token", "PASS", f"{len(env_token)} characters"))
    if file_token is None:
        checks.append(Check(".alive/token", "FAIL", f"{token_path} is missing"))
    elif not valid_token(file_token):
        checks.append(Check(".alive/token", "FAIL", "must be at least 24 visible ASCII characters"))
    else:
        checks.append(Check(".alive/token", "PASS", f"{len(file_token)} characters"))
    if env_token and file_token:
        checks.append(
            Check(
                "token agreement",
                "PASS" if same_token(env_token, file_token) else "FAIL",
                "the token files agree"
                if same_token(env_token, file_token)
                else ("the token files disagree; run scripts/init.ps1"),
            )
        )
    if not args.no_permissions:
        checks.append(check_permissions(env_path, ".env permissions"))
        checks.append(check_permissions(token_path, ".alive/token permissions"))

    if not args.no_app and file_token:
        checks.extend(check_application(root, file_token))

    host_port = None
    project_name = None
    if not args.no_docker:
        config, error = compose_config(root)
        if error:
            checks.append(Check("compose token", "FAIL", error))
        else:
            project_name = str(config.get("name") or "") or None
            environment = compose_environment(config)
            compose_token = environment.get("ALIVE_API_TOKEN", "")
            if not valid_token(compose_token):
                checks.append(Check("compose token", "FAIL", "Compose has no valid token"))
            elif same_token(compose_token, file_token):
                checks.append(Check("compose token", "PASS", "matches the checkout token"))
            else:
                checks.append(
                    Check(
                        "compose token",
                        "FAIL",
                        "Compose resolves a different token; run scripts/init.ps1 in this checkout",
                    )
                )
            host_port = compose_host_port(config)
            expected = extension_port(root)
            if host_port and expected and host_port != expected:
                checks.append(
                    Check(
                        "compose port",
                        "WARN",
                        f"publishes {host_port}; the extension expects {expected}",
                    )
                )
        if not args.no_containers:
            containers, error = docker_containers()
            if error:
                checks.append(Check("running containers", "WARN", error))
            else:
                checks.extend(
                    check_containers(
                        containers,
                        file_token or "",
                        root,
                        args.strict_containers,
                        extension_port(root),
                        project_name,
                    )
                )

    if not args.no_http:
        base_url = args.base_url or f"http://127.0.0.1:{host_port or 8000}"
        checks.extend(
            check_live(
                base_url,
                file_token or "",
                args.wait,
                args.require_live,
                host_port,
            )
        )

    failures = sum(check.status == "FAIL" for check in checks)
    warnings = sum(check.status == "WARN" for check in checks)
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(root),
                    "checks": [check.__dict__ for check in checks],
                    "failures": failures,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        for check in checks:
            print(f"[{check.status}] {check.name}: {check.detail}")
        print(
            f"Summary: {len(checks) - failures - warnings} passed, "
            f"{warnings} warnings, {failures} failed"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
