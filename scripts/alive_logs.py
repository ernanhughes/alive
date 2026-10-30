"""Central log directory for ad-hoc/backend logs.

All ad-hoc redirection logs (``.consolidation-*.log``, ``.demo-*.log``,
``.qualification-*.log``, ``.review-*.log``) and backend process logs now live
under ``.alive/logs/`` (git-ignored via ``.alive/`` and ``*.log``) instead of
the repository root. Import this helper instead of hard-coding paths.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / ".alive" / "logs"


def ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR


def log_path(name: str) -> Path:
    """Return ``LOG_DIR / name``, creating the directory. Keeps leading dots."""
    ensure_log_dir()
    return LOG_DIR / name
