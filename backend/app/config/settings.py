from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentic Cinema"
    app_env: str = "development"
    debug: bool = True

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on", "t", "dev", "development")
        return bool(v)

    # Gemini API
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    # Hugging Face
    hf_token: str = ""
    hf_image_model: str = "black-forest-labs/FLUX.1-schnell"

    # Google Cloud / Vertex AI
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"

    # Parallel
    parallel_api_key: str = ""

    # Storage
    gcs_bucket_name: str = ""

    # Database
    database_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()