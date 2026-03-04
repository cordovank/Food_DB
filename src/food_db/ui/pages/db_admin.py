from __future__ import annotations
import streamlit as st

def render_page(*, db, settings):
    st.subheader("DB / Admin")
    st.caption(f"SQLite path: {settings.db_path}")

    counts = db.admin_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("Foods", counts["foods"])
    c2.metric("Variants", counts["variants"])
    c3.metric("Inventory items", counts["inventory_items"])

    st.divider()
    t_foods, t_variants, t_inv, t_units = st.tabs(["Foods", "Variants", "Inventory items", "Units"])

    with t_foods:
        st.dataframe(db.repo.export_foods(), width=True)  # read-only

    with t_variants:
        # simple: show via join helper from inventory_all + distinct would be extra; keep minimal
        # If you want, add a repo method list_variants_all() later.
        st.info("Tip: variants are visible per-food in Foods → Variants.")
    
    with t_inv:
        st.dataframe(db.inventory_all(), width=True)

    with t_units:
        st.dataframe([u.model_dump() for u in db.list_units()], width=True)

    with st.expander("Advanced: Export", expanded=False):
        if st.button("Export JSON"):
            p = db.export_json(settings.project_root / "data" / "export.json")
            st.success(f"Wrote {p}")
        if st.button("Export CSV"):
            p = db.export_csv(settings.project_root / "data" / "export.csv")
            st.success(f"Wrote {p}")