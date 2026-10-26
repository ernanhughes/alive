from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = Field(
        default="sqlite+aiosqlite:///.alive/development.db",
        validation_alias=AliasChoices("DATABASE_URL", "ALIVE_DSN", "database_url"),
    )
    alive_api_token: str = ""
    alive_allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    alive_browser_origins: list[str] = ["http://127.0.0.1:8000"]
    alive_heartbeat_seconds: float = Field(10, ge=0.1)
    alive_pi_command: list[str] = ["pi"]
    alive_pi_provider: str = ""
    alive_pi_model: str = ""
    alive_agent_timeout: float = Field(120, ge=1)
    alive_meta_url: str = ""
    alive_meta_model: str = ""
    alive_meta_api_key: str = ""
    alive_headless: bool = True
    alive_workspace: Path = Path(".alive/agent-workspace")

    @field_validator("database_url")
    @classmethod
    def async_driver(cls, value):
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


def prepare_local(settings: Settings) -> str:
    Path(".alive").mkdir(exist_ok=True)
    settings.alive_workspace.mkdir(parents=True, exist_ok=True)
    if settings.alive_api_token:
        if len(settings.alive_api_token) < 24:
            raise ValueError("ALIVE_API_TOKEN must contain at least 24 characters")
        return settings.alive_api_token
    import secrets

    token_path = Path(".alive/token")
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    return token_path.read_text(encoding="utf-8").strip()
