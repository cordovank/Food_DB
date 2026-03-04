from __future__ import annotations
import streamlit as st
from food_db.core.models import FoodVariantCreate
from .select_or_other import select_or_other

def render_add_variant_form(*, db, food_id: int, default_brand: str | None, default_unit: str | None, form_key: str):
    units = [u.unit_symbol for u in db.list_units()]

    with st.form(form_key):
        store = select_or_other(label="Store", options=db.stores(), value=None, key=f"{form_key}_store")
        vbrand = select_or_other(label="Variant brand", options=db.brands(), value=default_brand, key=f"{form_key}_brand")

        c1, c2 = st.columns(2)
        price = c1.number_input("Price (USD)", min_value=0.0, value=0.0, step=0.01)
        package_size = c2.number_input("Package size", min_value=0.0, value=0.0, step=1.0)

        package_unit = select_or_other(label="Package unit", options=units, value=default_unit, key=f"{form_key}_unit")
        notes = st.text_input("Notes", value="")

        submitted = st.form_submit_button("Add variant")
        if not submitted:
            return None

        def nz(x): return None if float(x) == 0.0 else float(x)

        return FoodVariantCreate(
            food_id=food_id,
            store_name=store,
            brand=vbrand,
            price=nz(price),
            package_size=nz(package_size),
            package_unit=package_unit,
            notes=(notes.strip() or None),
        )