from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Crop Health API"
    model_dir: Path = Path("models")
    model_version: str = "legacy"
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_dimension: int = 4096
    confidence_threshold: float = 0.80
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    strip_exif_gps: bool = True
    rate_limit: str = "30/minute"
    history_limit: int = 500
    frontend_dir: Path = Path("frontend")
    severity_bands_path: Path = Path("data/kb/severity.json")

    # ── Feature flags ──────────────────────────────────────────
    feature_pwa: bool = True
    feature_multilingual: bool = True
    feature_batch_scan: bool = True
    feature_weather_risk: bool = True
    feature_outbreak_map: bool = True
    feature_treatment_planner: bool = True
    feature_feedback_loop: bool = True
    feature_pdf_report: bool = True
    feature_expert_escalation: bool = True
    feature_analytics: bool = True

    # ── Feature-specific settings ──────────────────────────────
    feedback_dir: Path = Path("backend/data/feedback")
    admin_secret: str = "changeme-in-production"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def allowed_origins(self) -> list[str]:
        configured = [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]
        local_app_origins = [
            "http://127.0.0.1:8000",
            "http://localhost:8000",
            "http://127.0.0.1:8001",
            "http://localhost:8001",
        ]
        return list(dict.fromkeys([*configured, *local_app_origins]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
