from __future__ import annotations

from pathlib import Path

import streamlit as st

from food_db.config import settings
from food_db.core.models import FoodCreate, FoodUpdate, FoodVariantCreate
from food_db.core.services import make_food_db
from food_db.core.usecases import parse_text_to_nutrition, ocr_image_to_nutrition


st.set_page_config(page_title="FoodDB", page_icon="🍎", layout="wide")


@st.cache_resource(show_spinner=False)
def get_db():
    db = make_food_db(settings.db_path)
    db.init()
    return db


db = get_db()

def select_or_other(
    *,
    label: str,
    options: list[str],
    value: str | None,
    key: str,
    none_label: str = "(none)",
    other_label: str = "(other...)",
) -> str | None:
    """
    Dropdown populated from DB with optional free-text 'other'.
    Returns normalized string or None.
    """
    # de-dupe while preserving sorted feel
    opts = [o for o in options if o]
    opts = sorted(set(opts), key=lambda x: x.lower())

    base = [none_label] + opts + [other_label]

    # pick index
    if value and value in opts:
        idx = base.index(value)
    elif value:
        idx = base.index(other_label)
    else:
        idx = 0

    chosen = st.selectbox(label, base, index=idx, key=f"{key}__sel")

    if chosen == none_label:
        return None

    if chosen == other_label:
        typed = st.text_input(f"{label} (other)", value=value or "", key=f"{key}__other")
        typed = (typed or "").strip()
        return typed or None

    return chosen


st.title("🍎 FoodDB")
st.caption(f"SQLite: {settings.db_path}")

# -------------------------
# Sidebar
# -------------------------

with st.sidebar:
    st.header("Tools")

    st.subheader("Unit conversion")
    units = [u.unit_symbol for u in db.list_units()]
    col1, col2 = st.columns(2)
    value = col1.number_input("Value", min_value=0.0, value=100.0, step=1.0)
    from_u = col2.selectbox("From", units, index=0 if "g" in units else 0)
    to_u = st.selectbox("To", units, index=units.index("oz") if "oz" in units else 0)
    if st.button("Convert"):
        st.success(f"{value} {from_u} = {db.convert(value, from_u, to_u):.4f} {to_u}")

    st.divider()
    st.subheader("Import")
    raw_text = st.text_area("Paste label text (optional)", height=140)
    if st.button("Parse text"):
        if raw_text.strip():
            st.session_state["parsed"] = parse_text_to_nutrition(raw_text)
        else:
            st.warning("Paste some text first")

    img = st.file_uploader("OCR image (optional)", type=["png", "jpg", "jpeg", "webp", "heic", "heif"])
    if st.button("Run OCR"):
        if img is None:
            st.warning("Upload an image")
        else:
            try:
                # Convert UploadedFile -> temp PNG (handles heic/heif)
                from food_db.infra.ocr.extractor import FoodOCRExtractor
                tmp_png = FoodOCRExtractor.save_uploaded_image_to_tempfile(img)

                st.session_state["parsed"] = ocr_image_to_nutrition(tmp_png)
            except Exception as e:
                st.error(str(e))

# -------------------------
# Search + results
# -------------------------

st.subheader("Search")
q = st.text_input("Search by name/category", value=st.session_state.get("q", ""))

# Filters - Smart Search
with st.sidebar:
    st.subheader("Smart Search")
    use_smart = st.toggle("Use smart (fuzzy) search", value=True)
    min_score = st.slider("Min match score", 0.0, 1.0, 0.35, 0.01)
    limit = st.number_input("Max results", min_value=5, max_value=200, value=50, step=5)

    cats = ["(any)"] + db.categories()
    brands = ["(any)"] + db.brands()
    stores = ["(any)"] + db.stores()

    f_category = st.selectbox("Category filter", cats, index=0)
    f_brand = st.selectbox("Brand filter", brands, index=0)
    f_store = st.selectbox("Store filter", stores, index=0)

category = None if f_category == "(any)" else f_category
brand = None if f_brand == "(any)" else f_brand
store = None if f_store == "(any)" else f_store

