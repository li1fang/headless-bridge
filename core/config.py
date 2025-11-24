import functools
from pydantic import BaseSettings


class Settings(BaseSettings):
    service_name: str = "headless-bridge"
    auth_file: str = "/root/.codex/auth.json"
    codex_timeout: int = 600

    class Config:
        env_prefix = "HB_"


def _build_settings() -> Settings:
    return Settings()


@functools.lru_cache()
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return _build_settings()
