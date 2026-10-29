"""ALIVE-PI-01B: prove the pinned Pi starts and answers inside the built Docker image.

Runs the real PiRunner (real Node, real Pi 1.4.0, non-root, minimal env) against a throwaway
loopback server that speaks the OpenAI-compatible streaming shape ALIVE's egress speaks. There is
no provider, no credential and no network beyond 127.0.0.1.

    docker run --rm -e PYTHONPATH=/app \
        -v "$PWD/scripts/pi_image_smoke.py:/tmp/pi_image_smoke.py:ro" \
        --entrypoint python <image> /tmp/pi_image_smoke.py
"""

import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from alive.config import Settings
from alive.pi.runner import PiRunner, locate_pi

ANSWER = "pi-image-smoke-ok"
seen = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        seen.append({"path": self.path, "stream": body.get("stream"), "model": body.get("model")})

        def chunk(delta=None, finish=None, usage=None):
            payload = {"id": "x", "object": "chat.completion.chunk", "model": body["model"]}
            payload["choices"] = [{"index": 0, "delta": delta or {}, "finish_reason": finish}]
            if usage:
                payload["usage"] = usage
            return f"data: {json.dumps(payload)}\n\n"

        usage = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        out = (
            chunk({"role": "assistant", "content": ANSWER})
            + chunk(finish="stop")
            + "data: "
            + json.dumps({"id": "x", "choices": [], "usage": usage})
            + "\n\ndata: [DONE]\n\n"
        )
        data = out.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


async def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings = Settings(_env_file=None)
    install = locate_pi(settings)
    print(f"node={install.node} pi={install.version} bundle_sha256={install.bundle_sha256[:16]}")
    print(f"uid={os.getuid() if hasattr(os, 'getuid') else 'n/a'}")
    result = await PiRunner(settings).run(
        prompt="Say hello.",
        base_url=f"http://127.0.0.1:{server.server_address[1]}/v1",
        token="run-scoped-smoke-token",
        max_tokens=64,
        deadline=60,
        install=install,
    )
    server.shutdown()
    print(
        f"text={result.text!r} settled={result.settled} stop={result.stop_reason} "
        f"tool_events={result.tool_events} cleanup={result.cleanup_confirmed} "
        f"observed={result.observed_provider}/{result.observed_model} requests={len(seen)}"
    )
    ok = (
        result.failure is None
        and result.text == ANSWER
        and result.settled
        and result.tool_events == 0
        and result.cleanup_confirmed
        and len(seen) == 1
        and seen[0]["stream"] is True
    )
    print("PI IMAGE SMOKE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
