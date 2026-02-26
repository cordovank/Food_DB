from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Local configuration.

    Override values via environment variables or a `.env` file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Paths
    project_root: Path = Path(__file__).resolve().parents[2]
    db_path: Path = Path(__import__("os").getenv("DB_PATH", str(project_root / "data" / "food_database.db")))

    # Streamlit
    ui_host: str = __import__("os").getenv("UI_HOST", "0.0.0.0")  # bind on LAN
    ui_port: int = int(__import__("os").getenv("UI_PORT", "8501"))


settings = Settings()
