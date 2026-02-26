from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OCRErrorType(str, Enum):
    IMAGE_NOT_FOUND = "Image file not found"
    INVALID_FORMAT = "Unsupported image format"
    MODEL_ERROR = "Model error"
    NETWORK_ERROR = "Network connection error"
    PROCESSING_ERROR = "Text extraction failed"


@dataclass
class OCRException(RuntimeError):
    error_type: OCRErrorType
    message: str
    original_error: Optional[BaseException] = None

    def __str__(self) -> str:
        return f"{self.error_type.value}: {self.message}"