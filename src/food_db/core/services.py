from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from food_db.core.models import FoodCreate, FoodUpdate, ParsedNutrition, FoodVariantCreate
from food_db.core.repository import FoodRepository
from food_db.utils.search import fuzzy_score


@dataclass
class FoodDatabase:
    """Service layer facade.

    All DB reads/writes go through this instance.
    """

    repo: FoodRepository

    def init(self) -> None:
        self.repo.init_db()

    # -------------------------
    # Foods
    # -------------------------

    def add_food(self, data: FoodCreate):
        return self.repo.add_food(data)

    def upsert_food(self, data: FoodCreate):
        return self.repo.upsert_food_by_name(data)

    def get_food(self, food_id: int):
        return self.repo.get_food(food_id)

    def search_foods(self, query: str, category: Optional[str] = None):
        return self.repo.search_foods(query, category=category)

    def update_food(self, food_id: int, patch: FoodUpdate):
        return self.repo.update_food(food_id, patch)

    def delete_food(self, food_id: int) -> bool:
        return self.repo.delete_food(food_id)

    # -------------------------
    # Units + conversions
    # -------------------------

    def list_units(self):
        return self.repo.list_units()

    def convert(self, value: float, from_unit: str, to_unit: str) -> float:
        return self.repo.convert_units(value, from_unit, to_unit)

    # -------------------------
    # Smart Search
    # -------------------------

    def categories(self) -> list[str]:
        return self.repo.list_unique_categories()

    def search_foods_smart(
        self,
        query: str,
        *,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        store: Optional[str] = None,
        limit: int = 50,
        min_score: float = 0.35,
        candidate_limit: int = 200,
    ):
        """
        Smart search = SQL prefilter (candidates) + fuzzy ranking + filters.
        """
        if not query.strip():
            return []

        candidates = self.repo.search_foods_filtered(
            query,
            category=category,
            brand=brand,
            store=store,
            limit=candidate_limit,
        )

        scored: list[tuple[float, object]] = []
        for f in candidates:
            # Score against multiple “views” of the food (more forgiving)
            candidate_texts = [
                f.name or "",
                f"{f.brand or ''} {f.name or ''}",
                f"{f.category or ''} {f.name or ''}",
            ]
            score = max(fuzzy_score(query, t) for t in candidate_texts)
            if score >= float(min_score):
                scored.append((score, f))

        scored.sort(key=lambda x: (-x[0], (x[1].name or "").lower()))
        return [f for _, f in scored[: max(1, int(limit))]]
    
    # -------------------------
    # Variants
    # -------------------------

    def add_variant(self, data: FoodVariantCreate):
        return self.repo.add_variant(data)

    def list_variants(self, food_id: int):
        return self.repo.list_variants(food_id)

    def stores(self) -> list[str]:
        return self.repo.list_unique_stores()

    def brands(self) -> list[str]:
        return self.repo.list_unique_brands()

    # -------------------------
    # Workflows
    # -------------------------

    def add_from_parsed(self, parsed: ParsedNutrition):
        """Convert ParsedNutrition into a FoodCreate, then upsert."""
        if not parsed.name:
            raise ValueError("ParsedNutrition.name is required to add to DB")

        data = FoodCreate(
            name=parsed.name,
            brand=parsed.brand,
            category=parsed.category,

            serving_size=parsed.serving_size,
            serving_unit=parsed.serving_unit,
            servings_per_container=parsed.servings_per_container,
            serving_size_text=parsed.serving_size_text,
            serving_mass_g=parsed.serving_mass_g,

            calories=parsed.calories,
            protein_g=parsed.protein_g,
            carbs_g=parsed.carbs_g,
            fat_g=parsed.fat_g,

            saturated_fat_g=parsed.saturated_fat_g,
            trans_fat_g=parsed.trans_fat_g,
            cholesterol_mg=parsed.cholesterol_mg,

            fiber_g=parsed.fiber_g,
            sugar_g=parsed.sugar_g,
            added_sugar_g=parsed.added_sugar_g,
            sodium_mg=parsed.sodium_mg,

            vitamin_d_mcg=parsed.vitamin_d_mcg,
            calcium_mg=parsed.calcium_mg,
            iron_mg=parsed.iron_mg,
            potassium_mg=parsed.potassium_mg,

            ingredients=parsed.ingredients,
            best_by_date=parsed.best_by_date,
        )
        return self.upsert_food(data)

    def export_json(self, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.repo.export_foods()
        out_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
        return out_path

    def export_csv(self, out_path: Path) -> Path:
        try:
            import pandas as pd
        except Exception as e:
            raise RuntimeError("CSV export requires optional dependency: uv sync --extra export") from e

        out_path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.repo.export_foods()
        pd.DataFrame(rows).to_csv(out_path, index=False)
        return out_path


def make_food_db(db_path: Path) -> FoodDatabase:
    return FoodDatabase(repo=FoodRepository.from_path(db_path))
