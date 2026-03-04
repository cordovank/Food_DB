from __future__ import annotations
import streamlit as st

KEY_SELECTED_FOOD_ID = "selected_food_id"
KEY_SELECTED_VARIANT_ID = "selected_variant_id"
KEY_SEARCH_QUERY = "search_query"
KEY_FILTERS = "filters"
KEY_PARSED = "parsed_nutrition"
KEY_UI_MESSAGE = "ui_message"

def init_state():
    st.session_state.setdefault(KEY_SELECTED_FOOD_ID, None)
    st.session_state.setdefault(KEY_SELECTED_VARIANT_ID, None)
    st.session_state.setdefault(KEY_SEARCH_QUERY, "")
    st.session_state.setdefault(KEY_FILTERS, {"category": None, "brand": None, "store": None})
    st.session_state.setdefault(KEY_PARSED, None)
    st.session_state.setdefault(KEY_UI_MESSAGE, None)

def make_form_key(action: str, entity_id: int | str) -> str:
    """Generate a stable, unique Streamlit widget key for a form.

    Examples:
        make_form_key("edit", 42)           → "form_edit_42"
        make_form_key("add_variant", 7)     → "form_add_variant_7"
        make_form_key("upd_inv", 3)         → "form_upd_inv_3"
    """
    return f"form_{action}_{entity_id}"