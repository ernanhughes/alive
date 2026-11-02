from alive import ollama


def test_choose_chat_prefers_a_small_installed_model():
    names = [
        "qwen3-coder-next:latest",
        "qwen2.5:0.5b",
        "llama3.2:latest",
        "all-minilm:l6-v2",
    ]
    assert ollama.choose_chat(names) == "qwen2.5:0.5b"
    assert ollama.choose_chat(names, "llama3.2") == "llama3.2:latest"
    assert ollama.choose_chat(names, "missing:1b") is None


def test_choose_embedding_only_accepts_the_384_dimension_family():
    assert ollama.choose_embedding(["mxbai-embed-large:latest"]) is None
    assert ollama.choose_embedding(["nomic-embed-text:latest"]) is None
    assert ollama.choose_embedding(["all-minilm:l6-v2"]) == "all-minilm:l6-v2"
    assert ollama.choose_embedding(["all-minilm"]) == "all-minilm"


def test_probe_reports_detected_models_without_network(monkeypatch):
    monkeypatch.setattr(
        ollama,
        "_read_json",
        lambda url, timeout: {
            "models": [
                {"name": "qwen2.5:0.5b"},
                {"name": "all-minilm:l6-v2"},
                {"name": "mxbai-embed-large:latest"},
            ]
        },
    )
    status = ollama.probe("http://ollama:11434", timeout=0.1)
    assert status["available"] is True
    assert status["url"] == "http://ollama:11434"
    assert status["chat_model"] == "qwen2.5:0.5b"
    assert status["embedding_model"] == "all-minilm:l6-v2"
    assert status["models"] == [
        "qwen2.5:0.5b",
        "all-minilm:l6-v2",
        "mxbai-embed-large:latest",
    ]


def test_probe_is_explicit_when_unreachable_or_unconfigured(monkeypatch):
    def fail(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(ollama, "_read_json", fail)
    unreachable = ollama.probe("http://127.0.0.1:1", timeout=0.1)
    assert unreachable["available"] is False
    assert "not reachable" in unreachable["reason"]

    unconfigured = ollama.probe("")
    assert unconfigured["available"] is False
    assert unconfigured["reason"] == "Ollama URL not configured"


def test_pi_models_config_targets_the_openai_compatible_endpoint():
    config = ollama.pi_models_config("http://host.docker.internal:11434", "qwen2.5:0.5b")
    provider = config["providers"]["ollama"]
    assert provider["baseUrl"] == "http://host.docker.internal:11434/v1"
    assert provider["api"] == "openai-completions"
    assert provider["apiKey"] == "ollama"
    assert provider["models"] == [{"id": "qwen2.5:0.5b"}]
    assert ollama.openai_base("http://ollama:11434/v1") == "http://ollama:11434/v1"
