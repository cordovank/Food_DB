# FoodDB UI – Technical Implementation Guide

This document explains the **design, structure, and modification guidelines** for the FoodDB user interface.

The UI is built using **Streamlit**, organized as a **modular page system** designed for clarity, maintainability, and easy extension.

---

# 1. UI Philosophy

The FoodDB UI follows these principles:

### 1. Minimalist Navigation

Navigation appears as **horizontal tabs at the top** of the application.

Pages:

```
Foods | Import | Inventory | DB/Admin | Units
```

This avoids clutter and keeps navigation visible.

---

### 2. Search-First Workflow

The main workflow centers around **search → inspect → edit**.

Example:

```
Search foods
   ↓
Select result
   ↓
View tabs
   ↓
Edit / Add variant / Manage inventory
```

This avoids forcing users through forms before they locate the correct food item.

---

### 3. Modular UI

The UI is intentionally **component-driven**.

Each page:

* orchestrates logic
* renders reusable components
* communicates with the backend service layer

This allows:

* isolated modifications
* future migration to React or other UI frameworks if desired

---

# 2. UI Architecture

## Directory Layout

```
src/food_db/ui/

app.py
state.py

components/
    select_or_other.py
    notifications.py
    detail_panel.py
    import_panel.py
    form_food.py
    form_variant.py
    form_inventory.py

pages/
    foods.py
    import_page.py
    inventory.py
    db_admin.py
    units.py
```

---

# 3. Application Entry Point

### `ui/app.py`

Responsible for:

* Streamlit configuration
* database initialization
* navigation routing

It **must remain lightweight**.

Example structure:

```python
st.set_page_config(page_title="FoodDB", layout="wide")

db = get_db()

tab_foods, tab_import, tab_inventory, tab_admin, tab_units = st.tabs(
    ["Foods", "Import", "Inventory", "DB/Admin", "Units"]
)

with tab_foods:
    foods_page(db=db)

with tab_import:
    import_page(db=db)

with tab_inventory:
    inventory_page(db=db)

with tab_admin:
    admin_page(db=db)

with tab_units:
    units_page(db=db)
```

Important rule:

**app.py should only route pages — not implement UI logic.**

---

# 4. Global UI State

### `ui/state.py`

Defines all Streamlit session state keys.

Example:

```
selected_food_id
selected_variant_id
search_query
filters
parsed_nutrition
ui_message
```

These are used across multiple pages.

Example:

```python
KEY_SELECTED_FOOD_ID = "selected_food_id"
KEY_SELECTED_VARIANT_ID = "selected_variant_id"
KEY_SEARCH_QUERY = "search_query"
```

This prevents:

* naming collisions
* inconsistent state usage
* hidden dependencies

---

# 5. Pages

Each page corresponds to one major user function.

---

# 5.1 Foods Page

File:

```
pages/foods.py
```

Purpose:

Main database interface.

### Layout

```
Search + filters
------------------

Results list      | Food details
                  |
                  | Tabs:
                  |  Overview
                  |  Nutrition
                  |  Ingredients & Dates
                  |  Variants
                  |  Inventory
```

---

### Tabs

#### Overview

Shows key nutrition metrics:

* calories
* protein
* carbs
* fat

---

#### Nutrition

Shows extended nutrition:

```
fiber
sugar
added sugar
sodium
saturated fat
trans fat
cholesterol
vitamin D
calcium
iron
potassium
```

---

#### Ingredients & Dates

```
ingredients
best_by_date
```

---

#### Variants

Displays:

```
store
brand
price
package size
notes
```

Users can:

* add variants
* inspect existing variants

---

#### Inventory

Inventory items linked to a variant.

```
quantity
unit
purchase date
```

---

# 5.2 Import Page

File:

```
pages/import_page.py
```

Workflow:

```
Acquire → Review → Save
```

### Acquisition methods

1. Paste nutrition label text
2. Upload nutrition label image

Image extraction uses:

```
infra/ocr/extractor.py
```

with either:

```
tesseract
ollama_vision
```

---

### Parsed Result

Displays structured fields:

