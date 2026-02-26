from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from food_db.core.models import ParsedNutrition


_NUM = r"(?P<val>\d+(?:\.\d+)?)"
_UNIT = r"(?P<unit>mg|g|oz|lb|cal|kcal)"


@dataclass
class FoodTextProcessor:
    """Regex-first parser for Nutrition Facts-like text.

    Goal: be robust to OCR noise and avoid heavy NLP deps.
    """

    def parse(self, text: str) -> ParsedNutrition:
        raw = text or ""
        t = self._normalize(raw)
        warnings: list[str] = []

        out = ParsedNutrition(raw_text=raw)

        # Name heuristics: first non-empty line that isn't 'nutrition facts'
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        for ln in lines[:5]:
            if "nutrition facts" in ln.lower():
                continue
            if len(ln) >= 3:
                out.name = ln.strip()[:120]
                break

        # Serving size
        # examples: "Serving size 2/3 cup (55g)" / "Serving Size: 30 g" / "Serving 1 bar (40g)"
        serving_match = re.search(r"serving\s*(?:size)?\s*[:\-]?\s*(?P<body>[^\n]+)", t, flags=re.I)
        if serving_match:
            body = serving_match.group("body")
            # Prefer grams/oz inside parentheses
            m = re.search(r"\((" + _NUM + r")\s*(" + _UNIT + r")\)", body, flags=re.I)
            if not m:
                m = re.search(_NUM + r"\s*" + _UNIT, body, flags=re.I)
            if m:
                out.serving_size = float(m.group("val"))
                unit = m.group("unit").lower()
                out.serving_unit = "kcal" if unit == "cal" else unit
            else:
                warnings.append("Serving size line found but could not parse numeric unit.")

        # Calories: handle "Calories 120" or "Energy 500kJ / 120kcal"
        cal = self._first_number(r"(?:calories|calorie)\s*[:\-]?\s*" + _NUM, t)
        if cal is None:
            cal = self._first_number(r"(?:energy)\s*[:\-]?.*?" + _NUM + r"\s*(?:kcal|cal)", t)
        if cal is not None:
            out.calories = cal

        # Macronutrients (g)
        out.protein_g = self._grams("protein", t)
        out.carbs_g = self._grams(r"total\s*carbohydrate|carbohydrate|carb", t)
        out.fat_g = self._grams(r"total\s*fat|fat", t)
        out.fiber_g = self._grams(r"dietary\s*fiber|fiber|fibre", t)
        out.sugar_g = self._grams(r"total\s*sugars|sugars|sugar", t)

        # Sodium (mg)
        sodium = self._first_number(r"sodium\s*[:\-]?\s*" + _NUM + r"\s*mg", t)
        if sodium is not None:
            out.sodium_mg = sodium

        # Simple brand/category extraction (optional)
        brand = self._capture_line(r"(?:brand|manufacturer)\s*[:\-]\s*(.+)$", t)
        if brand:
            out.brand = brand

        cat = self._capture_line(r"(?:category)\s*[:\-]\s*(.+)$", t)
        if cat:
            out.category = cat

        # Warnings for missing essentials
        if not out.name:
            warnings.append("Could not infer product name (consider passing --name).")
        if out.serving_size is None or out.serving_unit is None:
            warnings.append("Serving size missing or incomplete.")

        out.warnings = warnings
        return out

    # -------------------------
    # Helpers
    # -------------------------

    def _normalize(self, text: str) -> str:
        t = text
        t = t.replace("\u00a0", " ")
        t = re.sub(r"[\t\r]+", " ", t)
        # collapse multiple spaces
        t = re.sub(r"[ ]{2,}", " ", t)
        return t

    def _first_number(self, pattern: str, text: str) -> Optional[float]:
        m = re.search(pattern, text, flags=re.I | re.S)
        if not m:
            return None
        try:
            return float(m.group("val"))
        except Exception:
            return None

    def _grams(self, nutrient_pattern: str, text: str) -> Optional[float]:
        # Match "Protein 7g" or "Protein: 7 g"; ignore "%DV".
        pattern = rf"(?:{nutrient_pattern})\s*[:\-]?\s*" + _NUM + r"\s*g\b"
        return self._first_number(pattern, text)

    def _capture_line(self, pattern: str, text: str) -> Optional[str]:
        m = re.search(pattern, text, flags=re.I | re.M)
        if not m:
            return None
        val = m.group(1).strip()
        return val[:120] if val else None
