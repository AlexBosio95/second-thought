from pathlib import Path
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_model: str = ""
    typesafe_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    typesafe_base_url: str = "https://api.typesafe.ai/v1"
    jev_model: str = "jev-1.13.0"
    intent_threshold: float = Field(.75, ge=0, le=1)
    evidence_threshold: float = Field(.80, ge=0, le=1)
    supported_threshold: float = Field(.80, ge=0, le=1)
    safe_threshold: float = Field(.85, ge=0, le=1)
    high_risk_safe_threshold: float = Field(.90, ge=0, le=1)
    human_review_threshold: float = Field(.80, ge=0, le=1)
    next_action_threshold: float = Field(.80, ge=0, le=1)
    http_timeout_seconds: float = Field(30, gt=0, le=120)
    audit_db: str = "backend/audit.sqlite3"

    @property
    def database_path(self) -> Path:
        path = Path(self.audit_db)
        return path if path.is_absolute() else ROOT / path

    @property
    def ready(self) -> bool:
        return bool(self.openrouter_api_key.get_secret_value() and self.openrouter_model
                    and self.typesafe_api_key.get_secret_value())
