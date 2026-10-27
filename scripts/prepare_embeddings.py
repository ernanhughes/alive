"""Download pinned public MiniLM assets locally; no browsing/history data is sent."""

import json
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

from alive.config import Settings
from alive.memory import EMBED_MODEL, EMBED_REVISION


def main():
    path = Path(Settings().alive_embedding_path)
    path.mkdir(parents=True, exist_ok=True)
    for remote, local in [("onnx/model.onnx", "model.onnx"), ("tokenizer.json", "tokenizer.json")]:
        source = hf_hub_download(
            EMBED_MODEL, remote, revision=EMBED_REVISION, local_files_only=False
        )
        shutil.copyfile(source, path / local)
    (path / "provenance.json").write_text(
        json.dumps({"model": EMBED_MODEL, "revision": EMBED_REVISION, "dimension": 384})
    )
    print("Pinned 384-dimensional MiniLM model prepared:", path)


if __name__ == "__main__":
    main()
