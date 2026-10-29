"""ALIVE-PI-01B: the Pi RPC supervisor, against a scripted fake Pi (real processes, real pipes)."""

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

from alive.pi import runner as pi_runner
from alive.pi.runner import PiInstall, PiRunFailure, PiRunner
from tests.test_pi_process import wait_dead

FAKE = str(Path(__file__).resolve().parent / "fixtures" / "fake_pi.py")
TOKEN = "run-token-for-tests-0123456789abcdef"


@pytest.fixture
def runner(settings):
    return PiRunner(settings, install=PiInstall(sys.executable, FAKE, "1.4.0", "f" * 64))


def go(runner, prompt, *, deadline=20, on_event=None):
    return asyncio.run(
        runner.run(
            prompt=prompt,
            base_url="http://127.0.0.1:9/v1",
            token=TOKEN,
            max_tokens=256,
            deadline=deadline,
            on_event=on_event,
        )
    )


def test_a_settled_run_returns_text_identity_and_confirmed_cleanup(runner):
    result = go(runner, "SCENARIO:text hello world")
    assert result.failure is None
    assert result.accepted and result.settled
    assert result.text == "hello world"
    assert (result.observed_provider, result.observed_model) == ("alive-egress", "alive-approved")
    assert result.stop_reason == "stop"
    assert result.cleanup_confirmed is True
    assert result.stats["toolCalls"] == 0


def test_pi_is_launched_with_every_authority_disabled(runner):
    argv = json.loads(go(runner, "SCENARIO:argv").text)
    for flag in (
        "--no-tools",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-context-files",
        "--no-session",
        "--no-mcp",
        "--no-approve",
        "--offline",
    ):
        assert flag in argv, flag
    assert argv[argv.index("--mode") + 1] == "rpc"
    assert argv[argv.index("--provider") + 1] == "alive-egress"
    assert argv == list(pi_runner.FLAGS)


def test_the_child_receives_only_the_allow_listed_environment(runner, monkeypatch):
    for name in ("DEV_CANARY_SECRET", "ALIVE_API_TOKEN", "MODEL_API_KEY", "PI_API_KEY"):
        monkeypatch.setenv(name, "must-not-reach-pi")
    keys = set(json.loads(go(runner, "SCENARIO:env").text))
    assert not any("must" in k or "CANARY" in k or "TOKEN" in k or "API_KEY" in k for k in keys)
    assert "PATH" not in keys  # nothing is inherited; node is invoked by absolute path
    allowed = set(pi_runner.build_env(Path("c"), Path("t"))) | {
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
    }
    unexpected = {k for k in keys if k.upper() not in {a.upper() for a in allowed}}
    assert not unexpected, unexpected


def test_pi_runs_offline_without_telemetry_or_update_checks(runner):
    values = json.loads(go(runner, "SCENARIO:envvalues").text)
    assert values["PI_OFFLINE"] == "1"
    assert values["PI_TELEMETRY"] == "0"
    assert values["PI_SKIP_VERSION_CHECK"] == "1"
    assert values["PI_CODING_AGENT_DIR"].endswith("config")  # the per-run directory


def test_the_developers_own_pi_configuration_is_unreachable(runner):
    report = json.loads(go(runner, "SCENARIO:canary").text)
    assert report["home"] == "config"  # HOME is the per-run directory, not the developer's
    assert report["dev_pi_auth_reachable"] is False


def test_events_are_retained_without_prompts_or_credentials(runner):
    seen = []

    async def on_event(event):
        seen.append(event)

    secret_prompt = "TOP-SECRET-PROMPT-CONTENT"
    result = go(runner, f"SCENARIO:text {secret_prompt}", on_event=on_event)
    blob = json.dumps(result.events)
    assert secret_prompt not in blob and TOKEN not in blob
    assert seen == result.events  # the same ordered stream is delivered to the callback
    types = [e.get("type") for e in result.events]
    assert types.index("agent_start") < types.index("agent_settled")


