from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    hindsight_api_key: str = ""
    hindsight_base_url: str = "https://api.hindsight.vectorize.io"
    hindsight_bank_id: str = "recallops-dev"
    groq_api_key: str = ""
    sqlite_db_path: str = "recallops.db"

    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
