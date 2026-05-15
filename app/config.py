from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SN_", env_file=".env", extra="ignore")

    app_name: str = "SurgiNote Report Service"
    database_url: str = "sqlite:///./data/surginote.db"

    contradiction_score_ratio_threshold: float = 0.8
    flag_policy: str = "phase_window_then_case_wide"

    # validation_alias skips env_prefix → allow plain GEMINI_API_KEY in .env
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "SN_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.0-flash", validation_alias=AliasChoices("GEMINI_MODEL", "SN_GEMINI_MODEL"))
    gemini_temperature: float = 0.35
    gemini_timeout_seconds: float = 120.0


settings = Settings()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
