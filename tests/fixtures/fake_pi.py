"""A scripted stand-in for the Pi RPC process, for PiRunner and egress tests (ALIVE-PI-01B).

It speaks the exact record shapes observed from real Pi 1.4.0 and, for scenarios that need a model
call, reads its own `models.json` and makes a real HTTP request to the egress, as Pi would.
A real-Pi test (tests/test_pi_real.py) is the only authority on Pi's own behaviour.

The scenario is the first word of the prompt: `SCENARIO:<name> <rest>`.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request


def send(record):
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def provider_call(user_text, *, model=None, system="You are a fake coding agent."):
    cfg = os.environ["PI_CODING_AGENT_DIR"]
    provider = json.load(open(os.path.join(cfg, "models.json"), encoding="utf-8"))["providers"][
        "alive-egress"
    ]
    entry = provider["models"][0]
    body = {
        "model": model or entry["id"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": [{"type": "text", "text": user_text}]},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_completion_tokens": entry["maxTokens"],
    }
    request = urllib.request.Request(
        provider["baseUrl"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + provider["apiKey"],
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text, usage = "", None
            for raw in response.read().decode("utf-8").splitlines():
                if raw.startswith("data: ") and raw != "data: [DONE]":
                    chunk = json.loads(raw[6:])
                    for choice in chunk.get("choices", []):
                        text += (choice.get("delta") or {}).get("content") or ""
                    usage = chunk.get("usage") or usage
            return response.status, text, usage
    except urllib.error.HTTPError as error:
        return error.code, None, None


def assistant(text, stop="stop", usage=None):
    return {
        "type": "message_end",
        "message": {
            "role": "assistant",
            "provider": "alive-egress",
            "model": "alive-approved",
            "stopReason": stop,
            "content": [{"type": "text", "text": text or ""}],
            "usage": usage or {"input": 0, "output": 0, "totalTokens": 0},
        },
    }


def main():
    last_text = None
    for line in sys.stdin:
        command = json.loads(line)
        kind = command.get("type")
        if kind == "get_last_assistant_text":
            send(
                {
                    "id": command["id"],
                    "type": "response",
                    "command": kind,
                    "success": True,
                    "data": {"text": last_text} if last_text is not None else {},
                }
            )
            continue
        if kind == "get_session_stats":
            send(
                {
                    "id": command["id"],
                    "type": "response",
                    "command": kind,
                    "success": True,
                    "data": {"userMessages": 1, "assistantMessages": 1, "toolCalls": 0},
                }
            )
            continue
        if kind == "abort":
            send({"id": command.get("id"), "type": "response", "command": kind, "success": True})
            continue
        if kind != "prompt":
            continue
        prompt = command["message"]
        # `SCENARIO:<name> <approved prompt>` sends the text after the scenario word upstream;
        # `GATEWAY:<name> ...` sends the whole prompt (the scenario rides inside the instructions).
        tag, _, remainder = prompt.partition(":")
        echo_whole = tag == "GATEWAY"
        scenario, _, rest = (
            remainder.partition(" ") if tag in ("SCENARIO", "GATEWAY") else ("ok", "", prompt)
        )
        if scenario == "reject":
            send(
                {
                    "id": command["id"],
                    "type": "response",
                    "command": kind,
                    "success": False,
                    "error": "no",
                }
            )
            continue
        disposition = "handled" if scenario == "handled" else "started"
        send(
            {
                "id": command["id"],
                "type": "response",
                "command": kind,
                "success": True,
                "data": {"disposition": disposition},
            }
        )
        if scenario == "handled":
            continue
        send({"type": "agent_start"})
        if scenario == "crash":
            sys.exit(3)
        if scenario in ("malformed", "flood"):
            for _ in range(2 if scenario == "malformed" else 12):
                sys.stdout.write("this is not json {broken" + chr(10))
            sys.stdout.flush()
            if scenario == "malformed":
                last_text = rest or "settled despite noise"
                send(assistant(last_text))
                send({"type": "agent_end"})
                send({"type": "agent_settled"})
            continue
        if scenario == "tool":
            send({"type": "tool_execution_start", "toolName": "bash"})
        if scenario == "children":
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
            send({"type": "alive_fake.child", "pid": child.pid})
        if scenario == "no-settle":
            time.sleep(120)
        if scenario in ("env", "envvalues"):
            last_text = json.dumps(
                {k: v for k, v in os.environ.items() if k.startswith("PI_")}
                if scenario == "envvalues"
                else sorted(os.environ)
            )
            send(assistant(last_text))
            send({"type": "agent_end"})
            send({"type": "agent_settled"})
            continue
        if scenario == "argv":
            last_text = json.dumps(sys.argv[1:])
            send(assistant(last_text))
            send({"type": "agent_end"})
            send({"type": "agent_settled"})
            continue
        if scenario == "canary":
            # Try to read the developer's real Pi configuration: it must not be reachable.
            home = os.path.expanduser("~")
            reachable = os.path.exists(os.path.join(home, ".pi", "agent", "auth.json"))
            last_text = json.dumps(
                {"home": os.path.basename(home), "dev_pi_auth_reachable": reachable}
            )
            send(assistant(last_text))
            send({"type": "agent_end"})
            send({"type": "agent_settled"})
            continue
        if scenario == "text":
            last_text = rest
            send(assistant(rest))
            send({"type": "agent_end"})
            send({"type": "agent_settled"})
            continue
        # Model-call scenarios: make real requests to the egress, as Pi's provider layer would.
        calls = 1
        if scenario == "multi":
            count, _, rest = rest.partition(chr(32))
            calls = int(count)
        text = None
        for _ in range(calls):
            model = "gpt-evil" if scenario == "wrong-model" else None
            user_text = prompt if echo_whole else rest
            if scenario == "mismatch-prompt":
                user_text = "tampered prompt"
            status, text, usage = provider_call(user_text, model=model)
            send({"type": "alive_fake.provider_call", "status": status})
        last_text = text + chr(32) + "tampered" if scenario == "tamper" and text else text
        send(assistant(last_text, "stop" if text is not None else "error"))
        send({"type": "agent_end"})
        send({"type": "agent_settled"})


if __name__ == "__main__":
    main()
