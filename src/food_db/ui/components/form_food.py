# src/food_db/ui/components/form_food.py
from __future__ import annotations
from datetime import date
import streamlit as st
from food_db.core.models import FoodCreate, FoodUpdate, ParsedNutrition
from .select_or_other import select_or_other


def _opt_num(
    label: str,
    value: float | None,
    step: float,
    key: str,
    min_value: float = 0.0,
) -> float | None:
    """Number input for optional nutrition fields.

    - If the stored value is None, renders empty (no default zero).
    - Accepts explicit 0.0 as a real, meaningful value (e.g. 0g trans fat).
    - Returns None only when the user leaves the field blank.
    """
    result = st.number_input(
        label,
        min_value=min_value,
        value=value,          # None → renders as empty in Streamlit ≥ 1.28
        step=step,
        key=key,
    )
    return result  # None if blank, float otherwise (including 0.0)


def render_food_form(
    *,
    mode: str,          # "add" | "edit"
    db,
    current=None,       # FoodOut for edit mode
    prefill: ParsedNutrition | None = None,
    form_key: str,
):
    pre = prefill.model_dump() if prefill else {}
    units = [u.unit_symbol for u in db.list_units()]
    brands = db.brands()

    def _cur(field: str):
        """Resolve field value: edit → current model, add → prefill dict, else None."""
        if current is not None:
            return getattr(current, field, None)
        return pre.get(field)

    with st.form(form_key):

        # ── Identity ──────────────────────────────────────────────────────
        with st.expander("Identity", expanded=True):
            name = st.text_input("Name *", value=_cur("name") or "")
            brand = select_or_other(
                label="Brand",
                options=brands,
                value=_cur("brand"),
                key=f"{form_key}_brand",
            )
            category = st.text_input("Category", value=_cur("category") or "")

        # ── Serving ───────────────────────────────────────────────────────
        with st.expander("Serving", expanded=True):
            c1, c2 = st.columns(2)
            serving_size = c1.number_input(
                "Serving size",
                min_value=0.0,
                value=_cur("serving_size"),
                step=1.0,
                key=f"{form_key}_serving_size",
            )
            serving_unit = select_or_other(
                label="Serving unit",
                options=units,
                value=_cur("serving_unit") or "g",
                key=f"{form_key}_serv_unit",
            )
            spc = st.number_input(
                "Servings per container",
                min_value=0.0,
                value=_cur("servings_per_container"),
                step=0.5,
                key=f"{form_key}_spc",
            )
            serving_size_text = st.text_input(
                "Serving size text (optional)",
                value=_cur("serving_size_text") or "",
            )
            serving_mass_g = st.number_input(
                "Serving mass (g) (optional)",
                min_value=0.0,
                value=_cur("serving_mass_g"),
                step=1.0,
                key=f"{form_key}_serving_mass_g",
            )

        # ── Calories & macros ─────────────────────────────────────────────
        with st.expander("Calories & macros", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            calories   = c1.number_input("Calories",     min_value=0.0, value=_cur("calories"),   step=1.0,  key=f"{form_key}_calories")
            protein_g  = c2.number_input("Protein (g)",  min_value=0.0, value=_cur("protein_g"),  step=0.5,  key=f"{form_key}_protein_g")
            carbs_g    = c3.number_input("Carbs (g)",    min_value=0.0, value=_cur("carbs_g"),    step=0.5,  key=f"{form_key}_carbs_g")
            fat_g      = c4.number_input("Fat (g)",      min_value=0.0, value=_cur("fat_g"),      step=0.5,  key=f"{form_key}_fat_g")

        # ── More nutrition ────────────────────────────────────────────────
        with st.expander("More nutrition", expanded=False):
            st.caption("Fats")
            c1, c2, c3 = st.columns(3)
            with c1:
                saturated_fat_g  = _opt_num("Saturated fat (g)",  _cur("saturated_fat_g"),  0.1, f"{form_key}_sat_fat")
            with c2:
                trans_fat_g      = _opt_num("Trans fat (g)",      _cur("trans_fat_g"),      0.1, f"{form_key}_trans_fat")
            with c3:
                cholesterol_mg   = _opt_num("Cholesterol (mg)",   _cur("cholesterol_mg"),   1.0, f"{form_key}_cholesterol")

            st.caption("Carbohydrates")
            c1, c2, c3 = st.columns(3)
            with c1:
                fiber_g      = _opt_num("Fiber (g)",       _cur("fiber_g"),      0.5, f"{form_key}_fiber_g")
            with c2:
                sugar_g      = _opt_num("Sugar (g)",       _cur("sugar_g"),      0.5, f"{form_key}_sugar_g")
            with c3:
                added_sugar_g= _opt_num("Added sugar (g)", _cur("added_sugar_g"),0.5, f"{form_key}_added_sugar_g")

            st.caption("Micronutrients")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                sodium_mg      = _opt_num("Sodium (mg)",     _cur("sodium_mg"),     1.0, f"{form_key}_sodium_mg")
            with c2:
                vitamin_d_mcg  = _opt_num("Vitamin D (mcg)", _cur("vitamin_d_mcg"), 0.1, f"{form_key}_vitamin_d_mcg")
            with c3:
                calcium_mg     = _opt_num("Calcium (mg)",    _cur("calcium_mg"),    1.0, f"{form_key}_calcium_mg")
            with c4:
                iron_mg        = _opt_num("Iron (mg)",       _cur("iron_mg"),       0.1, f"{form_key}_iron_mg")
            with c5:
                potassium_mg   = _opt_num("Potassium (mg)",  _cur("potassium_mg"),  1.0, f"{form_key}_potassium_mg")

        # ── Ingredients & dates ───────────────────────────────────────────
        with st.expander("Ingredients & dates", expanded=False):
            ingredients = st.text_area(
                "Ingredients",
                value=_cur("ingredients") or "",
                height=110,
            )
            best_by_val = _cur("best_by_date")
            best_by_date = st.date_input("Best-by date", value=best_by_val or None)

        submitted = st.form_submit_button("Save")
        if not submitted:
            return None

        if not (name or "").strip():
            st.error("Name is required.")
            return None

        common = dict(
            name=name.strip(),
            brand=brand,
            category=(category.strip() or None),
            serving_size=serving_size,
            serving_unit=serving_unit,
            servings_per_container=spc,
            serving_size_text=(serving_size_text.strip() or None),
            serving_mass_g=serving_mass_g,
            calories=calories,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
            saturated_fat_g=saturated_fat_g,
            trans_fat_g=trans_fat_g,
            cholesterol_mg=cholesterol_mg,
            fiber_g=fiber_g,
            sugar_g=sugar_g,
            added_sugar_g=added_sugar_g,
            sodium_mg=sodium_mg,
            vitamin_d_mcg=vitamin_d_mcg,
            calcium_mg=calcium_mg,
            iron_mg=iron_mg,
            potassium_mg=potassium_mg,
            ingredients=(ingredients.strip() or None),
            best_by_date=best_by_date if isinstance(best_by_date, date) else None,
        )

        if mode == "add":
            return FoodCreate(**common)
        return FoodUpdate(**common)