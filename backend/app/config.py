from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    environment: str = "development"
    jwt_secret_key: str = ""
    jwt_access_token_minutes: int = 60
    ml_ingest_token: str = ""
    sensor_ingest_token: str = ""
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'instance' / 'amrin.db').as_posix()}"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )
    upload_folder: str = str(BACKEND_DIR / "uploads" / "evidence")
    max_content_length: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
