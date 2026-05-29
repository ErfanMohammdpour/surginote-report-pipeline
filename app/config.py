from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SN_",
        env_file=_REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SurgiNote Report Service"
    database_url: str = Field(
        default="postgresql+psycopg://surginote:surginote@localhost:5432/surginote",
        description="PostgreSQL primary database URL. SQLite still accepted for local pytest.",
    )

    redis_url: str = "redis://localhost:6379/0"
    secret_provider: str = "env"  # env | mapped (extend for vault/aws in prod)

    # Object storage (MinIO / S3)
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "surginote-uploads"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = False

    max_upload_bytes: int = 50 * 1024 * 1024
    idempotency_ttl_hours: int = 24

    contradiction_score_ratio_threshold: float = 0.8
    flag_policy: str = "phase_window_then_case_wide"
    rules_config_path: str = "config/contradiction_rules.yaml"

    report_locale: Literal["en", "fa"] = Field(
        default="en",
        validation_alias=AliasChoices("SN_REPORT_LOCALE", "REPORT_LOCALE"),
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

    gemini_api_key: str | None = Field(default=None, validation_alias=AliasChoices("GEMINI_API_KEY", "SN_GEMINI_API_KEY"))
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias=AliasChoices("GEMINI_MODEL", "SN_GEMINI_MODEL"))
    gemini_temperature: float = 0.35
    gemini_timeout_seconds: float = 120.0

    webhook_signing_key: str | None = None
    webhook_max_retries: int = 3
    alert_webhook_url: str | None = None

    # CORS — comma-separated allowed origins, e.g. "https://app.example.com"
    cors_origins: str = "*"

    # Rate limiting — e.g. "60/minute", "1000/hour"
    rate_limit: str = "120/minute"

    # When true, async report stages run inline (dev/test)
    sync_jobs: bool = Field(default=False, validation_alias=AliasChoices("SN_SYNC_JOBS", "SYNC_JOBS"))
    skip_object_storage: bool = Field(
        default=False,
        validation_alias=AliasChoices("SN_SKIP_OBJECT_STORAGE", "SKIP_OBJECT_STORAGE"),
    )


settings = Settings()

PROJECT_ROOT = _REPO_ROOT
DATA_DIR = PROJECT_ROOT / "data"
RULES_PATH = PROJECT_ROOT / settings.rules_config_path
CANONICAL_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "canonical.schema.json"


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def resolve_gemini_api_key() -> str | None:
    """Prefer secret provider mapping over raw settings field."""
    from app.infrastructure.secrets import get_secret_provider

    prov = get_secret_provider(settings.secret_provider)
    hit = prov.get_secret("gemini_api_key") or prov.get_secret("GEMINI_API_KEY")
    if hit:
        return hit
    raw = settings.gemini_api_key
    return raw.strip() if raw and raw.strip() else None
