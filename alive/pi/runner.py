"""PiRunner: an ALIVE-owned supervisor for one Pi RPC process (ALIVE-PI-01B).

Pi is treated as an untrusted child. The command-line restrictions below are defense in depth,
not the security boundary: the boundary is that Pi never holds the real provider credential
(it holds a run-scoped token for ALIVE's own egress) and cannot make ALIVE forward a request that
ALIVE has not approved.

Pinned to the contract verified against Pi 1.4.0 (docs/rpc.md): strict LF-delimited JSONL; a
`prompt` response only means "accepted"; `agent_end` is NOT final; `agent_settled` is.
"""

import asyncio
import contextlib
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from alive.pi.process import ManagedProcess, shielded

PI_PACKAGE = "@earendil-works/pi-coding-agent"
PROVIDER_ID = "alive-egress"
MODEL_ID = "alive-approved"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Verified against Pi 1.4.0 `docs/cli.md`. Every one disables an authority Pi would otherwise have.
FLAGS = (
    "--mode",
    "rpc",
    "--provider",
    PROVIDER_ID,
    "--model",
    MODEL_ID,
    "--no-tools",
    "--no-extensions",
    "--no-skills",
    "--no-prompt-templates",
    "--no-context-files",
    "--no-session",
    "--no-mcp",
    "--no-approve",
    "--offline",
)
SETTINGS = {"retry": {"enabled": False, "provider": {"maxRetries": 0}}}
MAX_MALFORMED_FRAMES = 5
PROMPT_ID, TEXT_ID, STATS_ID = "alive-prompt", "alive-text", "alive-stats"

# What a retained Pi event may contain. Pi's output is UNTRUSTED: it can put anything in a key or a
# value, so an event is rebuilt from this allowlist rather than scrubbed. Unknown keys are dropped
# (and counted), free text is always hashed, protocol labels survive only if they are known ones.
EVENT_TYPES = frozenset(
    {
        "response",
        "agent_start",
        "agent_end",
        "agent_settled",
        "turn_start",
        "turn_end",
        "message_start",
        "message_update",
        "message_end",
        "tool_execution_start",
        "tool_execution_update",
        "tool_execution_end",
        "auto_retry_start",
        "auto_retry_end",
        "queue_update",
        "compaction_start",
        "compaction_end",
        "alive.malformed_frame",
    }
)
LABELS = {  # key -> the only string values kept verbatim
    "type": EVENT_TYPES,
    "role": frozenset({"user", "assistant", "toolResult", "system"}),
    "stopReason": frozenset({"stop", "length", "toolUse", "error", "aborted"}),
    "disposition": frozenset({"started", "handled", "queued"}),
    "command": frozenset({"prompt", "get_last_assistant_text", "get_session_stats", "abort"}),
    "provider": frozenset({PROVIDER_ID}),
    "model": frozenset({MODEL_ID}),
    "api": frozenset({"openai-completions"}),
    "id": frozenset({PROMPT_ID, TEXT_ID, STATS_ID}),
}
FREE_TEXT_KEYS = frozenset({"error", "reason", "text", "content", "toolName", "name", "thinking"})
STRUCTURE_KEYS = frozenset({"data", "message", "usage", "cost", "details"})
NUMBER_KEYS = frozenset(
    {
        "input",
        "output",
        "cacheRead",
        "cacheWrite",
        "totalTokens",
        "total",
        "userMessages",
        "assistantMessages",
        "toolCalls",
        "toolResults",
        "totalMessages",
        "timestamp",
    }
)
BOOL_KEYS = frozenset({"success"})
ALLOWED_KEYS = frozenset(LABELS) | FREE_TEXT_KEYS | STRUCTURE_KEYS | NUMBER_KEYS | BOOL_KEYS
MAX_EVENT_DEPTH, MAX_EVENT_LIST = 6, 20


class PiRunFailure(RuntimeError):
    """A typed failure of the Pi process itself (not of the upstream provider)."""

    def __init__(self, category, message=""):
        self.category = category
        super().__init__(f"{category}: {message}" if message else category)


