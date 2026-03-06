# src/food_db/ui/pages/foods.py
from __future__ import annotations
import streamlit as st

from food_db.config import settings as _settings
from food_db.core.models import FoodCreate
from food_db.ui.state import (
    KEY_SELECTED_FOOD_ID, KEY_SELECTED_VARIANT_ID, KEY_PARSED,
    KEY_SEARCH_QUERY, KEY_FILTERS, make_form_key
)
from food_db.ui.components.form_food import render_food_form
from food_db.ui.components.form_variant import render_add_variant_form
from food_db.ui.components.form_inventory import (
    render_add_inventory_form,
    render_update_inventory_form,
)


@st.cache_data(ttl=30, show_spinner=False)
def _filter_options(_db):
    """Cache category/brand/store lists for 30 s.

    Leading underscore on _db tells Streamlit not to hash the db object.
    Cleared explicitly after any mutation via st.cache_data.clear().
    """
    return _db.categories(), _db.brands(), _db.stores()


def _bust_cache():
    """Call after any DB write so dropdowns reflect the change on next rerun."""
    _filter_options.clear()


def render_page(*, db):
    st.subheader("Foods")

    categories, brands, stores = _filter_options(db)

    # ── Search + filters ─────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    q = c1.text_input(
        "Search foods by name, brand, category…",
        value=st.session_state.get(KEY_SEARCH_QUERY, ""),
        key="foods_q",
    )
    fcat   = c2.selectbox("Category", ["(any)"] + categories, index=0, key="foods_cat")
    fbrand = c3.selectbox("Brand",    ["(any)"] + brands,     index=0, key="foods_brand")
    fstore = c4.selectbox("Store",    ["(any)"] + stores,     index=0, key="foods_store")

    st.session_state[KEY_SEARCH_QUERY] = q
    st.session_state[KEY_FILTERS] = {
        "category": None if fcat == "(any)" else fcat,
        "brand":    None if fbrand == "(any)" else fbrand,
        "store":    None if fstore == "(any)" else fstore,
    }

    # ── Advanced search options (moved out of sidebar — Fix 5) ───────────
    with st.expander("Search options", expanded=False):
        sc1, sc2, sc3 = st.columns(3)
        use_smart = sc1.toggle("Smart (fuzzy) search", value=True, key="foods_smart")

        min_score = sc2.slider(
            "Min match score", min_value=0.0, max_value=1.0,
            value=_settings.search_min_score,
            step=0.05,
            key="foods_min_score",
            disabled=not use_smart,
        )
        limit = sc3.number_input(
            "Max results", min_value=5, max_value=200,
            value=_settings.search_result_limit,
            step=5,
            key="foods_limit",
        )

    # ── Run search ────────────────────────────────────────────────────────
    filt = st.session_state[KEY_FILTERS]
    browsing = not q.strip()

    if browsing:
        rows = db.list_foods_paged(limit=int(limit))
    elif use_smart:
        rows = db.search_foods_smart(
            q,
            category=filt["category"],
            brand=filt["brand"],
            store=filt["store"],
            limit=int(limit),
            min_score=float(min_score),
        )
    else:
        rows = db.search_foods(q, category=filt["category"])

    # ── Results list ──────────────────────────────────────────────────────
    left, right = st.columns([2, 3], gap="large")

    with left:
        st.markdown("#### Results")
        if browsing:
            st.caption(f"Showing first {len(rows)} foods — type to search")
        elif not rows:
            st.info("No matches")

        options = {f"{r.id} · {r.name}": r.id for r in rows}
        sel_label = st.selectbox("Select", ["-"] + list(options.keys()), key="foods_sel")
        sel_id = options.get(sel_label)
        st.session_state[KEY_SELECTED_FOOD_ID] = sel_id

    # ── Detail panel ──────────────────────────────────────────────────────
    with right:
        st.markdown("#### Details")
        selected_id = st.session_state.get(KEY_SELECTED_FOOD_ID)

        if not selected_id:
            st.info("Select a food to view/edit, or use Import to stage OCR/parse.")
            return

        current = db.get_food(selected_id)
        if not current:
            st.error("Selected item not found.")
            return

        st.markdown(f"### {current.name}")
        st.caption(f"{current.brand or '—'} · {current.category or '—'}")

        serving_bits = []
        if current.serving_size and current.serving_unit:
            serving_bits.append(f"{current.serving_size:g}{current.serving_unit}")
        if current.servings_per_container:
            serving_bits.append(f"{current.servings_per_container:g} servings/container")
        if current.serving_mass_g:
            serving_bits.append(f"{current.serving_mass_g:g}g mass")
        if current.serving_size_text:
            serving_bits.append(f"{current.serving_size_text}")
        
        st.caption(" · ".join(serving_bits) or "Serving: —")

        tab_overview, tab_nutrition, tab_ing, tab_variants, tab_inv = st.tabs(
            ["Overview", "Nutrition", "Ingredients & Dates", "Variants", "Inventory"]
        )

        # ── Overview tab (Fix 6: Edit + Delete moved here) ─────────────
        with tab_overview:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Calories",    f"{current.calories:g}"   if current.calories   is not None else "—")
            c2.metric("Protein (g)", f"{current.protein_g:g}"  if current.protein_g  is not None else "—")
            c3.metric("Carbs (g)",   f"{current.carbs_g:g}"    if current.carbs_g    is not None else "—")
            c4.metric("Fat (g)",     f"{current.fat_g:g}"      if current.fat_g      is not None else "—")

            st.divider()

            # Edit
            edit_key = f"foods_show_edit_{current.id}"

            if st.button("Edit food", type="primary", key=f"btn_edit_{current.id}"):
                st.session_state[edit_key] = True

            if st.session_state.get(edit_key):
                patch = render_food_form(
                    mode="edit",
                    db=db,
                    current=current,
                    prefill=None,
                    form_key=make_form_key("edit", current.id),
                )
                if patch:
                    db.update_food(current.id, patch)
                    st.session_state[edit_key] = False
                    _bust_cache()
                    st.success("Saved")
                    st.rerun()

            # Danger zone
            with st.expander("Danger zone", expanded=False):
                confirm = st.text_input(
                    "Type DELETE to confirm", value="",
                    key=f"del_confirm_{current.id}",
                )
                if st.button(
                    "Delete food", type="secondary",
                    key=f"btn_delete_{current.id}",
                    disabled=(confirm.strip().upper() != "DELETE"),
                ):
                    db.delete_food(current.id)
                    st.session_state[KEY_SELECTED_FOOD_ID] = None
                    _bust_cache()
                    st.success("Deleted")
                    st.rerun()

        # ── Nutrition tab ─────────────────────────────────────────────
        with tab_nutrition:
            nutrient_rows = [
                ("Fiber",         current.fiber_g,          "g"),
                ("Sugar",         current.sugar_g,          "g"),
                ("Added sugar",   current.added_sugar_g,    "g"),
                ("Sodium",        current.sodium_mg,        "mg"),
                ("Saturated fat", current.saturated_fat_g,  "g"),
                ("Trans fat",     current.trans_fat_g,      "g"),
                ("Cholesterol",   current.cholesterol_mg,   "mg"),
                ("Vitamin D",     current.vitamin_d_mcg,    "mcg"),
                ("Calcium",       current.calcium_mg,       "mg"),
                ("Iron",          current.iron_mg,          "mg"),
                ("Potassium",     current.potassium_mg,     "mg"),
            ]
            for label, val, unit in nutrient_rows:
                c1, c2 = st.columns([3, 1])
                c1.write(label)
                c2.write(f"{val:g} {unit}" if val is not None else "—")

        # ── Ingredients & dates tab ───────────────────────────────────
        with tab_ing:
            st.write("**Ingredients**")
            st.write(current.ingredients or "—")
            st.write("**Best-by date**")
            st.write(str(current.best_by_date) if current.best_by_date else "—")

        # ── Variants tab ──────────────────────────────────────────────
        with tab_variants:
            variants = db.list_variants(current.id)
            if variants:
                st.dataframe([v.model_dump() for v in variants], width='stretch')
            else:
                st.info("No variants yet.")

            v = render_add_variant_form(
                db=db,
                food_id=current.id,
                default_brand=current.brand,
                default_unit=current.serving_unit,
                form_key=make_form_key("add_variant", current.id),  # Fix 7
            )
            if v:
                db.add_variant(v)
                _bust_cache()
                st.success("Variant added")
                st.rerun()

            if variants:
                vmap = {
                    f"{vv.id} · {vv.store_name or '—'} · {vv.brand or '—'}": vv.id
                    for vv in variants
                }
                vsel = st.selectbox(
                    "Select variant for Inventory tab",
                    list(vmap.keys()),
                    index=0,
                    key=f"vsel_{current.id}",
                )
                st.session_state[KEY_SELECTED_VARIANT_ID] = vmap[vsel]

        # ── Inventory tab ─────────────────────────────────────────────
        with tab_inv:
            variant_id = st.session_state.get(KEY_SELECTED_VARIANT_ID)
            if not variant_id:
                st.info("Select a variant in the Variants tab first.")
            else:
                items = db.list_inventory_for_variant(variant_id)
                if items:
                    st.dataframe([i.model_dump() for i in items], width='stretch')
                else:
                    st.info("No inventory items for this variant.")

                new_item = render_add_inventory_form(
                    db=db,
                    variant_id=variant_id,
                    form_key=make_form_key("add_inv", variant_id),  # Fix 7
                )
                if new_item:
                    db.add_inventory_item(new_item)
                    st.success("Inventory item added")
                    st.rerun()

                units_list = [u.unit_symbol for u in db.list_units()]
                for it in items:
                    with st.expander(f"Inventory #{it.id}", expanded=False):
                        upd = render_update_inventory_form(
                            item=it,
                            units=units_list,
                            form_key=make_form_key("upd_inv", it.id),  # Fix 7
                        )
                        if upd:
                            item_id, patch = upd
                            db.update_inventory_item(item_id, patch)
                            st.success("Updated")
                            st.rerun()
                        if st.button("Remove item", key=f"rm_inv_{it.id}", type="secondary"):
                            db.delete_inventory_item(it.id)
                            st.success("Removed")
                            st.rerun()