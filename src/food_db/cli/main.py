from __future__ import annotations

import json
import typer

from datetime import date
from pathlib import Path
from rich import print
from rich.table import Table
from typing import Optional

from food_db.config import configure_logging, settings
from food_db.core.models import FoodCreate, FoodUpdate, FoodVariantCreate
from food_db.core.services import make_food_db
from food_db.core.usecases import parse_text_to_nutrition, ocr_image_to_nutrition

configure_logging(level="INFO")


def _parse_date(s: str | None) -> date | None:
    """
    Accepts:
      - YYYY-MM-DD
      - MM/DD/YYYY
    Returns a datetime.date or None.
    """
    if not s:
        return None
    s = s.strip()
    if not s:
        return None

    # ISO: 2027-08-04
    try:
        return date.fromisoformat(s)
    except Exception:
        pass

    # US: 08/04/2027
    try:
        mm, dd, yyyy = s.split("/")
        return date(int(yyyy), int(mm), int(dd))
    except Exception:
        raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY.")
    

app = typer.Typer(help="FoodDB CLI")

db_app = typer.Typer(help="Database commands")
food_app = typer.Typer(help="Food CRUD")
unit_app = typer.Typer(help="Unit commands")
variant_app = typer.Typer(help="Variant commands")
export_app = typer.Typer(help="Export commands")
parse_app = typer.Typer(help="Parse/OCR commands")

app.add_typer(db_app, name="db")
app.add_typer(food_app, name="food")
app.add_typer(unit_app, name="unit")
app.add_typer(variant_app, name="variant")
app.add_typer(export_app, name="export")
app.add_typer(parse_app, name="parse")


def _db():
    db = make_food_db(settings.db_path)
    return db


@db_app.command("init")
def db_init():
    """Create tables + seed base units."""
    db = _db()
    db.init()
    print(f"[green]OK[/green] initialized DB at {settings.db_path}")


@food_app.command("add")
def food_add(
    name: str = typer.Option(...),
    brand: Optional[str] = typer.Option(None),
    category: Optional[str] = typer.Option(None),
    serving_size: Optional[float] = typer.Option(None),
    serving_unit: Optional[str] = typer.Option(None),
    calories: Optional[float] = typer.Option(None),
    protein_g: Optional[float] = typer.Option(None),
    carbs_g: Optional[float] = typer.Option(None),
    fat_g: Optional[float] = typer.Option(None),
    fiber_g: Optional[float] = typer.Option(None),
    sugar_g: Optional[float] = typer.Option(None),
    sodium_mg: Optional[float] = typer.Option(None),
    upsert: bool = typer.Option(True, help="Upsert by name"),

    servings_per_container: Optional[float] = typer.Option(None),
    serving_size_text: Optional[str] = typer.Option(None),
    serving_mass_g: Optional[float] = typer.Option(None),
    saturated_fat_g: Optional[float] = typer.Option(None),
    trans_fat_g: Optional[float] = typer.Option(None),
    cholesterol_mg: Optional[float] = typer.Option(None),
    added_sugar_g: Optional[float] = typer.Option(None),
    vitamin_d_mcg: Optional[float] = typer.Option(None),
    calcium_mg: Optional[float] = typer.Option(None),
    iron_mg: Optional[float] = typer.Option(None),
    potassium_mg: Optional[float] = typer.Option(None),
    ingredients: Optional[str] = typer.Option(None),
    best_by_date: Optional[str] = typer.Option(None, help="YYYY-MM-DD or MM/DD/YYYY"),
):
    db = _db()
    best_by = _parse_date(best_by_date)

    data = FoodCreate(
        name=name,
        brand=brand,
        category=category,
        serving_size=serving_size,
        serving_unit=serving_unit,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        sugar_g=sugar_g,
        sodium_mg=sodium_mg,

        servings_per_container=servings_per_container,
        serving_size_text=serving_size_text,
        serving_mass_g=serving_mass_g,
        saturated_fat_g=saturated_fat_g,
        trans_fat_g=trans_fat_g,
        cholesterol_mg=cholesterol_mg,
        added_sugar_g=added_sugar_g,
        vitamin_d_mcg=vitamin_d_mcg,
        calcium_mg=calcium_mg,
        iron_mg=iron_mg,
        potassium_mg=potassium_mg,
        ingredients=ingredients,
        best_by_date=best_by,
    )
    out = db.upsert_food(data) if upsert else db.add_food(data)
    print(f"[green]OK[/green] saved food id={out.id} name='{out.name}'")


