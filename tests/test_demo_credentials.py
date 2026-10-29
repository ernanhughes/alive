"""Regression tests for the demo credential preflight."""

import importlib.util
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_demo_credentials.py"

spec = importlib.util.spec_from_file_location("verify_demo_credentials", SCRIPT)
assert spec and spec.loader
credentials = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = credentials
spec.loader.exec_module(credentials)


def test_env_file_token_parsing(tmp_path):
    path = tmp_path / ".env"
    path.write_bytes(b'# comment\r\nALIVE_API_TOKEN="local-token-abcdefghijklmnopqrstuvwxyz"\r\n')
    assert credentials.read_env_token(path) == "local-token-abcdefghijklmnopqrstuvwxyz"
    assert credentials.read_env_token(tmp_path / "missing") is None


def test_token_validation():
    assert credentials.valid_token("x" * 24)
    assert not credentials.valid_token("x" * 23)
    assert not credentials.valid_token("x" * 23 + " ")
    assert not credentials.valid_token("x" * 23 + "é")
    assert not credentials.valid_token("")


def test_compose_helpers():
    config = {
        "services": {
            "app": {
                "environment": {"ALIVE_API_TOKEN": "x" * 43},
                "ports": [{"target": 8000, "published": "8123"}],
            }
        }
    }
    assert credentials.compose_environment(config)["ALIVE_API_TOKEN"] == "x" * 43
    assert credentials.compose_host_port(config) == 8123

    list_config = {
        "services": {
            "app": {
                "environment": ["ALIVE_API_TOKEN=" + "y" * 43],
                "ports": ["127.0.0.1:8000:8000"],
            }
        }
    }
    assert credentials.compose_environment(list_config)["ALIVE_API_TOKEN"] == "y" * 43
    assert credentials.compose_host_port(list_config) == 8000


def test_private_dacl_accepts_owner_and_rejects_broad_principals():
    sid = "S-1-5-21-1-2-3-1001"
    assert credentials.private_dacl(f"D:P(A;;FA;;;{sid})", sid)[0]
    assert not credentials.private_dacl(f"D:P(A;;FA;;;{sid})(A;;FA;;;WD)", sid)[0]
    assert not credentials.private_dacl(f"D:AI(A;;FA;;;{sid})", sid)[0]
    assert "Everyone" in credentials.private_dacl("D:P(A;;FA;;;WD)", sid)[1]


def test_running_container_with_a_different_token_is_reported():
    local = "local-token-abcdefghijklmnopqrstuvwxyz"
    other = "other-token-abcdefghijklmnopqrstuvwxyz"
    containers = [
        {
            "Name": "/alive-app-1",
            "Config": {
                "Labels": {
                    "com.docker.compose.service": "app",
                    "com.docker.compose.project": "other",
                    "com.docker.compose.project.working_dir": r"C:\Projects\other",
                },
                "Env": [f"ALIVE_API_TOKEN={other}"],
            },
            "NetworkSettings": {"Ports": {"8000/tcp": [{"HostPort": "8080"}]}},
        }
    ]

    checks = credentials.check_containers(
        containers,
        local,
        Path("C:/Projects/current"),
        strict=True,
        expected_port=8000,
        project_name="other",
    )

    assert any(check.status == "FAIL" and "different" in check.detail for check in checks)
    assert any("different checkout" in check.detail for check in checks)
    assert any("publishes 8080" in check.detail for check in checks)


def test_running_container_with_the_current_token_passes():
    local = "local-token-abcdefghijklmnopqrstuvwxyz"
    containers = [
        {
            "Name": "/alive-app-1",
            "Config": {
                "Labels": {
                    "com.docker.compose.service": "app",
                    "com.docker.compose.project": "alive",
                    "com.docker.compose.project.working_dir": r"C:\Projects\current",
                },
                "Env": [f"ALIVE_API_TOKEN={local}"],
            },
            "NetworkSettings": {"Ports": {"8000/tcp": [{"HostPort": "8000"}]}},
        }
    ]

    checks = credentials.check_containers(
        containers, local, Path(r"C:\Projects\current"), strict=True, expected_port=8000
    )

    assert not any(check.status == "FAIL" for check in checks)
    assert any(check.status == "PASS" for check in checks)


def test_live_probe_accepts_only_the_configured_token():
    token = "server-token-abcdefghijklmnopqrstuvwxyz"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            authorized = self.headers.get("Authorization") == f"Bearer {token}"
            self.send_response(200 if authorized else 401)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        accepted = credentials.check_live(base_url, token, 0, True, None)
        assert not any(check.status == "FAIL" for check in accepted)

        rejected = credentials.check_live(
            base_url, "wrong-token-abcdefghijklmnopqrstuvwxyz", 0, True, None
        )
        assert any(
            check.status == "FAIL" and "different token" in check.detail for check in rejected
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_main_accepts_matching_files(tmp_path, capsys):
    token = "matching-token-abcdefghijklmnopqrstuvwxyz"
    (tmp_path / ".alive").mkdir()
    (tmp_path / ".env").write_text(f"ALIVE_API_TOKEN={token}\n", encoding="utf-8")
    (tmp_path / ".alive" / "token").write_text(token, encoding="utf-8")

    result = credentials.main(
        [
            "--root",
            str(tmp_path),
            "--no-app",
            "--no-docker",
            "--no-http",
            "--no-permissions",
        ]
    )

    assert result == 0
    assert "Summary:" in capsys.readouterr().out


def test_main_rejects_mismatched_files(tmp_path, capsys):
    (tmp_path / ".alive").mkdir()
    (tmp_path / ".env").write_text(
        "ALIVE_API_TOKEN=first-token-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
    )
    (tmp_path / ".alive" / "token").write_text(
        "second-token-abcdefghijklmnopqrstuvwxyz", encoding="utf-8"
    )

    result = credentials.main(
        [
            "--root",
            str(tmp_path),
            "--no-app",
            "--no-docker",
            "--no-http",
            "--no-permissions",
        ]
    )

    assert result == 1
    assert "disagree" in capsys.readouterr().out


def test_main_rejects_missing_token_file(tmp_path, capsys):
    (tmp_path / ".env").write_text(
        "ALIVE_API_TOKEN=only-env-token-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
    )

    result = credentials.main(
        [
            "--root",
            str(tmp_path),
            "--no-app",
            "--no-docker",
            "--no-http",
            "--no-permissions",
        ]
    )

    assert result == 1
    assert ".alive/token" in capsys.readouterr().out
