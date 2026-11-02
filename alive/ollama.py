"""Read-only discovery of an optional local Ollama installation.

Nothing here starts Ollama, pulls a model or sends ALIVE data to a remote host. The capabilities
endpoint, the doctor and the Pi runner share this probe so their answers cannot drift.

The memory schema stores 384-dimensional vectors. Only 384-dimensional embedding models are
reported as compatible; ``mxbai-embed-large`` (1024) and ``nomic-embed-text`` (768) are not.
"""

import argparse
import json
import time
from urllib.request import urlopen

DEFAULT_URL = "http://127.0.0.1:11434"
# all-MiniLM is the same 384-dimensional family as the pinned local ONNX model.
EMBEDDING_PREFERENCE = ("all-minilm:l6-v2", "all-minilm")
# Small instruction-capable models first. A 50 GB coding model is not a safe automatic default.
CHAT_PREFERENCE = (
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "llama3.2:1b",
    "llama3.2:3b",
    "llama3.2:latest",
    "llama3.2",
    "qwen3:0.6b",
    "phi3:mini",
    "mistral:latest",
)
_CACHE = {}
_CACHE_SECONDS = 10.0


def _canonical(name):
    return name[:-7] if name.endswith(":latest") else name


def _pick(names, preference, explicit=""):
    wanted = _canonical(explicit) if explicit else ""
    if wanted:
        return next((name for name in names if _canonical(name) == wanted), None)
    for preferred in preference:
        match = next((name for name in names if _canonical(name) == _canonical(preferred)), None)
        if match:
            return match
    return None


def choose_chat(names, explicit=""):
    return _pick(names, CHAT_PREFERENCE, explicit)


def choose_embedding(names):
    return _pick(names, EMBEDDING_PREFERENCE)


def _read_json(url, timeout):
    with urlopen(url, timeout=timeout) as response:  # noqa: S310 - configured local URL
        return json.loads(response.read().decode("utf-8"))


def openai_base(url):
    base = url.rstrip("/")
    return base if base.endswith("/v1") else base + "/v1"


def probe(url, timeout=1.5, chat_model=""):
    """Return an honest, bounded snapshot of one Ollama endpoint. Never raises for I/O."""
    result = {
        "available": False,
        "url": url.rstrip("/") if url else "",
        "models": [],
        "chat_model": None,
        "embedding_model": None,
        "requested_chat_model": chat_model or "",
        "reason": "",
    }
    if not url:
        result["reason"] = "Ollama URL not configured"
        return result
    try:
        data = _read_json(result["url"] + "/api/tags", timeout)
    except Exception as exc:  # noqa: BLE001 - an optional probe must not fail capabilities
        result["reason"] = f"Ollama not reachable at {result['url']} ({type(exc).__name__})"
        return result
    entries = data.get("models", []) if isinstance(data, dict) else []
    if not isinstance(entries, list):
        entries = []
    names = []
    for item in entries:
        name = (item.get("name") or item.get("model")) if isinstance(item, dict) else None
        if name and name not in names:
            names.append(name)
    result.update(
        available=True,
        models=names[:50],
        chat_model=choose_chat(names, chat_model),
        embedding_model=choose_embedding(names),
    )
    if result["chat_model"]:
        result["reason"] = "Ollama reachable; local chat model available"
    elif chat_model:
        result["reason"] = f"Ollama reachable; requested model {chat_model!r} is not installed"
    else:
        result["reason"] = "Ollama reachable; no supported chat model installed"
    return result


def probe_cached(url, chat_model="", timeout=1.5):
    """Cache the probe briefly so a polling dashboard does not re-connect every request."""
    key = (url.rstrip("/") if url else "", chat_model, timeout)
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    value = probe(url, timeout=timeout, chat_model=chat_model)
    _CACHE[key] = (now, value)
    return value


def pi_models_config(url, model):
    """The minimal Pi models.json entry for an OpenAI-compatible Ollama endpoint."""
    return {
        "providers": {
            "ollama": {
                "baseUrl": openai_base(url),
                "api": "openai-completions",
                "apiKey": "ollama",
                "models": [{"id": model}],
            }
        }
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Probe a local Ollama endpoint without changing it"
    )
    parser.add_argument("--url", default="")
    parser.add_argument("--chat-model", default="")
    parser.add_argument("--timeout", type=float, default=1.5)
    args = parser.parse_args(argv)
    print(json.dumps(probe(args.url, timeout=args.timeout, chat_model=args.chat_model), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
