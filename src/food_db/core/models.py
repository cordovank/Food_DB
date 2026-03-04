from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# -------------------------
# SQLAlchemy ORM
# -------------------------


class Base(DeclarativeBase):
    pass


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Canonical identity
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    category: Mapped[Optional[str]] = mapped_column(String, default=None, index=True)

    # Optional canonical brand (variants can override)
    brand: Mapped[Optional[str]] = mapped_column(String, default=None)

    # Base serving
    serving_size: Mapped[Optional[float]] = mapped_column(Float, default=None)
    serving_unit: Mapped[Optional[str]] = mapped_column(String, default=None)  # e.g., g, oz
    # Serving / package context
    servings_per_container: Mapped[Optional[float]] = mapped_column(Float, default=None)
    serving_size_text: Mapped[Optional[str]] = mapped_column(String, default=None)  # raw label phrase
    serving_mass_g: Mapped[Optional[float]] = mapped_column(Float, default=None)   # parsed grams when present

    # Nutrition (per serving)
    calories: Mapped[Optional[float]] = mapped_column(Float, default=None)
    protein_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    carbs_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    fat_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    fiber_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    sugar_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    sodium_mg: Mapped[Optional[float]] = mapped_column(Float, default=None)

    # Additional nutrition facts
    saturated_fat_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    trans_fat_g: Mapped[Optional[float]] = mapped_column(Float, default=None)
    cholesterol_mg: Mapped[Optional[float]] = mapped_column(Float, default=None)
    added_sugar_g: Mapped[Optional[float]] = mapped_column(Float, default=None)

    vitamin_d_mcg: Mapped[Optional[float]] = mapped_column(Float, default=None)
    calcium_mg: Mapped[Optional[float]] = mapped_column(Float, default=None)
    iron_mg: Mapped[Optional[float]] = mapped_column(Float, default=None)
    potassium_mg: Mapped[Optional[float]] = mapped_column(Float, default=None)

    ingredients: Mapped[Optional[str]] = mapped_column(String, default=None)
    best_by_date: Mapped[Optional[date]] = mapped_column(Date, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    units = relationship("FoodUnit", back_populates="food", cascade="all, delete-orphan")
    variants = relationship("FoodVariant", back_populates="food", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    unit_name: Mapped[str] = mapped_column(String, unique=True)  # e.g., gram
    unit_symbol: Mapped[str] = mapped_column(String, unique=True)  # e.g., g

    # Conversion factor to grams for weight-like units.
    # For non-weight units (e.g., "serving"), leave as NULL and handle via FoodUnit.
    to_grams: Mapped[Optional[float]] = mapped_column(Float, default=None)
    is_base: Mapped[bool] = mapped_column(Integer, default=0)


class FoodUnit(Base):
    __tablename__ = "food_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)

    # How many grams in 1 unit for this specific food.
    # Example: 1 tbsp peanut butter = 16g.
    unit_to_grams: Mapped[float] = mapped_column(Float)

    food = relationship("Food", back_populates="units")
    unit = relationship("Unit")

    __table_args__ = (
        UniqueConstraint("food_id", "unit_id", name="uq_food_unit"),
    )


class FoodVariant(Base):
    """Store/brand specific variant for the same canonical food.

    Example: "Greek Yogurt" as Food, with variants for Costco/Aldi different price/package.
    """

    __tablename__ = "food_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), index=True)

    store_name: Mapped[Optional[str]] = mapped_column(String, default=None, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String, default=None, index=True)

    price: Mapped[Optional[float]] = mapped_column(Float, default=None)  # USD

    # Package sizing (e.g., 907g tub)
    package_size: Mapped[Optional[float]] = mapped_column(Float, default=None)
    package_unit: Mapped[Optional[str]] = mapped_column(String, default=None)

    notes: Mapped[Optional[str]] = mapped_column(String, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    food = relationship("Food", back_populates="variants")
    inventory_items = relationship("InventoryItem", back_populates="variant", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_variant_store_brand", "store_name", "brand"),
    )


class InventoryItem(Base):
    """Optional inventory tracking: what you currently have on hand."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("food_variants.id"), index=True)

    quantity: Mapped[Optional[float]] = mapped_column(Float, default=None)
    unit: Mapped[Optional[str]] = mapped_column(String, default=None)
    purchase_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    variant = relationship("FoodVariant", back_populates="inventory_items")


# -------------------------
# Pydantic (API layer)
# -------------------------


class FoodCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None

    serving_size: Optional[float] = None
    serving_unit: Optional[str] = None
    servings_per_container: Optional[float] = None
    serving_size_text: Optional[str] = None
    serving_mass_g: Optional[float] = None

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None

    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    added_sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None

    vitamin_d_mcg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None

    ingredients: Optional[str] = None
    best_by_date: Optional[date] = None


class FoodUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None

    serving_size: Optional[float] = None
    serving_unit: Optional[str] = None
    servings_per_container: Optional[float] = None
    serving_size_text: Optional[str] = None
    serving_mass_g: Optional[float] = None

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None

    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    added_sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None

    vitamin_d_mcg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None

    ingredients: Optional[str] = None
    best_by_date: Optional[date] = None


class FoodOut(BaseModel):
    id: int
    name: str
    brand: Optional[str]
    category: Optional[str]

    serving_size: Optional[float]
    serving_unit: Optional[str]
    servings_per_container: Optional[float] = None
    serving_size_text: Optional[str] = None
    serving_mass_g: Optional[float] = None

    calories: Optional[float]
    protein_g: Optional[float]
    carbs_g: Optional[float]
    fat_g: Optional[float]

    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None

    fiber_g: Optional[float]
    sugar_g: Optional[float]
    added_sugar_g: Optional[float] = None
    sodium_mg: Optional[float]

    vitamin_d_mcg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None

    ingredients: Optional[str] = None
    best_by_date: Optional[date] = None

    created_at: datetime
    updated_at: datetime


class UnitCreate(BaseModel):
    unit_name: str
    unit_symbol: str
    to_grams: Optional[float] = None
    is_base: bool = False


class UnitOut(BaseModel):
    id: int
    unit_name: str
    unit_symbol: str
    to_grams: Optional[float]
    is_base: bool


class FoodVariantCreate(BaseModel):
    food_id: int
    store_name: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    package_size: Optional[float] = None
    package_unit: Optional[str] = None
    notes: Optional[str] = None


class FoodVariantOut(BaseModel):
    id: int
    food_id: int
    store_name: Optional[str]
    brand: Optional[str]
    price: Optional[float]
    package_size: Optional[float]
    package_unit: Optional[str]
    notes: Optional[str]
    created_at: datetime


class ParsedNutrition(BaseModel):
    """Output of OCR/NLP pipeline (what we can confidently extract)."""

    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None

    serving_size: Optional[float] = None
    serving_unit: Optional[str] = None
    servings_per_container: Optional[float] = None
    serving_size_text: Optional[str] = None
    serving_mass_g: Optional[float] = None

    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    cholesterol_mg: Optional[float] = None

    fiber_g: Optional[float] = None
    sugar_g: Optional[float] = None
    added_sugar_g: Optional[float] = None
    sodium_mg: Optional[float] = None

    vitamin_d_mcg: Optional[float] = None
    calcium_mg: Optional[float] = None
    iron_mg: Optional[float] = None
    potassium_mg: Optional[float] = None

    ingredients: Optional[str] = None
    best_by_date: Optional[date] = None

    raw_text: Optional[str] = Field(default=None, description="Original extracted text")
    warnings: list[str] = Field(default_factory=list)

# --- add near other Pydantic models ---

class InventoryItemCreate(BaseModel):
    variant_id: int
    quantity: Optional[float] = None
    unit: Optional[str] = None
    purchase_date: Optional[datetime] = None  # if None, DB default is fine


class InventoryItemUpdate(BaseModel):
    quantity: Optional[float] = None
    unit: Optional[str] = None
    purchase_date: Optional[datetime] = None


class InventoryItemOut(BaseModel):
    id: int
    variant_id: int
    quantity: Optional[float]
    unit: Optional[str]
    purchase_date: datetime

class InventoryRowOut(BaseModel):
    inventory_id: int
    food_id: int
    food_name: str
    canonical_brand: Optional[str]
    store: Optional[str]
    variant_brand: Optional[str]
    quantity: Optional[float]
    unit: Optional[str]
    purchase_date: datetime
    variant_id: int