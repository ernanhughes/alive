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


@pytest.fixture(autouse=True)
def fake_pi_bookkeeping_events(monkeypatch):
    """The fake Pi reports child pids / provider status as extra events; allow just those here."""
    monkeypatch.setitem(
        pi_runner.LABELS,
        "type",
        pi_runner.EVENT_TYPES | {"alive_fake.child", "alive_fake.provider_call"},
    )
    monkeypatch.setattr(pi_runner, "ALLOWED_KEYS", pi_runner.ALLOWED_KEYS | {"pid", "status"})
    monkeypatch.setattr(pi_runner, "NUMBER_KEYS", pi_runner.NUMBER_KEYS | {"pid", "status"})


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


# The expected environment is written out here, NOT derived from build_env: an oracle computed from
# the implementation would authorize anything the implementation added (review finding PIB-07).
EXPECTED_BUILD_ENV = {
    "PI_CODING_AGENT_DIR",
    "PI_OFFLINE",
    "PI_TELEMETRY",
    "PI_SKIP_VERSION_CHECK",
    "HOME",
    "USERPROFILE",
    "TMPDIR",
    "TEMP",
    "TMP",
} | ({"SYSTEMROOT"} if sys.platform == "win32" else set())
SPAWN_ADDS_TAG = {"ALIVE_PI_RUN_TAG"}  # ManagedProcess tags every child (process-tree containment)
ADDED_BY_THE_PYTHON_DOUBLE = {"SYSTEMDRIVE", "WINDIR", "LC_CTYPE"}  # loader / PEP 538, not ALIVE
HOSTILE_PARENT_ENV = {
    "DEV_CANARY_SECRET": "must-not-reach-pi",
    "ALIVE_API_TOKEN": "must-not-reach-pi",
    "ALIVE_META_API_KEY": "must-not-reach-pi",
    "MODEL_API_KEY": "must-not-reach-pi",
    "PI_API_KEY": "must-not-reach-pi",
    "OPENAI_API_KEY": "must-not-reach-pi",
    "ANTHROPIC_API_KEY": "must-not-reach-pi",
    "HTTP_PROXY": "http://proxy.invalid:9000",
    "HTTPS_PROXY": "http://proxy.invalid:9000",
    "ALL_PROXY": "http://proxy.invalid:9000",
    "NO_PROXY": "*",
    "NODE_OPTIONS": "--require=/nonexistent.js",
    "NODE_EXTRA_CA_CERTS": "/nonexistent.pem",
    "NODE_TLS_REJECT_UNAUTHORIZED": "0",
    "PI_CONFIG_DIR": "/dev/nonexistent",
    "PATH": "/nonexistent",
}


def test_build_env_is_exactly_the_written_out_allowlist(monkeypatch):
    for name, value in HOSTILE_PARENT_ENV.items():
        monkeypatch.setenv(name, value)
    env = pi_runner.build_env(Path("c"), Path("t"))
    assert {k.upper() for k in env} == {k.upper() for k in EXPECTED_BUILD_ENV}
    assert not set(HOSTILE_PARENT_ENV) & set(env)


def test_the_child_receives_only_the_allow_listed_environment(runner, monkeypatch):
    for name, value in HOSTILE_PARENT_ENV.items():
        monkeypatch.setenv(name, value)
    keys = {k.upper() for k in json.loads(go(runner, "SCENARIO:env").text)}
    assert not keys & {name.upper() for name in HOSTILE_PARENT_ENV}
    expected = EXPECTED_BUILD_ENV | SPAWN_ADDS_TAG
    unexpected = keys - {k.upper() for k in expected} - ADDED_BY_THE_PYTHON_DOUBLE
    assert not unexpected, unexpected
    assert {k.upper() for k in EXPECTED_BUILD_ENV | SPAWN_ADDS_TAG} <= keys


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
    settings.alive_pi_bundle_sha256 = ""  # this test is about name/version; the digest has its own
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


# --- PIB-06: Pi output is untrusted; retained events are rebuilt from an allowlist ---

PROMPT_CANARY = "PRIVATE-PROMPT-CANARY-DO-NOT-RETAIN"


def test_a_hostile_key_or_short_safe_field_cannot_carry_a_prompt_or_the_run_token():
    token = "review-only-single-run-token-not-real"
    event = {
        "type": "message_update",
        "reason": PROMPT_CANARY,  # a short "safe-looking" field used to be retained verbatim
        "stopReason": PROMPT_CANARY,
        "role": PROMPT_CANARY,
        "provider": PROMPT_CANARY,
        token: "a hostile JSON key equal to the run token",
        PROMPT_CANARY: "a hostile JSON key equal to the prompt",
        "message": {"role": "assistant", "content": [{"type": "text", "text": PROMPT_CANARY}]},
    }
    encoded = json.dumps(pi_runner.redact_event(event, (token,)))
    assert PROMPT_CANARY not in encoded and token not in encoded
    assert pi_runner.redact_event(event, (token,))["_dropped_keys"] == 2
    assert pi_runner.redact_event(event, (token,))["type"] == "message_update"  # real labels stay


def test_known_protocol_labels_and_numbers_survive_but_nothing_else():
    event = {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "provider": "alive-egress",
            "model": "alive-approved",
            "stopReason": "stop",
            "usage": {"input": 3, "output": 4, "totalTokens": 7, "note": PROMPT_CANARY},
        },
    }
    kept = pi_runner.redact_event(event)
    assert kept["message"]["stopReason"] == "stop"
    assert kept["message"]["usage"] == {
        "input": 3,
        "output": 4,
        "totalTokens": 7,
        "_dropped_keys": 1,
    }
    assert PROMPT_CANARY not in json.dumps(kept)


def test_depth_and_list_length_are_bounded():
    deep = current = {}
    for _ in range(40):
        current["data"] = {}
        current = current["data"]
    assert json.dumps(pi_runner.redact_event(deep)).count("data") < 10
    many = {"data": [{"input": i} for i in range(1000)]}
    assert len(pi_runner.redact_event(many)["data"]) == pi_runner.MAX_EVENT_LIST + 1


def test_untrusted_identity_and_usage_reported_by_pi_are_reduced():
    assert pi_runner.label_or_hash("alive-egress", {"alive-egress"}) == "alive-egress"
    odd = pi_runner.label_or_hash(PROMPT_CANARY, {"alive-egress"})
    assert odd.startswith("unexpected:") and PROMPT_CANARY not in odd
    assert pi_runner.numeric_only(
        {"input": 5, "cost": {"total": 0.0, "x": "no"}, "z": PROMPT_CANARY}
    ) == {
        "input": 5,
        "cost": {"total": 0.0},
    }
    assert pi_runner.numeric_only("not a dict") is None


# --- supply chain: the pinned bundle's bytes are enforced, not just recorded ---


def test_a_same_version_bundle_with_different_bytes_is_refused(settings, tmp_path):
    settings.alive_pi_cli = str(make_package(tmp_path))
    with pytest.raises(PiRunFailure) as refused:
        pi_runner.locate_pi(settings)
    assert refused.value.category == "pi_bundle_mismatch"


def test_the_pinned_digest_is_what_gets_accepted(settings, tmp_path):
    settings.alive_pi_cli = str(make_package(tmp_path))
    settings.alive_pi_bundle_sha256 = pi_runner.sha256_text("// bundle")
    assert pi_runner.locate_pi(settings).bundle_sha256 == settings.alive_pi_bundle_sha256
    settings.alive_pi_bundle_sha256 = ""  # an operator may disable the pin, explicitly
    assert pi_runner.locate_pi(settings).version == "1.4.0"
