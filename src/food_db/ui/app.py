from __future__ import annotations
import streamlit as st

from food_db.config import settings
from food_db.core.services import make_food_db
from food_db.ui.state import init_state
from food_db.ui.pages.foods import render_page as foods_page
from food_db.ui.pages.import_page import render_page as import_page
from food_db.ui.pages.inventory import render_page as inventory_page
from food_db.ui.pages.db_admin import render_page as admin_page
from food_db.ui.pages.units import render_page as units_page

st.set_page_config(page_title="FoodDB", page_icon="🍎", layout="wide")

@st.cache_resource(show_spinner=False)
def get_db():
    db = make_food_db(settings.db_path)
    db.init()
    return db

db = get_db()
init_state()

st.title("🍎 FoodDB")
st.caption(f"SQLite: {settings.db_path}")

# --- Navigation (top horizontal) ---
tab_foods, tab_import, tab_inventory, tab_admin, tab_units = st.tabs(
    ["Foods", "Import", "Inventory", "DB/Admin", "Units"]
)

with tab_foods:
    foods_page(db=db)

with tab_import:
    import_page(db=db, settings=settings)

with tab_inventory:
    inventory_page(db=db)

with tab_admin:
    admin_page(db=db, settings=settings)

with tab_units:
    units_page(db=db)
    
# with st.sidebar:
#     st.header("Navigation")
#     page = st.radio(
#         "Go to",
#         ["Foods", "Import", "Inventory", "DB / Admin", "Units"],
#         index=0,
#         label_visibility="collapsed",
#     )
#     st.divider()
#     st.caption("Advanced controls are inside pages (keeps sidebar calm).")

# if page == "Foods":
#     foods_page(db=db)
# elif page == "Import":
#     import_page(db=db, settings=settings)
# elif page == "Inventory":
#     inventory_page(db=db)
# elif page == "DB / Admin":
#     admin_page(db=db, settings=settings)
# elif page == "Units":
#     units_page(db=db)