if q:
    if use_smart:
        rows = db.search_foods_smart(
            q,
            category=category,
            brand=brand,
            store=store,
            limit=int(limit),
            min_score=float(min_score),
        )
    else:
        rows = db.search_foods(q, category=category)
else:
    rows = []

# Results
colA, colB = st.columns([2, 3])

with colA:
    st.markdown("#### Results")
    if not rows and q:
        st.info("No matches")

    # Build selection list
    options = {f"{r.id} · {r.name}": r.id for r in rows}
    sel_label = st.selectbox("Select", ["-"] + list(options.keys()))
    selected_id = options.get(sel_label)

with colB:
    st.markdown("#### Details")

    parsed = st.session_state.get("parsed")
    if parsed and parsed.warnings:
        st.warning("\n".join(parsed.warnings))

    # Prefill with parsed content if present
    pre = parsed.model_dump() if parsed else {}

    if selected_id:
        current = db.get_food(selected_id)
        if not current:
            st.error("Selected item not found")
        else:
            st.write({
                "id": current.id,
                "name": current.name,
                "brand": current.brand,
                "category": current.category,
                "serving": f"{current.serving_size} {current.serving_unit}",
                "kcal": current.calories,
                "protein_g": current.protein_g,
                "carbs_g": current.carbs_g,
                "fat_g": current.fat_g,
                "fiber_g": current.fiber_g,
                "sugar_g": current.sugar_g,
                "sodium_mg": current.sodium_mg,
            })

            with st.expander("Edit", expanded=False):
                with st.form("edit_food"):
                    name = st.text_input("Name", value=current.name)
                    brand = select_or_other(
                        label="Brand",
                        options=db.brands(),
                        value=current.brand,
                        key=f"edit_brand_{current.id}",
                    )
                    category = st.text_input("Category", value=current.category or "")

                    c1, c2 = st.columns(2)
                    serving_size = c1.number_input("Serving size", value=float(current.serving_size or 0.0), min_value=0.0, step=1.0)
                    serving_unit = select_or_other(
                        label="Serving unit",
                        options=[u.unit_symbol for u in db.list_units()],
                        value=current.serving_unit,
                        key=f"edit_serv_unit_{current.id}",
                    )

                    c1, c2, c3, c4 = st.columns(4)
                    calories = c1.number_input("Calories", value=float(current.calories or 0.0), min_value=0.0)
                    protein_g = c2.number_input("Protein (g)", value=float(current.protein_g or 0.0), min_value=0.0)
                    carbs_g = c3.number_input("Carbs (g)", value=float(current.carbs_g or 0.0), min_value=0.0)
                    fat_g = c4.number_input("Fat (g)", value=float(current.fat_g or 0.0), min_value=0.0)

                    c1, c2, c3 = st.columns(3)
                    fiber_g = c1.number_input("Fiber (g)", value=float(current.fiber_g or 0.0), min_value=0.0)
                    sugar_g = c2.number_input("Sugar (g)", value=float(current.sugar_g or 0.0), min_value=0.0)
                    sodium_mg = c3.number_input("Sodium (mg)", value=float(current.sodium_mg or 0.0), min_value=0.0)

                    submitted = st.form_submit_button("Save")
                    if submitted:
                        patch = FoodUpdate(
                            name=name,
                            brand=brand,
                            category=category.strip() or None,
                            serving_size=serving_size or None,
                            serving_unit=serving_unit,
                            calories=calories or None,
                            protein_g=protein_g or None,
                            carbs_g=carbs_g or None,
                            fat_g=fat_g or None,
                            fiber_g=fiber_g or None,
                            sugar_g=sugar_g or None,
                            sodium_mg=sodium_mg or None,
                        )
                        db.update_food(current.id, patch)
                        st.success("Saved")
                        st.rerun()

            with st.expander("Variants (store/brand/pricing)", expanded=False):
                variants = db.list_variants(current.id)
                if variants:
                    st.dataframe([v.model_dump() for v in variants], use_container_width=True)
                else:
                    st.info("No variants")

                with st.form("add_variant"):
                    st.caption("Add variant")
                    store = select_or_other(
                        label="Store",
                        options=db.stores(),
                        value=None,
                        key=f"variant_store_{current.id}",
                    )
                    vbrand = select_or_other(
                        label="Variant brand",
                        options=db.brands(),
                        value=current.brand,
                        key=f"variant_brand_{current.id}",
                    )
                    c1, c2 = st.columns(2)
                    price = c1.number_input("Price (USD)", min_value=0.0, value=0.0, step=0.01)
                    pkg_size = c2.number_input("Package size", min_value=0.0, value=0.0, step=1.0)
                    pkg_unit = select_or_other(
                        label="Package unit",
                        options=[u.unit_symbol for u in db.list_units()],
                        value=current.serving_unit,
                        key=f"variant_pkg_unit_{current.id}",
                    )
                    notes = st.text_input("Notes", value="")
                    if st.form_submit_button("Add variant"):
                        db.add_variant(
                            FoodVariantCreate(
                                food_id=current.id,
                                store_name=store,
                                brand=vbrand,
                                price=price or None,
                                package_size=pkg_size or None,
                                package_unit=pkg_unit,
                                notes=notes.strip() or None,
                            )
                        )
                        st.success("Variant added")
                        st.rerun()

            if st.button("Delete food", type="secondary"):
                db.delete_food(current.id)
                st.success("Deleted")
                st.rerun()

    else:
        st.info("Select a food to view/edit, or add a new one below.")