```
name
brand
category
serving size
calories
protein
carbs
fat
```

User must **review and confirm** before saving.

No automatic database writes occur.

---

# 5.3 Inventory Page

File:

```
pages/inventory.py
```

Displays a global inventory table.

Fields:

```
food name
store
brand
quantity
unit
purchase date
```

Filters:

```
food name search
store
brand
```

Inventory items are created through:

```
Foods → Variants → Inventory
```

---

# 5.4 DB/Admin Page

File:

```
pages/db_admin.py
```

Purpose:

Administrative database inspection.

Displays:

```
foods count
variants count
inventory count
```

Tabs include:

```
Foods
Inventory
Units
```

Also supports exporting:

```
JSON
CSV
```

---

# 5.5 Units Page

File:

```
pages/units.py
```

Provides:

* unit conversion
* unit database view

Example conversion:

```
100 g → oz
```

Units stored in DB include:

```
g
oz
ml
cup
tbsp
tsp
```

---

# 6. UI Components

Reusable UI pieces live in:

```
ui/components
```

---

## `form_food.py`

Form for:

```
Add food
Edit food
```

Sections:

```
Identity
Serving
Calories & Macros
More Nutrition
Ingredients & Dates
```

Uses **expanders** for progressive disclosure.

---

## `form_variant.py`

Adds store-specific product variants.

Fields:

```
store
brand
price
package size
package unit
notes
```

---

## `form_inventory.py`

Manages inventory entries.

Fields:

```
quantity
unit
purchase date
```

---

## `select_or_other.py`

Reusable input pattern.

Allows either:

```
select existing value
OR
enter custom value
```

Example:

```
Brand:
[Quaker ▼]
or
[Other: ____ ]
```

Used for:

```
brands
stores
units
```

---

# 7. UI Data Flow

The UI **never talks directly to the database**.

All interactions go through:

```
core/services.py
```

Example:

```
UI → FoodDatabase service → Repository → DB
```

Example call:

```
db.upsert_food()
db.add_variant()
db.list_variants()
db.inventory_all()
```

This separation ensures:

* UI remains stateless
* business logic remains centralized

---

# 8. Widget Key Rules

Because Streamlit runs all tabs simultaneously, **every widget must have a unique key**.

Example:

```
text_input(..., key="foods_search")
selectbox(..., key="inventory_store_filter")
```

Without unique keys Streamlit will raise:

```
StreamlitDuplicateElementId
```

---

# 9. How To Add A New Page

1. Create file

```
ui/pages/new_page.py
```

2. Implement

```
def render_page(*, db):
```

3. Add to navigation

```
app.py
```

Example:

```
tab_new = st.tabs([...])
with tab_new:
    new_page(db=db)
```

---

# 10. Styling Guidelines

The UI intentionally avoids heavy styling.

Goals:

```
clean
fast
data-focused
```

Recommended patterns:

```
st.columns
st.tabs
st.metric
st.dataframe
st.expander
```

Avoid:

```
large nested expanders
excessive sidebars
over-custom CSS
```

---

# 11. Future UI Improvements

Potential enhancements:

### Food comparison

Compare nutrition across foods.

### Inventory analytics

Track:

```
purchase history
price trends
stock alerts
```

### Meal planner integration

Link foods to meal plans.

### Barcode scanning

Add barcode lookup using open databases.

---

# 12. Running the UI

Start the UI:

```
uv run streamlit run src/food_db/ui/app.py
```

Default access:

```
http://localhost:8501
```

---

# 13. Definition of Done (UI)

A correct UI implementation must allow:

✔ Search foods
✔ Add/edit foods
✔ Add variants
✔ Track inventory
✔ Import nutrition labels
✔ Export database
✔ Convert units

---

# 14. Key Design Principle

The UI must always remain:

```
simple to modify
simple to understand
simple to extend
```

All complexity should live in:

```
core/
infra/
```

not the UI layer.

---

If you'd like, I can also produce a **shorter "UI_AGENT_GUIDE.md" (~200 lines)** specifically optimized for **AI coding agents like Copilot, Goose, or GPT coding assistants**, which dramatically improves automated UI edits.
