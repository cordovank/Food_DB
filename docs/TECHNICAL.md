# FoodDB — Technical Reference

> Extended documentation for contributors and maintainers.
> The main README covers quickstart and usage (briefly mentioned here). This document covers
> architecture, design decisions, module internals, and extension points.

---

## Usage: What it does?

- **Store food items** with full nutrition facts (macros, micros, ingredients, best-by date)
- **Track store variants** — same food from Costco vs. Aldi vs. Publix with price and package size
- **Track inventory** — what you currently have on hand, per variant
- **Import from a label** — paste text or upload a photo (JPG/PNG/WEBP/HEIC/HEIF); regex parser extracts structured fields automatically
- **OCR two ways** — Tesseract (local, offline) or a local Ollama vision model (LLaVA/Qwen-VL style)
- **Fuzzy search** — token overlap + SequenceMatcher scoring; filter by category, brand, or store
- **Export** — JSON or CSV
- **Unit conversions** — stored conversion table (g ↔ oz, etc.) with a UI calculator

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Layer Breakdown](#layer-breakdown)
  - [Config (`config.py`)](#config-configpy)
  - [Core: Models (`core/models.py`)](#core-models-coremodels-py)
  - [Core: Repository (`core/repository.py`)](#core-repository-corerepositorypy)
  - [Core: Services (`core/services.py`)](#core-services-coreservicespy)
  - [Core: Usecases (`core/usecases.py`)](#core-usecases-coreusecasespy)
  - [Infra: DB (`infra/db/sql_db.py`)](#infra-db-infradbsql_dbpy)
  - [Infra: NLP (`infra/nlp/processor.py`)](#infra-nlp-infranl-pprocessorpy)
  - [Infra: OCR (`infra/ocr/`)](#infra-ocr-infraocr)
  - [Utils](#utils)
  - [CLI (`cli/main.py`)](#cli-climainpy)
  - [UI (`ui/`)](#ui-ui)
- [Data Model](#data-model)
- [OCR Backends](#ocr-backends)
- [Search Implementation](#search-implementation)
- [Design Decisions](#design-decisions)
- [Extension Points](#extension-points)
- [Known Limitations](#known-limitations)

---

## Architecture Overview

FoodDB follows a layered architecture with explicit separation between data access, business logic, and presentation. The CLI and UI are both thin clients over the same service layer; they share one SQLite file via the singleton `Settings.db_path`.

```
CLI (Typer)         Streamlit UI
      \                  /
       \                /
        ── Services ──
              |
         Repository
              |
        SQLAlchemy ORM
              |
          SQLite file
```

No HTTP server is involved. All communication is direct Python calls. The UI and CLI can run simultaneously — both read/write the same SQLite file; CLI writes are visible in the UI after a page refresh or rerun.

---

## Layer Breakdown

### Config (`config.py`)

`Settings` is a `pydantic_settings.BaseSettings` subclass. All fields load from environment variables or a `.env` file — do not use `os.getenv()` inside the class body, as that bypasses `.env` file support.

**Key behaviors:**
- `db_path` defaults to `<project_root>/data/food_database.db` and is resolved in `model_post_init` after `project_root` is known.
- `ocr_backend` switches between `"tesseract"` and `"ollama_vision"` at runtime; no code change required.
- `search_min_score`, `search_candidate_limit`, and `search_result_limit` tune fuzzy search behavior without code changes.

```python
# Override via environment or .env
DB_PATH=/custom/path/food.db
OCR_BACKEND=ollama_vision
OCR_TESSERACT_CMD=/opt/homebrew/bin/tesseract
```

---

### Core: Models (`core/models.py`)

Two parallel model systems in one file:

**SQLAlchemy ORM classes** (map to DB tables):
- `Food` — canonical product record; unique on `name`
- `FoodVariant` — store/brand-specific variant, FK to `Food`
- `InventoryItem` — quantity on hand, FK to `FoodVariant`
- `Unit` — conversion factors to grams
- `FoodUnit` — per-food unit override (e.g., 1 tbsp peanut butter = 16g)

**Pydantic schemas** (API / service layer):
- `FoodCreate` / `FoodUpdate` / `FoodOut` — CRUD contracts; `FoodUpdate` uses all-Optional fields for partial updates
- `FoodVariantCreate` / `FoodVariantOut`
- `InventoryItemCreate` / `InventoryItemOut` / `InventoryItemUpdate`
- `UnitOut` / `InventoryRow`
- `ParsedNutrition` — output of the text parser and OCR pipeline; includes a `warnings: list[str]` field for uncertain extractions

The ORM and Pydantic layers are intentionally separate: the repository reads ORM objects and converts them to Pydantic outputs before returning to callers. No ORM objects leak above the repository boundary.

---

### Core: Repository (`core/repository.py`)

`FoodRepository` wraps a SQLAlchemy `Session` and exposes typed methods. All DB access lives here — no raw SQL elsewhere.

Key methods:

| Method | Notes |
|---|---|
| `add_food(data: FoodCreate) → FoodOut` | Insert; raises on duplicate name |
| `upsert_food(data: FoodCreate) → FoodOut` | Insert or update by name |
| `get_food(food_id: int) → FoodOut \| None` | |
| `get_food_by_name(name: str) → FoodOut \| None` | Used for duplicate detection in UI |
| `update_food(food_id, patch: FoodUpdate) → FoodOut \| None` | Partial update; only sets non-None fields |
| `delete_food(food_id) → bool` | Cascades to variants and inventory |
| `search_foods_smart(query, ...)` | See [Search Implementation](#search-implementation) |
| `add_variant / list_variants / delete_variant` | Variant CRUD |
| `add_inventory_item / update_inventory_item / delete_inventory_item` | Inventory CRUD |
| `inventory_all() → list[InventoryRow]` | Joined view across foods + variants + inventory |
| `add_from_parsed(parsed: ParsedNutrition) → FoodOut` | Converts parsed output to FoodCreate and upserts |
| `export_json / export_csv` | Writes to file; returns Path |
| `convert(value, from_unit, to_unit) → float` | Unit conversion via DB table |
| `brands() / stores()` | Distinct value lists for UI dropdowns |

---

### Core: Services (`core/services.py`)

`make_food_db(db_path: Path) → FoodRepository` is the single factory function. It creates the SQLAlchemy engine, initializes `SessionLocal`, and returns a `FoodRepository`. Both the CLI and UI call this factory; both get a repository pointed at the same file.

`FoodRepository.init()` creates all tables (idempotent via `checkfirst=True`) and seeds base units on first run.

---

### Core: Usecases (`core/usecases.py`)

Thin orchestration layer that bridges infra (NLP/OCR) with the core:

- `parse_text_to_nutrition(text: str) → ParsedNutrition` — delegates to `FoodTextProcessor`
- `ocr_image_to_nutrition(image_path: Path) → ParsedNutrition` — selects OCR backend from `settings.ocr_backend`, extracts text, then delegates to `parse_text_to_nutrition`

This layer ensures that the UI and CLI don't import from `infra` directly, keeping the dependency direction clean.

---

### Infra: DB (`infra/db/sql_db.py`)

SQLAlchemy engine + `SessionLocal` factory. Uses a context manager pattern for session lifecycle. The engine uses `check_same_thread=False` for Streamlit compatibility (Streamlit runs callbacks on different threads).

---

### Infra: NLP (`infra/nlp/processor.py`)

`FoodTextProcessor` converts raw label text into a `ParsedNutrition` object using regex patterns. It handles:

- Serving size extraction (numeric + unit patterns)
- Calories
- Macros: protein, carbs, fat (including saturated fat, trans fat)
- Fiber, sugar, added sugar
- Micronutrients: sodium, cholesterol, vitamin D, calcium, iron, potassium
- Brand and category inference from common label patterns
- `warnings` list for fields that were present but ambiguous

The parser is regex-first and intentionally conservative: if a field can't be extracted with reasonable confidence, it leaves it as `None` and adds a warning rather than guessing.

---

### Infra: OCR (`infra/ocr/`)

Two backends, both implement `extract_text(image_path: Path) → str`:

**`FoodOCRExtractor` (Tesseract)**
- Imports are lazy (`importlib`) so the package works without OCR extras installed
- Preprocessing pipeline: convert to grayscale → bilateral filter → Otsu threshold → morphology open → `pytesseract.image_to_string`
- HEIC/HEIF: converted to a temp PNG before processing; temp file is always cleaned up in `finally`
- `save_uploaded_image_to_tempfile(uploaded_file)` — Streamlit-compatible helper; reads `UploadedFile`, opens via PIL, saves as temp PNG, returns `Path`. Caller is responsible for cleanup.

**`OllamaVisionOCRExtractor`**
- Uses the OpenAI-compatible chat completions API at `settings.ollama_host`
- Converts image to PNG bytes via `image_path_to_png_bytes`, base64-encodes it, sends as a multimodal message
- Default prompt instructs the model to return only raw label text with no commentary or markdown
- `OCRException` with typed `OCRErrorType` is raised on failure; the UI translates error types into actionable user-facing hints

**`OCRErrorType` enum** (in `errors.py`):
`IMAGE_NOT_FOUND`, `INVALID_IMAGE`, `OLLAMA_UNREACHABLE`, `OLLAMA_BAD_RESPONSE`, `OLLAMA_MODEL_ERROR`, `PROCESSING_ERROR`

**`image_utils.py`**: shared utilities (`image_path_to_png_bytes`, `encode_image`) used by the Ollama backend.

---

### Utils

**`utils/conversions.py`** — Simple unit math constants and functions (`g_to_oz`, `oz_to_g`, `mg_to_g`, `g_to_mg`). Used where inline conversion is needed outside the DB table.

**`utils/search.py`** — See [Search Implementation](#search-implementation) below.

---

### CLI (`cli/main.py`)

Built with [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/) for formatted table output. Sub-command groups:

| Group | Commands |
|---|---|
| `db` | `init` |
| `food` | `add`, `get`, `search`, `update`, `delete` |
| `variant` | `add`, `list` |
| `unit` | `list`, `convert` |
| `export` | `json`, `csv` |
| `parse` | `text`, `ocr` |

Date parsing (`_parse_date`) accepts both `YYYY-MM-DD` and `MM/DD/YYYY`. All commands call `make_food_db(settings.db_path)` — the same path the UI uses.

---

### UI (`ui/`)

Built with Streamlit. Top-level layout is five tabs: **Foods**, **Import**, **Inventory**, **Export**, **Units**.

**`ui/app.py`** — Entry point. `@st.cache_resource` ensures the DB connection is created once per server process. `init_state()` sets up session state keys at startup.

**`ui/state.py`** — Centralizes session state key constants (`KEY_SELECTED_FOOD_ID`, `KEY_PARSED`, etc.) and `init_state()`. `make_form_key(action, entity_id)` generates stable widget keys to avoid Streamlit form key collisions.

**`ui/pages/`**:
- `foods.py` — Search/filter, food list, food detail with edit and delete, variant management sub-panel with its own add/edit/delete
- `import_page.py` — Paste text or upload image → parse/OCR → staged preview with warnings → review form → save. Duplicate detection before save. Typed `OCRException` handling with user-friendly hints per error type.
- `inventory.py` — Read-only filtered view of all inventory items (joined across food + variant + inventory tables)
- `db_admin.py` — Export JSON/CSV; DB path display
- `units.py` — Unit list and interactive converter

**`ui/components/form_food.py`** — Shared food form used in both add (Import) and edit (Foods) modes. `render_food_form` accepts a `prefill: ParsedNutrition` for import mode and a `current: FoodOut` for edit mode. `_opt_num` renders optional numeric fields correctly: `None` renders blank (no default zero), but `0.0` is preserved as a meaningful value.

---

## Data Model

```
foods
  id, name (unique), category, brand
  serving_size, serving_unit, servings_per_container, serving_size_text, serving_mass_g
  calories, protein_g, carbs_g, fat_g
  saturated_fat_g, trans_fat_g, cholesterol_mg
  fiber_g, sugar_g, added_sugar_g
  sodium_mg, vitamin_d_mcg, calcium_mg, iron_mg, potassium_mg
  ingredients, best_by_date
  created_at, updated_at

food_variants
  id, food_id (FK → foods)
  store_name, brand, price
  package_size, package_unit
  notes, created_at

inventory_items
  id, variant_id (FK → food_variants)
  quantity, unit, purchase_date

units
  id, unit_name (unique), unit_symbol (unique)
  to_grams (NULL for non-weight units), is_base

food_units
  id, food_id (FK), unit_id (FK)
  unit_to_grams   ← per-food override (e.g., 1 tbsp peanut butter = 16g)
  UNIQUE(food_id, unit_id)
```

**Design intent:** `foods` holds the canonical product — what it is, what's in it per serving. `food_variants` holds where you buy it and for how much. This lets you compare "Greek Yogurt at Costco ($8.99/907g)" vs "Greek Yogurt at Aldi ($3.49/500g)" without duplicating nutrition data.

---

## OCR Backends

| | Tesseract | Ollama Vision |
|---|---|---|
| Setup | `brew install tesseract` + pip extras | `ollama pull <model>` + Ollama running |
| Works offline | ✅ | ✅ (local model) |
| HEIC/HEIF | ✅ (via pillow-heif → temp PNG) | ✅ (via pillow-heif → PNG bytes) |
| Accuracy on clean labels | Good | Often better (understands layout) |
| Accuracy on noisy/curved labels | Moderate | Better |
| Speed | Fast | Slower (model inference) |
| Requires GPU | No | Optional (CPU mode works) |

Switch with `OCR_BACKEND=ollama_vision` in `.env`. No code changes required.

---

## Search Implementation

`search_foods_smart` in the repository uses `fuzzy_score` from `utils/search.py`:

1. Fetch candidate rows (up to `search_candidate_limit`) filtered by any hard filters (category, brand, store)
2. Score each candidate against the query using `fuzzy_score`
3. Return top `search_result_limit` results with score ≥ `search_min_score`

**`fuzzy_score(query, candidate) → float [0, 1]`**:
- Normalizes both strings (lowercase, `&` → `and`, collapse whitespace/hyphens)
- Returns `1.0` for direct substring match
- Otherwise: `0.65 × token_overlap + 0.35 × SequenceMatcher_ratio`
- Token overlap is the fraction of query tokens present in the candidate; handles multi-word queries well
- SequenceMatcher handles misspellings and OCR noise

Default thresholds (`search_min_score=0.35`, `search_candidate_limit=200`, `search_result_limit=50`) are configurable via `.env`.

---

## Design Decisions

**Why SQLite?** Local-first, zero infrastructure, single portable file. Enough for a personal catalogue at any realistic scale.

**Why pydantic-settings?** Centralizes all configuration in one place; `.env` file support is automatic; avoids scattered `os.getenv()` calls.

**Why lazy OCR imports?** The package is usable (CLI, UI, core features) without installing Tesseract or pytesseract. `RuntimeError` is raised with a clear install instruction if OCR is called without extras.

**Why separate `foods` and `food_variants`?** Avoids duplicating nutrition data when the same product is sold at multiple stores. The canonical food holds the nutrition facts; variants hold price/packaging/store info.

**Why the `ParsedNutrition.warnings` list?** Explicit, inspectable signal for uncertain extractions. The UI surfaces these as `st.warning()` calls before the user saves, so the user can correct them rather than silently saving wrong data.

**Why `upsert_food` as the default path?** For personal use, re-importing a label should update the record, not fail with a duplicate-name error. The CLI `food add` defaults `--upsert True`. The import page always upserts (with a duplicate warning shown to the user first).

---

## Extension Points

**Add a new OCR backend:**
1. Create `src/food_db/infra/ocr/your_backend.py` implementing `extract_text(image_path: Path) → str`
2. Add a new `OCRErrorType` variant if needed
3. Add a `case "your_backend"` branch in `core/usecases.ocr_image_to_nutrition`
4. Add the backend name to `Settings.ocr_backend` documentation

**Add a new nutrition field:**
1. Add the column to `Food` ORM class and run `db init` (idempotent `CREATE TABLE IF NOT EXISTS` will not add the column to existing DBs — use an ALTER TABLE migration or recreate)
2. Add to `FoodCreate`, `FoodUpdate`, `FoodOut` Pydantic models
3. Add to `FoodTextProcessor` regex patterns
4. Add the field to `form_food.py` UI form

**Add a new UI page:**
1. Create `src/food_db/ui/pages/your_page.py` with `render_page(*, db, ...)` signature
2. Import and add a tab in `ui/app.py`

---

## Known Limitations

- **Schema migrations:** `db.init()` is idempotent for table creation but does not run column-level migrations. Adding a new field to an existing DB requires a manual `ALTER TABLE` or recreating the DB.
- **Concurrency:** SQLite handles multiple readers but single writer. Concurrent UI + CLI writes are safe at low frequency but not tested under load.
- **OCR accuracy:** Regex-based parsing works well on standard USDA-format labels; non-standard layouts (e.g., restaurant nutrition cards, foreign labels) may produce low-confidence results with warnings.
- **No authentication:** This is a personal local tool. Do not expose the Streamlit port to untrusted networks.