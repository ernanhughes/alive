"""The Windows init script must create one consistent, private local token."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")


pytestmark = pytest.mark.skipif(
    os.name != "nt" or PWSH is None,
    reason="the init script is a Windows PowerShell entry point",
)


def run_init(directory: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-File",
            str(directory / "scripts" / "init.ps1"),
            "-NoClipboard",
            *arguments,
        ],
        cwd=directory,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )


def read_env_token(directory: Path) -> str:
    text = (directory / ".env").read_text(encoding="utf-8")
    match = re.search(r"(?m)^ALIVE_API_TOKEN=(.*?)\r?$", text)
    assert match, "init must add an active ALIVE_API_TOKEN line"
    return match.group(1)


def read_file_token(directory: Path) -> str:
    return (directory / ".alive" / "token").read_text(encoding="utf-8").rstrip("\r\n")


def valid(token: str) -> bool:
    return len(token) >= 24 and token.isascii() and not any(ch.isspace() for ch in token)


def sandbox(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / "scripts" / "init.ps1", scripts / "init.ps1")
    shutil.copy2(ROOT / ".env.example", tmp_path / ".env.example")
    return tmp_path


def test_init_is_idempotent_and_rotates_on_request(tmp_path):
    directory = sandbox(tmp_path)

    first = run_init(directory, "-Quiet")
    token = read_file_token(directory)
    assert valid(token)
    assert read_env_token(directory) == token
    assert token not in first.stdout and token not in first.stderr

    run_init(directory, "-Quiet")
    assert read_file_token(directory) == token
    assert read_env_token(directory) == token

    run_init(directory, "-Quiet", "-Rotate")
    rotated = read_file_token(directory)
    assert valid(rotated) and rotated != token
    assert read_env_token(directory) == rotated


def test_init_reuses_an_existing_private_token(tmp_path):
    directory = sandbox(tmp_path)
    (directory / ".alive").mkdir()
    token = "existing-local-token-abcdefghijklmnopqrstuvwxyz"
    (directory / ".alive" / "token").write_text(token, encoding="ascii")

    run_init(directory, "-Quiet")

    assert read_file_token(directory) == token
    assert read_env_token(directory) == token


def test_init_makes_env_the_single_source_of_truth(tmp_path):
    directory = sandbox(tmp_path)
    (directory / ".alive").mkdir()
    (directory / ".alive" / "token").write_text(
        "stale-local-token-abcdefghijklmnopqrstuvwxyz", encoding="ascii"
    )
    env_token = "configured-local-token-abcdefghijklmnopqrstuvwxyz"
    env_text = (directory / ".env.example").read_text(encoding="utf-8")
    (directory / ".env").write_text(env_text + f"\nALIVE_API_TOKEN={env_token}\n", encoding="utf-8")

    run_init(directory, "-Quiet")

    assert read_file_token(directory) == env_token
    assert read_env_token(directory) == env_token
