from __future__ import annotations

import logging
from pathlib import Path

from food_db.core.models import ParsedNutrition
from food_db.infra.ocr.extractor import FoodOCRExtractor
from food_db.infra.nlp.processor import FoodTextProcessor
from food_db.infra.ocr.ollama_vision import OllamaVisionOCRExtractor
from food_db.config import settings

logger = logging.getLogger(__name__)


def parse_text_to_nutrition(text: str) -> ParsedNutrition:
    logger.debug("parse_text_to_nutrition: %d chars", len(text))
    processor = FoodTextProcessor()
    result = processor.parse(text)
    if result.warnings:
        for w in result.warnings:
            logger.warning("parse warning: %s", w)
    return result


def ocr_image_to_nutrition(image_path: Path) -> ParsedNutrition:
    backend = (settings.ocr_backend or "tesseract").strip().lower()
    logger.info("ocr_image_to_nutrition: backend=%r image=%s", backend, image_path)

    if backend == "ollama_vision":
        ocr = OllamaVisionOCRExtractor(
            host=settings.ollama_host,
            model=settings.ollama_vision_model,
        )
    else:
        ocr = FoodOCRExtractor()

    text = ocr.extract_text(image_path)
    logger.debug("ocr_image_to_nutrition: extracted %d chars", len(text))

    parsed = parse_text_to_nutrition(text)
    parsed.raw_text = text
    return parsed