def test_malformed_frames_are_counted_and_do_not_end_the_run(runner):
    result = go(runner, "SCENARIO:malformed carry on")
    assert result.failure is None and result.settled and result.text == "carry on"
    assert result.malformed_frames == 2


def test_a_flood_of_malformed_frames_is_a_typed_protocol_failure(runner):
    result = go(runner, "SCENARIO:flood")
    assert result.failure.category == "pi_protocol_error"
    assert result.cleanup_confirmed is True


def test_a_prompt_that_starts_no_run_fails_fast_instead_of_waiting(runner):
    start = time.monotonic()
    result = go(runner, "SCENARIO:handled", deadline=30)
    assert result.failure.category == "pi_prompt_handled"
    assert time.monotonic() - start < 10  # did not wait for a settlement that will never come
    assert result.cleanup_confirmed is True


def test_a_refused_prompt_is_typed(runner):
    assert go(runner, "SCENARIO:reject").failure.category == "pi_prompt_rejected"


def test_a_process_that_dies_mid_run_is_typed_and_cleaned_up(runner):
    result = go(runner, "SCENARIO:crash")
    assert result.failure.category == "pi_process_exited"
    assert result.settled is False and result.cleanup_confirmed is True


def test_the_deadline_kills_the_whole_tree(runner):
    pids = []

    async def on_event(event):
        if event.get("type") == "alive_fake.child":
            pids.append(event["pid"])

    result = go(runner, "SCENARIO:children", deadline=2, on_event=on_event)
    assert result.failure.category == "pi_deadline"
    assert result.cleanup_confirmed is True
    assert pids and wait_dead(pids[0])  # the grandchild did not outlive the run


def test_cancelling_a_run_kills_the_tree_before_the_cancel_propagates(runner):
    pids = []

    async def on_event(event):
        if event.get("type") == "alive_fake.child":
            pids.append(event["pid"])

    async def scenario():
        task = asyncio.create_task(
            runner.run(
                prompt="SCENARIO:children",
                base_url="http://127.0.0.1:9/v1",
                token=TOKEN,
                max_tokens=256,
                deadline=60,
                on_event=on_event,
            )
        )
        for _ in range(200):
            if pids:
                break
            await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert pids and wait_dead(pids[0])


def test_any_tool_activity_is_counted(runner):
    assert go(runner, "SCENARIO:tool").tool_events == 1


def make_package(tmp_path, *, name="@earendil-works/pi-coding-agent", version="1.4.0"):
    package = tmp_path / "node_modules" / "@earendil-works" / "pi-coding-agent"
    (package / "dist" / "bundle").mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": name, "version": version}))
    (package / "dist" / "bundle" / "cli.js").write_text("// bundle")
    return str(package / "dist" / "bundle" / "cli.js")


def test_the_pinned_version_is_verified_and_a_mismatch_is_refused(settings, tmp_path):
    settings.alive_pi_cli = make_package(tmp_path)
    install = pi_runner.locate_pi(settings)
    assert install.version == "1.4.0" and len(install.bundle_sha256) == 64

    other = tmp_path / "other"
    other.mkdir()
    settings.alive_pi_cli = make_package(other, version="1.5.0")
    with pytest.raises(PiRunFailure) as mismatch:
        pi_runner.locate_pi(settings)
    assert mismatch.value.category == "pi_version_mismatch"

    wrong = tmp_path / "wrong"
    wrong.mkdir()
    settings.alive_pi_cli = make_package(wrong, name="some-other-package")
    with pytest.raises(PiRunFailure) as impostor:
        pi_runner.locate_pi(settings)
    assert impostor.value.category == "pi_version_mismatch"


def test_a_missing_bundle_is_unavailable_not_a_crash(settings, tmp_path):
    settings.alive_pi_cli = str(tmp_path / "nope" / "cli.js")
    with pytest.raises(PiRunFailure) as error:
        pi_runner.locate_pi(settings)
    assert error.value.category == "pi_unavailable"
