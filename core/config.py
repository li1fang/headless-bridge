import functools
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "headless-bridge"
    auth_file: str = "/root/.codex/auth.json"
    codex_timeout: int = 600

    model_config = SettingsConfigDict(env_prefix="HB_", extra="ignore")


def _build_settings() -> Settings:
    return Settings()


@functools.lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return _build_settings()
