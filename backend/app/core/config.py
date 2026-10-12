from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Industrial Predict AI API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = True

    database_url: str

    rul_model_path: Path = Path(
        "artifacts/rul/rul_model.joblib"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()