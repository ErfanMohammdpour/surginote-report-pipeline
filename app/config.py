from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve `.env` from repo root (parent of `app/`), not from the process cwd —
# otherwise `uvicorn` started from another directory may miss or load the wrong file.
_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SN_",
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SurgiNote Report Service"
    database_url: str = "sqlite:///./data/surginote.db"

    contradiction_score_ratio_threshold: float = 0.8
    flag_policy: str = "phase_window_then_case_wide"

    # Default report language for JSON narrative strings (templates). Override per request via query/body where supported.
    report_locale: Literal["en", "fa"] = Field(
        default="en",
        validation_alias=AliasChoices("SN_REPORT_LOCALE", "REPORT_LOCALE"),
        description="Default locale for structured report prose (score_narrative, limitations, flag notes)",
    )

    @classmethod
    @field_validator("report_locale", mode="before")
    def _normalize_report_locale(cls, v):  # type: ignore[no-untyped-def]
        if v is None:
            return "en"
        tok = str(v).strip().lower().replace("_", "-").split("-")[0]
        if tok in ("en", "fa"):
            return tok
        raise ValueError("report_locale must be 'en' or 'fa' (set SN_REPORT_LOCALE)")

    # validation_alias skips env_prefix → allow plain GEMINI_API_KEY in .env
    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "SN_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "SN_GEMINI_MODEL"))
    gemini_temperature: float = 0.35
    gemini_timeout_seconds: float = 120.0


settings = Settings()

PROJECT_ROOT = _REPO_ROOT
DATA_DIR = PROJECT_ROOT / "data"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