# -------------------------
# Add new
# -------------------------

st.divider()
st.subheader("Add new")

parsed = st.session_state.get("parsed")
pre = parsed.model_dump() if parsed else {}

with st.form("add_food"):
    name = st.text_input("Name", value=pre.get("name") or "")
    brand = select_or_other(
        label="Brand",
        options=db.brands(),
        value=pre.get("brand"),
        key="add_brand",
    )
    category = st.text_input("Category", value=pre.get("category") or "")

    c1, c2 = st.columns(2)
    serving_size = c1.number_input("Serving size", min_value=0.0, value=float(pre.get("serving_size") or 0.0), step=1.0)
    serving_unit = select_or_other(
        label="Serving unit",
        options=[u.unit_symbol for u in db.list_units()],
        value=pre.get("serving_unit") or "g",
        key="add_serv_unit",
    )

    c1, c2, c3, c4 = st.columns(4)
    calories = c1.number_input("Calories", min_value=0.0, value=float(pre.get("calories") or 0.0))
    protein_g = c2.number_input("Protein (g)", min_value=0.0, value=float(pre.get("protein_g") or 0.0))
    carbs_g = c3.number_input("Carbs (g)", min_value=0.0, value=float(pre.get("carbs_g") or 0.0))
    fat_g = c4.number_input("Fat (g)", min_value=0.0, value=float(pre.get("fat_g") or 0.0))

    c1, c2, c3 = st.columns(3)
    fiber_g = c1.number_input("Fiber (g)", min_value=0.0, value=float(pre.get("fiber_g") or 0.0))
    sugar_g = c2.number_input("Sugar (g)", min_value=0.0, value=float(pre.get("sugar_g") or 0.0))
    sodium_mg = c3.number_input("Sodium (mg)", min_value=0.0, value=float(pre.get("sodium_mg") or 0.0))

    submitted = st.form_submit_button("Save (upsert by name)")
    if submitted:
        if not name.strip():
            st.error("Name is required")
        else:
            db.upsert_food(
                FoodCreate(
                    name=name.strip(),
                    brand=brand,
                    category=category.strip() or None,
                    serving_size=serving_size or None,
                    serving_unit=serving_unit,
                    calories=calories or None,
                    protein_g=protein_g or None,
                    carbs_g=carbs_g or None,
                    fat_g=fat_g or None,
                    fiber_g=fiber_g or None,
                    sugar_g=sugar_g or None,
                    sodium_mg=sodium_mg or None,
                )
            )
            st.success("Saved")
            # clear parsed
            st.session_state.pop("parsed", None)
            st.rerun()