@food_app.command("get")
def food_get(food_id: int):
    db = _db()
    f = db.get_food(food_id)
    if not f:
        raise typer.Exit(code=1)
    print(json.dumps(f.model_dump(), indent=2, default=str))


@food_app.command("search")
def food_search(
    query: str,
    category: Optional[str] = typer.Option(None),
    brand: Optional[str] = typer.Option(None, help="Canonical or variant brand"),
    store: Optional[str] = typer.Option(None, help="Variant store name"),
    limit: int = typer.Option(50),
    min_score: float = typer.Option(0.35, help="Fuzzy threshold (0..1)"),
):
    db = _db()
    rows = db.search_foods_smart(
        query,
        category=category,
        brand=brand,
        store=store,
        limit=limit,
        min_score=min_score,
    )
    table = Table(title=f"Foods matching '{query}'")
    table.add_column("id", justify="right")
    table.add_column("name")
    table.add_column("brand")
    table.add_column("category")
    table.add_column("serving")
    table.add_column("kcal")
    table.add_column("P/C/F")
    for r in rows:
        serving = f"{r.serving_size or ''}{r.serving_unit or ''}".strip() or "-"
        pcf = f"{r.protein_g or '-'} / {r.carbs_g or '-'} / {r.fat_g or '-'}"
        table.add_row(str(r.id), r.name, r.brand or "-", r.category or "-", serving, str(r.calories or "-"), pcf)
    print(table)


@food_app.command("update")
def food_update(
    food_id: int,
    name: Optional[str] = typer.Option(None),
    brand: Optional[str] = typer.Option(None),
    category: Optional[str] = typer.Option(None),
    serving_size: Optional[float] = typer.Option(None),
    serving_unit: Optional[str] = typer.Option(None),
    calories: Optional[float] = typer.Option(None),
    protein_g: Optional[float] = typer.Option(None),
    carbs_g: Optional[float] = typer.Option(None),
    fat_g: Optional[float] = typer.Option(None),
    fiber_g: Optional[float] = typer.Option(None),
    sugar_g: Optional[float] = typer.Option(None),
    sodium_mg: Optional[float] = typer.Option(None),

    servings_per_container: Optional[float] = typer.Option(None),
    serving_size_text: Optional[str] = typer.Option(None),
    serving_mass_g: Optional[float] = typer.Option(None),
    saturated_fat_g: Optional[float] = typer.Option(None),
    trans_fat_g: Optional[float] = typer.Option(None),
    cholesterol_mg: Optional[float] = typer.Option(None),
    added_sugar_g: Optional[float] = typer.Option(None),
    vitamin_d_mcg: Optional[float] = typer.Option(None),
    calcium_mg: Optional[float] = typer.Option(None),
    iron_mg: Optional[float] = typer.Option(None),
    potassium_mg: Optional[float] = typer.Option(None),
    ingredients: Optional[str] = typer.Option(None),
    best_by_date: Optional[str] = typer.Option(None, help="YYYY-MM-DD or MM/DD/YYYY"),

):
    db = _db()
    best_by = _parse_date(best_by_date) if best_by_date is not None else None

    patch = FoodUpdate(
        name=name,
        brand=brand,
        category=category,
        serving_size=serving_size,
        serving_unit=serving_unit,
        calories=calories,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fat_g=fat_g,
        fiber_g=fiber_g,
        sugar_g=sugar_g,
        sodium_mg=sodium_mg,

        servings_per_container=servings_per_container,
        serving_size_text=serving_size_text,
        serving_mass_g=serving_mass_g,
        saturated_fat_g=saturated_fat_g,
        trans_fat_g=trans_fat_g,
        cholesterol_mg=cholesterol_mg,
        added_sugar_g=added_sugar_g,
        vitamin_d_mcg=vitamin_d_mcg,
        calcium_mg=calcium_mg,
        iron_mg=iron_mg,
        potassium_mg=potassium_mg,
        ingredients=ingredients,
        best_by_date=best_by,
    )
    out = db.update_food(food_id, patch)
    if not out:
        print("[red]Not found[/red]")
        raise typer.Exit(code=1)
    print(f"[green]OK[/green] updated id={out.id}")


