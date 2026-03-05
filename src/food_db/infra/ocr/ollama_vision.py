from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from openai import OpenAI
from pathlib import Path
from typing import Any

from food_db.config import settings
from food_db.infra.ocr.errors import OCRException, OCRErrorType
from food_db.infra.ocr.image_utils import image_path_to_png_bytes, encode_image


DEFAULT_PROMPT = (
    "You are reading a nutrition facts label.\n"
    "Extract ALL text exactly as it appears from the image.\n"
    "Return ONLY the text content. No commentary, no markdown fences.\n"
)


@dataclass
class OllamaVisionOCRExtractor:
    """
    Vision-based OCR using a local Ollama server.


    # Uses Ollama HTTP API:
    #   POST {host}/api/generate
    #   { model, prompt, images:[base64], stream:false }
    """
    host: str
    model: str
    timeout_s: float = 120.0
    prompt: str = DEFAULT_PROMPT

    def extract_text(self, image_path: Path) -> str:
        if not image_path.exists():
            raise OCRException(OCRErrorType.IMAGE_NOT_FOUND, f"Could not read image: {image_path}")

        try:
            png_bytes = image_path_to_png_bytes(image_path)
            base64_image = encode_image(png_bytes)
        except Exception as e:
            raise OCRException(OCRErrorType.INVALID_IMAGE, f"Invalid/unsupported image: {image_path}", e)

        text = self.call_model_via_api(base64_image)
        return text
    
    # -------------------------
    # Uses OpenAI-compatible API  
    # -------------------------

    def call_model_via_api(self, base64_image):
        client = OpenAI(api_key="OLLAMA", base_url=settings.ollama_host)
        messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}", "detail": "auto"}},
                {"type": "text", "text": self.prompt},
            ],
        }
        ]
        
        completion = client.chat.completions.create(model=settings.ollama_vision_model, messages=messages,)
       
        text = completion.choices[0].message.content
        if not text:
            raise OCRException(
                OCRErrorType.OLLAMA_BAD_RESPONSE,
                "Ollama returned an empty response for the image.",
            )
        
        return text
