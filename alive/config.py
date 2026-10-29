import csv
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = Field(
        repr=False,
        default="sqlite+aiosqlite:///.alive/development.db",
        validation_alias=AliasChoices("DATABASE_URL", "ALIVE_DSN", "database_url"),
    )
    alive_api_token: str = Field(default="", repr=False)
    alive_allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    alive_browser_origins: list[str] = ["http://127.0.0.1:8000"]
    alive_heartbeat_seconds: float = Field(10, ge=0.1)
    alive_pi_command: list[str] = ["pi"]
    alive_pi_provider: str = ""
    alive_pi_model: str = ""
    alive_agent_timeout: float = Field(120, ge=1)
    alive_meta_url: str = ""
    alive_meta_model: str = "muse-spark-1.3"
    alive_meta_base_url: str = "https://api.meta.ai/v1"
    alive_meta_api_key: str = Field(
        repr=False,
        default="",
        validation_alias=AliasChoices(
            "ALIVE_META_API_KEY", "MODEL_API_KEY", "META_API_KEY", "alive_meta_api_key"
        ),
    )
    alive_meta_timeout: float = Field(30, ge=1, le=120)
    alive_meta_max_output: int = Field(1536, ge=64, le=4096)
    alive_native_test_pages: str = ""
    alive_companion_micro_usd_limit: int | None = Field(default=None, ge=0)
    alive_research_meta_enabled: bool = False
    alive_claim_meta_enabled: bool = False
    alive_relationship_micro_usd_limit: int | None = Field(default=100000, ge=0)
    alive_relationship_allow_test_providers: bool = False
    alive_demo_tour_enabled: bool = False
    alive_role_models: dict[str, str] = {}
    alive_embedding_enabled: bool = False
    alive_embedding_path: str = ".alive/models/minilm"
    alive_cognitive_provider: str = "mock"
    alive_headless: bool = True
    alive_workspace: Path = Path(".alive/agent-workspace")

    @field_validator("database_url")
    @classmethod
    def async_driver(cls, value):
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


def _validate_api_token(token: str) -> str:
    # Match the local bearer contract for configured and persisted credentials.
    # Never include invalid credential content in the exception.
    if len(token) < 24 or not token.isascii() or any(not 33 <= ord(ch) <= 126 for ch in token):
        raise ValueError("Invalid local API token: require at least 24 visible ASCII characters")
    return token


def _restrict_token_file(path: str):
    if os.name == "nt":
        # chmod(0600) does not enforce a private Windows DACL. Remove inherited
        # grants before writing any secret; use the owner's SID, not a localized name.
        identity = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
            timeout=5,
        )
        sid = next(csv.reader([identity.stdout.strip()]))[1]
        if not sid.startswith("S-1-"):
            raise ValueError("Cannot determine local token owner")
        subprocess.run(
            ["icacls", path, "/inheritance:r", "/grant:r", f"*{sid}:(F)"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    # mkstemp already creates with mode0600 on POSIX; never broaden it.


def _create_local_token(path: Path):
    # Write/fsync privately, then publish a complete file without replacing any
    # concurrently-created credential. A failed/crashed write cannot publish empty.
    fd, temporary = tempfile.mkstemp(prefix=".token-", dir=path.parent)
    try:
        _restrict_token_file(temporary)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            fd = None
            stream.write(secrets.token_urlsafe(32))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass  # Read and validate the winner; never rotate or replace it.
    finally:
        if fd is not None:
            os.close(fd)
        Path(temporary).unlink(missing_ok=True)


def prepare_local(settings: Settings) -> str:
    Path(".alive").mkdir(mode=0o700, exist_ok=True)
    settings.alive_workspace.mkdir(parents=True, exist_ok=True)
    if settings.alive_api_token:
        return _validate_api_token(settings.alive_api_token)
    token_path = Path(".alive/token")
    try:
        try:
            token = token_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            _create_local_token(token_path)
            token = token_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError, subprocess.SubprocessError):
        # Decoder/OS exception context may include the credential's raw bytes.
        raise ValueError("Cannot securely load or create local API token") from None
    # Preserve legacy text-file newline compatibility, but reject token whitespace.
    return _validate_api_token(token.rstrip("\r\n"))