@food_app.command("delete")
def food_delete(food_id: int):
    db = _db()
    ok = db.delete_food(food_id)
    print("[green]OK[/green]" if ok else "[red]Not found[/red]")


@unit_app.command("list")
def unit_list():
    db = _db()
    units = db.list_units()
    table = Table(title="Units")
    table.add_column("symbol")
    table.add_column("name")
    table.add_column("to_grams")
    for u in units:
        table.add_row(u.unit_symbol, u.unit_name, str(u.to_grams or "-"))
    print(table)


@unit_app.command("convert")
def unit_convert(value: float, from_unit: str, to_unit: str):
    db = _db()
    out = db.convert(value, from_unit, to_unit)
    print(f"{value} {from_unit} = {out:.4f} {to_unit}")


@variant_app.command("add")
def variant_add(
    food_id: int,
    store: Optional[str] = typer.Option(None),
    brand: Optional[str] = typer.Option(None),
    price: Optional[float] = typer.Option(None),
    package_size: Optional[float] = typer.Option(None),
    package_unit: Optional[str] = typer.Option(None),
    notes: Optional[str] = typer.Option(None),
):
    db = _db()
    v = db.add_variant(
        FoodVariantCreate(
            food_id=food_id,
            store_name=store,
            brand=brand,
            price=price,
            package_size=package_size,
            package_unit=package_unit,
            notes=notes,
        )
    )
    print(f"[green]OK[/green] added variant id={v.id} for food_id={food_id}")


@variant_app.command("list")
def variant_list(food_id: int):
    db = _db()
    rows = db.list_variants(food_id)
    table = Table(title=f"Variants for food_id={food_id}")
    table.add_column("id")
    table.add_column("store")
    table.add_column("brand")
    table.add_column("price")
    table.add_column("package")
    for r in rows:
        pkg = f"{r.package_size or ''}{r.package_unit or ''}".strip() or "-"
        table.add_row(str(r.id), r.store_name or "-", r.brand or "-", str(r.price or "-"), pkg)
    print(table)


@export_app.command("json")
def export_json(out: Path = typer.Option(Path("data/export.json"))):
    db = _db()
    p = db.export_json(out)
    print(f"[green]OK[/green] wrote {p}")


@export_app.command("csv")
def export_csv(out: Path = typer.Option(Path("data/export.csv"))):
    db = _db()
    p = db.export_csv(out)
    print(f"[green]OK[/green] wrote {p}")


@parse_app.command("text")
def parse_text(path: Optional[Path] = typer.Option(None), text: Optional[str] = typer.Option(None)):
    """Parse nutrition text (from --text or --path)."""
    if not text and path:
        text = path.read_text(encoding="utf-8")
    if not text:
        print("Provide --text or --path")
        raise typer.Exit(code=2)
    parsed = parse_text_to_nutrition(text)
    print(json.dumps(parsed.model_dump(), indent=2, default=str))


@parse_app.command("ocr")
def parse_ocr(image: Path, save: bool = typer.Option(False, help="Upsert parsed food into DB")):
    parsed = ocr_image_to_nutrition(image)
    print(json.dumps(parsed.model_dump(), indent=2, default=str))
    if save:
        db = _db()
        db.init()
        out = db.add_from_parsed(parsed)
        print(f"[green]OK[/green] saved id={out.id} name='{out.name}'")


if __name__ == "__main__":
    app()
