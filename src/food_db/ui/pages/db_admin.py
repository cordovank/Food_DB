from __future__ import annotations
import streamlit as st


# ── Export helpers ────────────────────────────────────────────────────────────

_EXPORTS = [
    {
        "format":      "JSON",
        "button":      "Export JSON",
        "description": "Full food library as JSON. Good for backups and importing into other tools.",
        "filename":    "export.json",
        "method":      "export_json",
    },
    {
        "format":      "CSV",
        "button":      "Export CSV",
        "description": "Spreadsheet-friendly. Opens directly in Excel or Google Sheets.",
        "filename":    "export.csv",
        "method":      "export_csv",
    },
]


def _run_export(db, settings, method: str, filename: str) -> None:
    """Invoke the requested export method and surface result or error."""
    out_path = settings.project_root / "data" / filename
    try:
        p = getattr(db, method)(out_path)
        st.success(f"Saved to `{p}`")
    except RuntimeError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(f"Export failed: {exc}")


# ── Page ──────────────────────────────────────────────────────────────────────

def render_page(*, db, settings) -> None:
    st.subheader("Export")

    # ── Export actions ────────────────────────────────────────────────────
    for spec in _EXPORTS:
        col_btn, col_desc = st.columns([1, 4])
        if col_btn.button(spec["button"], type="primary", key=f"export_{spec['format']}"):
            _run_export(db, settings, spec["method"], spec["filename"])
        col_desc.caption(spec["description"])

    st.divider()

    # ── Library summary ───────────────────────────────────────────────────
    st.markdown("**Your library**")
    counts = db.admin_counts()
    c1, c2, c3 = st.columns(3)
    c1.metric("Foods",           counts["foods"])
    c2.metric("Variants",        counts["variants"])
    c3.metric("Inventory items", counts["inventory_items"])

    # ── Advanced / debug (collapsed) ──────────────────────────────────────
    with st.expander("Advanced", expanded=False):
        st.caption(f"SQLite path: `{settings.db_path}`")
        st.divider()

        t_foods, t_inv, t_units = st.tabs(["Foods", "Inventory", "Units"])

        with t_foods:
            st.dataframe(db.repo.export_foods(), width='stretch')

        with t_inv:
            rows = db.inventory_all()
            if rows:
                st.dataframe(
                    [r.model_dump() for r in rows],
                    width='stretch',
                )
            else:
                st.info("No inventory items yet.")

        with t_units:
            st.dataframe(
                [u.model_dump() for u in db.list_units()],
                width='stretch',
            )