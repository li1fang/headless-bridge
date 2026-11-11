from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "headless-bridge"
    backend: Literal["fixture", "codex"] = "fixture"
    auth_file: Path = Path.home() / ".codex" / "auth.json"
    codex_binary: str = "codex"
    codex_timeout: float = Field(default=10, ge=0.1, le=600)
    max_concurrency: int = Field(default=1, ge=1, le=4)
    output_limit: int = Field(default=16384, ge=256, le=1048576)
    workspace_root: Path = Path(".runs")
    model_config = SettingsConfigDict(env_prefix="HB_", extra="ignore")
