from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

import logging
import os


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger. Call once from app entry points (app.py, cli/main.py)."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )

class Settings(BaseSettings):
    """Local configuration.

    Override values via environment variables or a `.env` file.
    All fields use pydantic-settings env loading — do NOT use os.getenv()
    inside this class body, as that bypasses .env file support.
    """

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    db_path: Optional[Path] = Field(default=None)
    # db_path: Path = Path(os.getenv("DB_PATH", str(project_root / "data" / "food_database.db")))

    # Streamlit
    ui_host: str = Field(default="0.0.0.0")  # bind on LAN
    ui_port: int = Field(default=8501)

    # OCR backend: tesseract (current) or ollama_vision
    ocr_backend: str = Field(default="tesseract")
    ocr_tesseract_cmd: Optional[str] = Field(
        default=None,
        description=(
            "Absolute path to the tesseract binary. "
            "Leave unset to use whatever is on PATH (works on Linux and most macOS installs). "
            "Override via OCR_TESSERACT_CMD env var or .env file. "
            "Example: OCR_TESSERACT_CMD=/opt/homebrew/bin/tesseract"
        ),
    )
    ollama_vision_model: str = Field(default="qwen3-vl:8b")
    ollama_host: str = Field(default="http://localhost:11434")

    # Search defaults
    search_min_score:      float = Field(default=0.35)
    search_candidate_limit: int  = Field(default=200)
    search_result_limit:    int  = Field(default=50)

    def model_post_init(self, __context) -> None:
        # Resolve db_path default after project_root is known
        if self.db_path is None:
            object.__setattr__(
                self, "db_path", self.project_root / "data" / "food_database.db"
            )

            
settings = Settings()
