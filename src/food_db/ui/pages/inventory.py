from __future__ import annotations
import streamlit as st

def render_page(*, db):
    st.subheader("Inventory")

    rows = db.inventory_all()
    if not rows:
        st.info("No inventory items yet.")
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    q     = c1.text_input("Search by food name", value="", key="inv_q")
    store = c2.selectbox("Store", ["(any)"] + db.stores(), index=0, key="inv_store")
    brand = c3.selectbox("Brand", ["(any)"] + db.brands(), index=0, key="inv_brand")

    filtered = [
        r for r in rows
        if (not q     or q.lower() in r.food_name.lower())
        and (store == "(any)" or r.store == store)
        and (brand == "(any)" or r.variant_brand == brand or r.canonical_brand == brand)
    ]

    st.dataframe(
        [r.model_dump() for r in filtered],
        width='stretch',
    )
    st.caption("To add inventory: Foods tab → select a food → Variants → select a variant → Inventory.")