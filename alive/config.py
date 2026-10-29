import csv
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

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
    # ALIVE-PI-01B: which transport carries a migrated model operation. `direct` (default) is the
    # unchanged MetaProvider path; `pi` runs the operation through a governed Pi child process.
    alive_model_transport: Literal["direct", "pi"] = "direct"
    alive_pi_node: str = ""  # absolute path to node; empty = resolve `node` from PATH at run time
    alive_pi_cli: str = ""  # explicit Pi bundle path; empty = derived from alive_pi_runtime_dir
    alive_pi_runtime_dir: str = "pi-runtime"  # holds the lockfile-pinned Pi install
    alive_pi_pinned_version: str = "1.4.0"  # a different installed version is refused
    alive_pi_run_deadline: float = Field(120, ge=1, le=900)  # absolute per-run deadline, seconds
    alive_pi_max_provider_requests: int = Field(1, ge=1, le=4)  # upstream requests per Pi run
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


def _current_user_sid() -> str:
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
        timeout=5,
    )
    sid = next(csv.reader([identity.stdout.strip()]))[1].strip()
    if not sid.startswith("S-1-"):
        raise ValueError("Cannot determine local token owner")
    return sid


def _restrict_token_file(path: str):
    if os.name == "nt":
        # chmod(0600) does not enforce a private Windows DACL. Set an exact
        # protected owner-only DACL before writing any secret. icacls
        # /grant:r leaves other explicit default ACEs in place on some hosts,
        # so use the Win32 security API and the owner's SID, not a localized name.
        import ctypes
        from ctypes import wintypes

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.ULONG),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
        advapi32.SetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
        advapi32.SetFileSecurityW.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        # DACL_SECURITY_INFORMATION | PROTECTED_DACL_SECURITY_INFORMATION
        information = 0x00000004 | 0x80000000
        sid = _current_user_sid()
        descriptor = ctypes.c_void_p()
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            f"D:P(A;;FA;;;{sid})", 1, ctypes.byref(descriptor), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not advapi32.SetFileSecurityW(path, information, descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.LocalFree(descriptor)
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
