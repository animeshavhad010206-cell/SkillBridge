from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = f"sqlite:///{(BASE_DIR / 'skillbridge.db').as_posix()}"
    github_token: str = ""
    job_country: str = "India"
    job_refresh_hours: int = 12
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
