from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_sqlite_url() -> str:
    # Абсолютный путь: иначе при другом cwd создаётся другая schedule.db и «логин не подходит»
    return f"sqlite:///{(_PROJECT_ROOT / 'schedule.db').as_posix()}"


class Settings(BaseSettings):
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    database_url: str = Field(default_factory=_default_sqlite_url)

    class Config:
        env_file = ".env"


settings = Settings()
