"""Download pinned public MiniLM assets locally; no browsing/history data is sent."""

import argparse
import json
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alive.config import Settings  # noqa: E402
from alive.memory import EMBED_MODEL, EMBED_REVISION  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        default=None,
        help="destination directory (default: ALIVE_EMBEDDING_PATH)",
    )
    args = parser.parse_args(argv)
    path = Path(args.path or Settings().alive_embedding_path)
    path.mkdir(parents=True, exist_ok=True)
    for remote, local in [("onnx/model.onnx", "model.onnx"), ("tokenizer.json", "tokenizer.json")]:
        source = hf_hub_download(
            EMBED_MODEL, remote, revision=EMBED_REVISION, local_files_only=False
        )
        shutil.copyfile(source, path / local)
    (path / "provenance.json").write_text(
        json.dumps({"model": EMBED_MODEL, "revision": EMBED_REVISION, "dimension": 384}) + "\n"
    )
    print("Pinned 384-dimensional MiniLM model prepared:", path)


if __name__ == "__main__":
    main()
