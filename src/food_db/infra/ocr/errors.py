from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OCRErrorType(str, Enum):
    IMAGE_NOT_FOUND = "image_not_found | Image file not found"
    INVALID_IMAGE = "invalid_image"
    OLLAMA_UNREACHABLE = "ollama_unreachable"
    OLLAMA_BAD_RESPONSE = "ollama_bad_response"
    OLLAMA_MODEL_ERROR = "ollama_model_error"
    PROCESSING_ERROR = "processing_error | Text extraction failed"

@dataclass
class OCRException(RuntimeError):
    error_type: OCRErrorType
    message: str
    original_error: Exception | None = None

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"