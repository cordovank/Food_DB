from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal
from food_db.core.models import ParsedNutrition
from food_db.infra.ocr.extractor import FoodOCRExtractor
from food_db.infra.nlp.processor import FoodTextProcessor
from food_db.infra.ocr.ollama_vision import OllamaVisionOCRExtractor
from food_db.config import settings


def parse_text_to_nutrition(text: str) -> ParsedNutrition:
    processor = FoodTextProcessor()
    return processor.parse(text)

def ocr_image_to_nutrition(image_path: Path) -> ParsedNutrition:
    backend = (settings.ocr_backend or "tesseract").strip().lower()

    if backend == "ollama_vision":
        ocr = OllamaVisionOCRExtractor(
            host=settings.ollama_host,
            model=settings.ollama_vision_model,
        )
        text = ocr.extract_text(image_path)
    else:
        ocr = FoodOCRExtractor()
        text = ocr.extract_text(image_path)

    parsed = parse_text_to_nutrition(text)
    parsed.raw_text = text
    return parsed