from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

import os

class Settings(BaseSettings):
    """Local configuration.

    Override values via environment variables or a `.env` file.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Paths
    project_root: Path = Path(__file__).resolve().parents[2]
    db_path: Path = Path(os.getenv("DB_PATH", str(project_root / "data" / "food_database.db")))

    # Streamlit
    ui_host: str = os.getenv("UI_HOST", "0.0.0.0")  # bind on LAN
    ui_port: int = int(os.getenv("UI_PORT", "8501"))

    # OCR backend: tesseract (current) or ollama_vision
    ocr_backend: str = os.getenv("OCR_BACKEND", "tesseract")  # tesseract|ollama_vision
    ollama_vision_model: str = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:8b")
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

settings = Settings()