@dataclass(frozen=True)
class PiInstall:
    node: str
    cli: str
    version: str
    bundle_sha256: str


@dataclass
class PiResult:
    text: str | None = None
    settled: bool = False
    accepted: bool = False
    observed_provider: str | None = None
    observed_model: str | None = None
    stop_reason: str | None = None
    pi_usage: dict | None = None
    stats: dict | None = None
    malformed_frames: int = 0
    stderr_bytes: int = 0
    stderr_sha256: str | None = None
    events: list = field(default_factory=list)
    cleanup_confirmed: bool = False
    failure: PiRunFailure | None = None
    tool_events: int = 0


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def locate_pi(settings):
    """Resolve and verify the pinned Pi install. A different version is refused, not tolerated."""
    node = settings.alive_pi_node or shutil.which("node")
    if not node:
        raise PiRunFailure("pi_unavailable", "node was not found")
    if settings.alive_pi_cli:
        cli = Path(settings.alive_pi_cli)
    else:
        runtime = Path(settings.alive_pi_runtime_dir)
        runtime = runtime if runtime.is_absolute() else REPO_ROOT / runtime
        cli = (
            runtime
            / "node_modules"
            / "@earendil-works"
            / "pi-coding-agent"
            / "dist"
            / "bundle"
            / "cli.js"
        )
    if not cli.is_file():
        raise PiRunFailure("pi_unavailable", f"Pi bundle not found at {cli.name}")
    package = cli.parents[2] / "package.json"
    try:
        meta = json.loads(package.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PiRunFailure("pi_unavailable", "cannot read the Pi package metadata") from exc
    if meta.get("name") != PI_PACKAGE:
        raise PiRunFailure("pi_version_mismatch", f"unexpected package {meta.get('name')!r}")
    if meta.get("version") != settings.alive_pi_pinned_version:
        raise PiRunFailure(
            "pi_version_mismatch",
            f"installed {meta.get('version')!r}, pinned {settings.alive_pi_pinned_version!r}",
        )
    digest = hashlib.sha256()
    with cli.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    pinned = settings.alive_pi_bundle_sha256
    if pinned and digest.hexdigest() != pinned:
        raise PiRunFailure("pi_bundle_mismatch", "the Pi bundle is not the pinned bundle")
    return PiInstall(node, str(cli), meta["version"], digest.hexdigest())


def build_env(config_dir, temp_dir):
    """The ONLY environment Pi receives. Nothing is inherited from ALIVE's process."""
    env = {
        "PI_CODING_AGENT_DIR": str(config_dir),
        "PI_OFFLINE": "1",
        "PI_TELEMETRY": "0",
        "PI_SKIP_VERSION_CHECK": "1",
        "HOME": str(config_dir),
        "USERPROFILE": str(config_dir),
        "TMPDIR": str(temp_dir),
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
    }
    if sys.platform == "win32":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")  # Node needs it to start
    return env


def models_config(base_url, token, max_tokens):
    return {
        "providers": {
            PROVIDER_ID: {
                "baseUrl": base_url,
                "apiKey": token,  # a run-scoped token for ALIVE's egress, never a provider key
                "api": "openai-completions",
                "compat": {
                    "supportsStore": False,
                    "supportsDeveloperRole": True,
                    "supportsReasoningEffort": False,
                    "supportsUsageInStreaming": True,
                    "maxTokensField": "max_completion_tokens",
                },
                "models": [
                    {
                        "id": MODEL_ID,
                        "name": MODEL_ID,
                        "reasoning": False,
                        "input": ["text"],
                        "contextWindow": 128000,
                        "maxTokens": max_tokens,
                        # Pi prices an unknown custom model at zero. That is not evidence that the
                        # call was free; ALIVE records its own usage and never reads this value.
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                    }
                ],
            }
        }
    }


def flags_identity(max_tokens):
    """A hash of everything that shapes Pi's authority, excluding the per-run token and URL."""
    shape = models_config("<egress>", "<token>", max_tokens)
    return hashlib.sha256(
        json.dumps([list(FLAGS), SETTINGS, shape], sort_keys=True).encode()
    ).hexdigest()


def redact_event(value, secrets=(), key=None, depth=0):
    """Rebuild an untrusted Pi event from the allowlist. Nothing outside it is retained."""
    if depth > MAX_EVENT_DEPTH:
        return {"truncated": True}
    if isinstance(value, dict):
        kept = {}
        dropped = 0
        for name, item in value.items():
            if name in ALLOWED_KEYS:
                kept[name] = redact_event(item, secrets, name, depth + 1)
            else:
                dropped += 1  # the key itself may be hostile (a prompt or a token): never copied
        if dropped:
            kept["_dropped_keys"] = dropped
        return kept
    if isinstance(value, list):
        out = [redact_event(item, secrets, key, depth + 1) for item in value[:MAX_EVENT_LIST]]
        if len(value) > MAX_EVENT_LIST:
            out.append({"truncated": len(value) - MAX_EVENT_LIST})
        return out
    if isinstance(value, str):
        if any(secret and secret in value for secret in secrets):
            return {"redacted": "credential", "sha256": sha256_text(value)}
        if key in LABELS and value in LABELS[key]:
            return value
        return {"sha256": sha256_text(value), "chars": len(value)}
    if isinstance(value, bool):
        return value if key in BOOL_KEYS else None
    if isinstance(value, int | float):
        return value if key in NUMBER_KEYS else None
    return None


def label_or_hash(value, allowed):
    """A protocol label reported by Pi, kept only if it is one we know; else an opaque marker."""
    if value is None or value in allowed:
        return value
    return "unexpected:" + sha256_text(str(value))[:16]


def numeric_only(value, depth=0):
    """Pi's own usage/cost report, reduced to numbers under known keys (it is untrusted)."""
    if not isinstance(value, dict) or depth > 2:
        return None
    out = {}
    for name, item in value.items():
        if name in NUMBER_KEYS and isinstance(item, int | float) and not isinstance(item, bool):
            out[name] = item
        elif name in STRUCTURE_KEYS and isinstance(item, dict):
            nested = numeric_only(item, depth + 1)
            if nested:
                out[name] = nested
    return out or None


class PiRunner:
    def __init__(self, settings, install=None):
        self.settings = settings
        self._install = install  # test seam: a fake Pi bundle

    def install(self):
        return self._install or locate_pi(self.settings)

    async def run(
        self,
        *,
        prompt,
        base_url,
        token,
        max_tokens,
        deadline,
        on_event=None,
        on_running=None,
        install=None,
        result=None,
    ):
        # A caller may hand in the result so what was learned survives a cancellation.
        install = install or self.install()
        result = result if result is not None else PiResult()
        root = Path(tempfile.mkdtemp(prefix="alive-pi-"))
        config_dir, work_dir, temp_dir = root / "config", root / "cwd", root / "tmp"
        for directory in (config_dir, work_dir, temp_dir):
            directory.mkdir()
        (config_dir / "models.json").write_text(
            json.dumps(models_config(base_url, token, max_tokens)), encoding="utf-8"
        )
        (config_dir / "settings.json").write_text(json.dumps(SETTINGS), encoding="utf-8")
        managed = None
        stderr_task = None
        try:
            managed = await ManagedProcess.spawn(
                [install.node, install.cli, *FLAGS],
                env=build_env(config_dir, temp_dir),
                cwd=str(work_dir),
            )
            stderr_task = asyncio.ensure_future(self._drain_stderr(managed, result))
            async with asyncio.timeout(deadline):
                if on_running is not None:
                    # Pi calls the egress the moment it gets the prompt, so the run must already
                    # be admitted as RUNNING by then.
                    await on_running()
                await self._conversation(managed, prompt, token, result, on_event)
        except TimeoutError:
            result.failure = PiRunFailure("pi_deadline", f"no settlement within {deadline}s")
        except PiRunFailure as failure:
            result.failure = failure
        finally:
            # Cleanup must finish even if this task is cancelled again; the cancel is re-raised.
            if managed is not None:
                result.cleanup_confirmed = await shielded(managed.terminate_tree())
            if stderr_task is not None:
                stderr_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await stderr_task
            shutil.rmtree(root, ignore_errors=True)
        if managed is not None and not result.cleanup_confirmed and result.failure is None:
            result.failure = PiRunFailure(
                "pi_cleanup_unconfirmed", "process tree not confirmed gone"
            )
        return result

    async def _drain_stderr(self, managed, result):
        digest = hashlib.sha256()
        while chunk := await managed.stderr.read(4096):
            digest.update(chunk)
            result.stderr_bytes += len(chunk)
        result.stderr_sha256 = digest.hexdigest() if result.stderr_bytes else None

    @staticmethod
    async def _read_record(managed, result):
        """Read one LF-framed JSON record. Returns None for a malformed frame (counted)."""
        try:
            line = await managed.stdout.readuntil(b"\n")
        except asyncio.IncompleteReadError as exc:
            raise PiRunFailure("pi_process_exited", "stdout closed mid-record") from exc
        except asyncio.LimitOverrunError as exc:
            raise PiRunFailure("pi_protocol_error", "a record exceeded the frame limit") from exc
        line = line[:-1]
        if line.endswith(b"\r"):
            line = line[:-1]
        try:
            record = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            result.malformed_frames += 1
            if result.malformed_frames > MAX_MALFORMED_FRAMES:
                raise PiRunFailure("pi_protocol_error", "too many malformed frames") from None
            return None
        return record if isinstance(record, dict) else None

    @staticmethod
    async def _send(managed, command):
        managed.stdin.write((json.dumps(command) + "\n").encode("utf-8"))
        await managed.stdin.drain()

    async def _record(self, record, token, result, on_event):
        redacted = redact_event(record, (token,))
        if len(result.events) < MAX_EVENT_LIST * 10:
            result.events.append(redacted)
        if on_event is not None:
            await on_event(redacted)

    async def _conversation(self, managed, prompt, token, result, on_event):
        await self._send(managed, {"id": PROMPT_ID, "type": "prompt", "message": prompt})
        while True:
            record = await self._read_record(managed, result)
            if record is None:
                await self._record({"type": "alive.malformed_frame"}, token, result, on_event)
                continue
            await self._record(record, token, result, on_event)
            kind = record.get("type")
            if kind == "response" and record.get("id") == PROMPT_ID:
                if not record.get("success"):
                    raise PiRunFailure("pi_prompt_rejected", "Pi refused the prompt")
                if (record.get("data") or {}).get("disposition") == "handled":
                    # "handled": no run started, so waiting for settlement would hang forever.
                    raise PiRunFailure("pi_prompt_handled", "Pi did not start a run")
                result.accepted = True
            elif kind and kind.startswith("tool_execution"):
                result.tool_events += 1  # PI-01B runs with no tools; any such event is hostile
            elif kind == "message_end":
                message = record.get("message") or {}
                if message.get("role") == "assistant":
                    result.observed_provider = label_or_hash(
                        message.get("provider"), LABELS["provider"]
                    )
                    result.observed_model = label_or_hash(message.get("model"), LABELS["model"])
                    result.stop_reason = label_or_hash(
                        message.get("stopReason"), LABELS["stopReason"]
                    )
                    result.pi_usage = numeric_only(message.get("usage"))
            elif kind == "agent_settled":
                result.settled = True
                break
        # `agent_end` was not enough: only `agent_settled` means no retry or follow-up is pending.
        await self._send(managed, {"id": TEXT_ID, "type": "get_last_assistant_text"})
        await self._send(managed, {"id": STATS_ID, "type": "get_session_stats"})
        pending = {TEXT_ID, STATS_ID}
        while pending:
            record = await self._read_record(managed, result)
            if record is None:
                continue
            await self._record(record, token, result, on_event)
            if record.get("type") == "response" and record.get("id") in pending:
                pending.discard(record["id"])
                data = record.get("data") or {}
                if record["id"] == TEXT_ID:
                    result.text = data.get("text")
                else:
                    result.stats = data
