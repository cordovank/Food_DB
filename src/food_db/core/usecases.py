from __future__ import annotations

from pathlib import Path

from food_db.core.models import ParsedNutrition
from food_db.infra.ocr.extractor import FoodOCRExtractor
from food_db.infra.nlp.processor import FoodTextProcessor


def parse_text_to_nutrition(text: str) -> ParsedNutrition:
    processor = FoodTextProcessor()
    return processor.parse(text)


def ocr_image_to_nutrition(image_path: Path) -> ParsedNutrition:
    ocr = FoodOCRExtractor()
    text = ocr.extract_text(image_path)
    parsed = parse_text_to_nutrition(text)
    parsed.raw_text = text
    return parsed
