from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import select, delete, or_, and_, func
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from food_db.core.models import (
    Base,
    Food,
    Unit,
    FoodVariant,
    FoodCreate,
    FoodUpdate,
    FoodOut,
    UnitCreate,
    UnitOut,
    FoodVariantCreate,
    FoodVariantOut,
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemOut,
    InventoryRowOut
)
from food_db.infra.db.sql_db import DbHandle, make_db, get_session

import logging

logger = logging.getLogger(__name__)


DEFAULT_UNITS: list[UnitCreate] = [
    UnitCreate(unit_name="gram", unit_symbol="g", to_grams=1.0, is_base=True),
    UnitCreate(unit_name="milligram", unit_symbol="mg", to_grams=0.001, is_base=False),
    UnitCreate(unit_name="ounce", unit_symbol="oz", to_grams=28.349523125, is_base=False),
    UnitCreate(unit_name="pound", unit_symbol="lb", to_grams=453.59237, is_base=False),
]


@dataclass
class FoodRepository:
    db: DbHandle

    @classmethod
    def from_path(cls, db_path: Path) -> "FoodRepository":
        return cls(db=make_db(db_path))

    # -------------------------
    # Schema
    # -------------------------
    # MIGRATION RULE: only ADD columns here. Never rename or drop.
    # SQLite does not support DROP COLUMN in older versions.
    # For destructive changes, create a new migration script instead.
    
    def init_db(self) -> None:
        logger.info("Initializing DB schema at %s", self.db.engine.url)
        Base.metadata.create_all(self.db.engine)
        logger.debug("create_all complete")

        with self.db.engine.begin() as conn:
            # ── foods migration ────────────────────────────────────────────
            foods_cols = {row[1] for row in conn.execute(sql_text("PRAGMA table_info(foods)")).fetchall()}

            def add_food_col(name: str, ddl: str):
                if name not in foods_cols:
                    logger.info("Migrating foods: adding column %s %s", name, ddl)
                    conn.execute(sql_text(f"ALTER TABLE foods ADD COLUMN {name} {ddl}"))

            add_food_col("servings_per_container", "FLOAT")
            add_food_col("serving_size_text",      "VARCHAR")
            add_food_col("serving_mass_g",         "FLOAT")
            add_food_col("saturated_fat_g",        "FLOAT")
            add_food_col("trans_fat_g",            "FLOAT")
            add_food_col("cholesterol_mg",         "FLOAT")
            add_food_col("added_sugar_g",          "FLOAT")
            add_food_col("vitamin_d_mcg",          "FLOAT")
            add_food_col("calcium_mg",             "FLOAT")
            add_food_col("iron_mg",                "FLOAT")
            add_food_col("potassium_mg",           "FLOAT")
            add_food_col("ingredients",            "VARCHAR")
            add_food_col("best_by_date",           "DATE")

        # ── food_variants migration ────────────────────────────────────
        # Add new food_variants columns here as the schema evolves.
        # All columns currently match the ORM — no ALTER needed yet.
        # Example for future use:
        #   variant_cols = {row[1] for row in conn.execute(sql_text("PRAGMA table_info(food_variants)")).fetchall()}
        #   def add_variant_col(name, ddl):
        #       if name not in variant_cols:
        #           conn.execute(sql_text(f"ALTER TABLE food_variants ADD COLUMN {name} {ddl}"))
        #   add_variant_col("quantity_threshold", "FLOAT")

        # ── inventory_items migration ──────────────────────────────────
        # Add new inventory_items columns here as the schema evolves.
        # All columns currently match the ORM — no ALTER needed yet.
        # Example for future use:
        #   inv_cols = {row[1] for row in conn.execute(sql_text("PRAGMA table_info(inventory_items)")).fetchall()}
        #   def add_inv_col(name, ddl):
        #       if name not in inv_cols:
        #           conn.execute(sql_text(f"ALTER TABLE inventory_items ADD COLUMN {name} {ddl}"))
        #   add_inv_col("expiry_date", "DATE")

        # ── Seed units ─────────────────────────────────────────────────────
        with get_session(self.db) as s:
            existing = {u.unit_symbol for u in s.scalars(select(Unit)).all()}
            for u in DEFAULT_UNITS:
                if u.unit_symbol not in existing:
                    s.add(Unit(
                        unit_name=u.unit_name,
                        unit_symbol=u.unit_symbol,
                        to_grams=u.to_grams,
                        is_base=1 if u.is_base else 0,
                    ))
            s.commit()

    # -------------------------
    # Foods
    # -------------------------

    def add_food(self, data: FoodCreate) -> FoodOut:
        with get_session(self.db) as s:
            food = Food(**data.model_dump())
            s.add(food)
            s.commit()
            s.refresh(food)
            return self._food_out(food)

    def upsert_food_by_name(self, data: FoodCreate) -> FoodOut:
        with get_session(self.db) as s:
            existing = s.scalar(select(Food).where(Food.name == data.name))
            if existing:
                logger.info("upsert_food: updating existing food id=%d name=%r", existing.id, data.name)
                for k, v in data.model_dump().items():
                    setattr(existing, k, v)
                s.commit()
                s.refresh(existing)
                return self._food_out(existing)
            
            logger.info("upsert_food: inserting new food name=%r", data.name)
            food = Food(**data.model_dump())
            s.add(food)
            s.commit()
            s.refresh(food)
            return self._food_out(food)

    def get_food(self, food_id: int) -> Optional[FoodOut]:
        with get_session(self.db) as s:
            food = s.get(Food, food_id)
            return self._food_out(food) if food else None

    def get_food_by_name(self, name: str) -> Optional[FoodOut]:
        with get_session(self.db) as s:
            food = s.scalar(select(Food).where(Food.name == name))
            return self._food_out(food) if food else None

    def search_foods(self, query: str, category: Optional[str] = None) -> list[FoodOut]:
        q = f"%{query}%"
        with get_session(self.db) as s:
            stmt = select(Food).where((Food.name.ilike(q)) | (Food.category.ilike(q)))
            if category:
                stmt = stmt.where(Food.category == category)
            stmt = stmt.order_by(Food.name.asc())
            rows = s.scalars(stmt).all()
            return [self._food_out(r) for r in rows]

    def update_food(self, food_id: int, patch: FoodUpdate) -> Optional[FoodOut]:
        with get_session(self.db) as s:
            food = s.get(Food, food_id)
            if not food:
                logger.warning("update_food: food id=%d not found", food_id)
                return None
            for k, v in patch.model_dump(exclude_unset=True).items():
                setattr(food, k, v)
            s.commit()
            s.refresh(food)
            logger.info("update_food: updated food id=%d name=%r", food.id, food.name)
            return self._food_out(food)

    def delete_food(self, food_id: int) -> bool:
        with get_session(self.db) as s:
            res = s.execute(delete(Food).where(Food.id == food_id))
            s.commit()
            deleted = (res.rowcount or 0) > 0
            if deleted:
                logger.info("delete_food: removed food id=%d", food_id)
            else:
                logger.warning("delete_food: food id=%d not found", food_id)
            return deleted

    # -------------------------
    # Smart Search
    # -------------------------

    def list_unique_categories(self) -> list[str]:
        with get_session(self.db) as s:
            rows = s.scalars(select(Food.category).where(Food.category.is_not(None)).distinct()).all()
            return sorted({r for r in rows if r})

    def search_foods_filtered(
        self,
        query: str,
        *,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        store: Optional[str] = None,
        limit: int = 200,
    ) -> list[FoodOut]:
        """
        Broad SQL candidate retrieval (fast) + optional filters.

        IMPORTANT: SQL LIKE prefilter can miss typos. If it returns 0 rows,
        we fall back to a filtered-but-unscoped candidate list so Python fuzzy
        ranking can still find matches.
        """
        q_like = f"%{query}%"

        with get_session(self.db) as s:
            base = select(Food).outerjoin(FoodVariant, FoodVariant.food_id == Food.id)

            # Optional filters (apply to both primary query and fallback)
            preds = []

            if category:
                preds.append(Food.category == category)

            # Brand filter: accept either canonical brand OR any variant brand
            if brand:
                preds.append(or_(Food.brand == brand, FoodVariant.brand == brand))

            # Store filter: only via variants
            if store:
                preds.append(FoodVariant.store_name == store)

            # Text match across canonical + variant fields (fast narrowing)
            if query.strip():
                text_pred = or_(
                    Food.name.ilike(q_like),
                    Food.category.ilike(q_like),
                    Food.brand.ilike(q_like),
                    FoodVariant.brand.ilike(q_like),
                    FoodVariant.store_name.ilike(q_like),
                )
                preds_with_text = preds + [text_pred]
            else:
                preds_with_text = preds

            stmt = (
                base.where(and_(*preds_with_text)) if preds_with_text else base
            ).distinct().order_by(Food.name.asc()).limit(max(1, int(limit)))

            rows = s.scalars(stmt).all()

            # --- Fallback for fuzzy typos / OCR noise ---
            # If LIKE prefilter returns nothing, fetch a small filtered candidate
            # pool without the text predicate so Python fuzzy ranking can still
            # find near-matches. Capped well below candidate_limit to avoid
            # full-table scans on large DBs.
            _FALLBACK_LIMIT = 50
            if not rows and query.strip():
                logger.debug(
                    "search_foods_filtered: LIKE prefilter returned 0 rows for %r — "
                    "falling back to unscoped candidate pool (limit=%d)",
                    query,
                    _FALLBACK_LIMIT,
                )
                fallback_stmt = (
                    base.where(and_(*preds)) if preds else base
                ).distinct().order_by(Food.name.asc()).limit(_FALLBACK_LIMIT)
                rows = s.scalars(fallback_stmt).all()

            return [self._food_out(r) for r in rows]
    
    def list_foods_paged(self, *, offset: int = 0, limit: int = 50,) -> list[FoodOut]:
        """Return foods alphabetically for browse/empty-search display."""
        with get_session(self.db) as s:
            stmt = (
                select(Food)
                .order_by(Food.name.asc())
                .offset(offset)
                .limit(max(1, int(limit)))
            )
            rows = s.scalars(stmt).all()
            return [self._food_out(r) for r in rows]

    # -------------------------
    # Units
    # -------------------------

    def list_units(self) -> list[UnitOut]:
        with get_session(self.db) as s:
            units = s.scalars(select(Unit).order_by(Unit.unit_symbol.asc())).all()
            return [self._unit_out(u) for u in units]

    def add_unit(self, data: UnitCreate) -> UnitOut:
        with get_session(self.db) as s:
            unit = Unit(
                unit_name=data.unit_name,
                unit_symbol=data.unit_symbol,
                to_grams=data.to_grams,
                is_base=1 if data.is_base else 0,
            )
            s.add(unit)
            s.commit()
            s.refresh(unit)
            return self._unit_out(unit)

    def convert_units(self, value: float, from_symbol: str, to_symbol: str) -> float:
        """Convert weight units using `units.to_grams`.

        If units are missing or not weight-like, returns original value.
        """
        with get_session(self.db) as s:
            u_from = s.scalar(select(Unit).where(Unit.unit_symbol == from_symbol))
            u_to = s.scalar(select(Unit).where(Unit.unit_symbol == to_symbol))
            if not u_from or not u_to or u_from.to_grams is None or u_to.to_grams is None:
                return value
            grams = value * float(u_from.to_grams)
            return grams / float(u_to.to_grams)

    # -------------------------
    # Variants
    # -------------------------

    def add_variant(self, data: FoodVariantCreate) -> FoodVariantOut:
        with get_session(self.db) as s:
            v = FoodVariant(**data.model_dump())
            s.add(v)
            s.commit()
            s.refresh(v)
            return self._variant_out(v)

    def list_variants(self, food_id: int) -> list[FoodVariantOut]:
        with get_session(self.db) as s:
            rows = s.scalars(select(FoodVariant).where(FoodVariant.food_id == food_id).order_by(FoodVariant.created_at.desc())).all()
            return [self._variant_out(r) for r in rows]

    def list_unique_stores(self) -> list[str]:
        with get_session(self.db) as s:
            rows = s.scalars(select(FoodVariant.store_name).where(FoodVariant.store_name.is_not(None)).distinct()).all()
            return sorted({r for r in rows if r})

    def list_unique_brands(self) -> list[str]:
        with get_session(self.db) as s:
            # Canonical brands on foods
            canon = s.scalars(
                select(Food.brand).where(Food.brand.is_not(None)).distinct()
            ).all()

            # Variant brands
            variant = s.scalars(
                select(FoodVariant.brand).where(FoodVariant.brand.is_not(None)).distinct()
            ).all()

            return sorted({b for b in (canon + variant) if b})
        
    # -------------------------
    # Inventory
    # -------------------------
    
    def add_inventory_item(self, data: InventoryItemCreate) -> InventoryItemOut:
        with get_session(self.db) as s:
            item = InventoryItem(**data.model_dump(exclude_none=True))
            s.add(item)
            s.commit()
            s.refresh(item)
            return self._inventory_out(item)

    def list_inventory_for_variant(self, variant_id: int) -> list[InventoryItemOut]:
        from sqlalchemy import select
        with get_session(self.db) as s:
            rows = s.scalars(
                select(InventoryItem)
                .where(InventoryItem.variant_id == variant_id)
                .order_by(InventoryItem.purchase_date.desc())
            ).all()
            return [self._inventory_out(r) for r in rows]

    def update_inventory_item(self, item_id: int, patch: InventoryItemUpdate) -> InventoryItemOut | None:
        with get_session(self.db) as s:
            item = s.get(InventoryItem, item_id)
            if not item:
                return None
            for k, v in patch.model_dump(exclude_unset=True).items():
                setattr(item, k, v)
            s.commit()
            s.refresh(item)
            return self._inventory_out(item)

    def delete_inventory_item(self, item_id: int) -> bool:
        with get_session(self.db) as s:
            res = s.execute(delete(InventoryItem).where(InventoryItem.id == item_id))
            s.commit()
            return (res.rowcount or 0) > 0

    def list_inventory_all(self) -> list[dict]:
        """
        Admin/inventory page helper:
        return inventory rows with joined food + variant context for display.
        """
        with get_session(self.db) as s:
            stmt = (
                select(InventoryItem, FoodVariant, Food)
                .join(FoodVariant, FoodVariant.id == InventoryItem.variant_id)
                .join(Food, Food.id == FoodVariant.food_id)
                .order_by(InventoryItem.purchase_date.desc())
            )
            out = []
            for item, var, food in s.execute(stmt).all():
                out.append(InventoryRowOut(
                    inventory_id=item.id,
                    food_id=food.id,
                    food_name=food.name,
                    canonical_brand=food.brand,
                    store=var.store_name,
                    variant_brand=var.brand,
                    quantity=item.quantity,
                    unit=item.unit,
                    purchase_date=item.purchase_date,
                    variant_id=var.id,
                ))
            return out

    # -------------------------
    # Admin stats
    # -------------------------

    def admin_counts(self) -> dict:
        with get_session(self.db) as s:
            foods = s.scalar(select(func.count()).select_from(Food)) or 0
            variants = s.scalar(select(func.count()).select_from(FoodVariant)) or 0
            inv = s.scalar(select(func.count()).select_from(InventoryItem)) or 0
            return {"foods": int(foods), "variants": int(variants), "inventory_items": int(inv)}    

    # -------------------------
    # Export
    # -------------------------

    def export_foods(self) -> list[dict]:
        with get_session(self.db) as s:
            foods = s.scalars(select(Food).order_by(Food.name.asc())).all()
            return [self._food_out(f).model_dump() for f in foods]

    # -------------------------
    # Helpers
    # -------------------------

    @staticmethod
    def _food_out(food: Food) -> FoodOut:
        return FoodOut(
            id=food.id,
            name=food.name,
            brand=food.brand,
            category=food.category,

            serving_size=food.serving_size,
            serving_unit=food.serving_unit,
            servings_per_container=food.servings_per_container,
            serving_size_text=food.serving_size_text,
            serving_mass_g=food.serving_mass_g,

            calories=food.calories,
            protein_g=food.protein_g,
            carbs_g=food.carbs_g,
            fat_g=food.fat_g,
            fiber_g=food.fiber_g,
            sugar_g=food.sugar_g,
            sodium_mg=food.sodium_mg,
            created_at=food.created_at,
            updated_at=food.updated_at,

            saturated_fat_g=food.saturated_fat_g,
            trans_fat_g=food.trans_fat_g,
            cholesterol_mg=food.cholesterol_mg,
            added_sugar_g=food.added_sugar_g,

            vitamin_d_mcg=food.vitamin_d_mcg,
            calcium_mg=food.calcium_mg,
            iron_mg=food.iron_mg,
            potassium_mg=food.potassium_mg,

            ingredients=food.ingredients,
            best_by_date=food.best_by_date,
        )

    @staticmethod
    def _unit_out(unit: Unit) -> UnitOut:
        return UnitOut(
            id=unit.id,
            unit_name=unit.unit_name,
            unit_symbol=unit.unit_symbol,
            to_grams=unit.to_grams,
            is_base=bool(unit.is_base),
        )

    @staticmethod
    def _variant_out(v: FoodVariant) -> FoodVariantOut:
        return FoodVariantOut(
            id=v.id,
            food_id=v.food_id,
            store_name=v.store_name,
            brand=v.brand,
            price=v.price,
            package_size=v.package_size,
            package_unit=v.package_unit,
            notes=v.notes,
            created_at=v.created_at,
        )
    
    @staticmethod
    def _inventory_out(i: InventoryItem) -> InventoryItemOut:
        return InventoryItemOut(
            id=i.id,
            variant_id=i.variant_id,
            quantity=i.quantity,
            unit=i.unit,
            purchase_date=i.purchase_date,
        )