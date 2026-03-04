from __future__ import annotations
from datetime import datetime, date
import streamlit as st
from food_db.core.models import InventoryItemCreate, InventoryItemUpdate

def render_add_inventory_form(*, db, variant_id: int, form_key: str):
    units = [u.unit_symbol for u in db.list_units()]
    with st.form(form_key):
        c1, c2 = st.columns(2)
        qty = c1.number_input("Quantity", min_value=0.0, value=0.0, step=1.0)
        unit = c2.selectbox("Unit", units, index=0 if "g" in units else 0)
        pd = st.date_input("Purchase date", value=date.today())

        submitted = st.form_submit_button("Add inventory item")
        if not submitted:
            return None

        return InventoryItemCreate(
            variant_id=variant_id,
            quantity=None if float(qty) == 0.0 else float(qty),
            unit=unit,
            purchase_date=datetime(pd.year, pd.month, pd.day),
        )

def render_update_inventory_form(*, item, units: list[str], form_key: str):
    with st.form(form_key):
        c1, c2 = st.columns(2)
        qty = c1.number_input("Quantity", min_value=0.0, value=float(item.quantity or 0.0), step=1.0)
        unit = c2.selectbox("Unit", units, index=units.index(item.unit) if item.unit in units else 0)
        pd = st.date_input("Purchase date", value=item.purchase_date.date())

        submitted = st.form_submit_button("Update")
        if not submitted:
            return None

        return item.id, InventoryItemUpdate(
            quantity=None if float(qty) == 0.0 else float(qty),
            unit=unit,
            purchase_date=datetime(pd.year, pd.month, pd.day),
        )