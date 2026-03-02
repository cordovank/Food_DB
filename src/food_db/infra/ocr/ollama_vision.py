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

    # -------------------------
    # Uses Ollama HTTP API
    # -------------------------

    def call_model_via_http(self, base64_image):
        """ TODO - FIX """

        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "stream": False,
            "images": [base64_image],
        }

        url = self.host.rstrip("/") + "/api/generate"
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise OCRException(
                OCRErrorType.OLLAMA_MODEL_ERROR,
                f"Ollama HTTP {e.code}. Response: {body[:500]}",
                e,
            )
        except (urllib.error.URLError, ConnectionError, socket.timeout) as e:
            raise OCRException(
                OCRErrorType.OLLAMA_UNREACHABLE,
                f"Could not reach Ollama at {self.host}. Is it running?",
                e,
            )
        except Exception as e:
            raise OCRException(OCRErrorType.PROCESSING_ERROR, "Ollama vision OCR failed", e)

        try:
            data: dict[str, Any] = json.loads(raw)
        except Exception as e:
            raise OCRException(
                OCRErrorType.OLLAMA_BAD_RESPONSE,
                f"Non-JSON response from Ollama: {raw[:500]}",
                e,
            )

        text = (data.get("response") or "").strip()
        if not text:
            raise OCRException(
                OCRErrorType.OLLAMA_BAD_RESPONSE,
                "Ollama returned an empty response for the image.",
            )

        return text