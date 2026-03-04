from __future__ import annotations
import streamlit as st

def render_page(*, db):
    st.subheader("Units")

    units = [u.unit_symbol for u in db.list_units()]
    c1, c2 = st.columns(2)
    value = c1.number_input("Value", min_value=0.0, value=100.0, step=1.0, key="units_value")
    from_u = c2.selectbox("From", units, index=0 if "g" in units else 0, key="units_fromu")
    to_u = st.selectbox("To", units, index=units.index("oz") if "oz" in units else 0, key="units_tou")

    if st.button("Convert", type="primary"):
        st.success(f"{value} {from_u} = {db.convert(value, from_u, to_u):.4f} {to_u}")

    st.divider()
    st.dataframe([u.model_dump() for u in db.list_units()], width=True)