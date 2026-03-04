## Developer Notes (Architecture + Where to Add Features)

FoodDB uses a **clean-ish layered architecture** so UI/CLI stay thin, and most behavior stays testable and reusable.

### High-level flow (what calls what)

* **Config (single source of truth)**
  `src/food_db/config.py` loads all runtime settings via env / `.env`, including:

  * `DB_PATH` (shared by CLI + UI)
  * Streamlit bind: `UI_HOST`, `UI_PORT`
  * OCR routing: `OCR_BACKEND` (`tesseract` | `ollama_vision`)
  * Ollama: `OLLAMA_HOST`, `OLLAMA_VISION_MODEL`

* **UI / CLI (thin adapters)**
  `src/food_db/ui/app.py` and `src/food_db/cli/main.py` should mostly:

  * collect user input
  * call a **usecase** or **service**
  * render output / actionable errors
    **Do not** touch SQLAlchemy sessions directly from UI/CLI.

* **Usecases (workflow orchestration)**
  `src/food_db/core/usecases.py` is where multi-step flows live, especially those that combine infra adapters + parsing:

  * OCR image → text → parse → return `ParsedNutrition`
  * routing OCR backend via `settings.ocr_backend`

* **Services (business rules + app facade)**
  `src/food_db/core/services.py` exposes the `FoodDatabase` facade used by CLI/UI:

  * Foods CRUD + upsert rules (`upsert_food` uses name uniqueness)
  * Smart search (SQL candidate fetch + fuzzy ranking)
  * Units + conversions
  * Variants CRUD + distinct lists (`stores()`, `brands()`)
  * Inventory CRUD + inventory overview (`inventory_all()`)
  * Export JSON/CSV
  * “Parsed → FoodCreate → upsert” (`add_from_parsed`)

* **Repository (DB boundary)**
  `src/food_db/core/repository.py` is the persistence boundary:

  * schema init + lightweight migration
  * deterministic CRUD queries
  * “broad candidate retrieval” for smart search
  * joined inventory queries for admin/inventory pages
    The repository is where SQLAlchemy lives.

* **Infra (impure adapters)**
  `src/food_db/infra/` contains external integration code:

  * `infra/db/sql_db.py`: engine/session factory (SQLite; `check_same_thread=False`)
  * OCR:

    * `infra/ocr/extractor.py`: Tesseract/OpenCV OCR + HEIC/HEIF conversion via Pillow+pillow-heif
    * `infra/ocr/ollama_vision.py`: Ollama vision OCR using OpenAI-compatible API
    * `infra/ocr/errors.py`: typed OCR exceptions
    * `infra/ocr/image_utils.py`: normalize images to PNG bytes + base64 encoding
  * Parsing:

    * `infra/nlp/processor.py`: regex-first label parsing into `ParsedNutrition`

* **Core models (ORM + Pydantic contracts)**
  `src/food_db/core/models.py` contains:

  * SQLAlchemy ORM: `Food`, `Unit`, `FoodVariant`, `InventoryItem`, `FoodUnit`
  * Pydantic contracts: `FoodCreate/Update/Out`, `Unit*`, `FoodVariant*`, `ParsedNutrition`
  * Inventory Pydantic contracts: `InventoryItemCreate/Update/Out`

---

## Data model & invariants (current reality)

* **foods**

  * canonical identity is `Food.name` (unique)
  * stores base serving + nutrition facts + label context fields (servings per container, serving_size_text, serving_mass_g, micronutrients, ingredients, best_by_date)

* **food_variants**

  * optional store/brand/price/package sizing tied to a canonical food
  * used for filtering (brand/store) and inventory linkage

* **inventory_items**

  * tracks quantities “on hand”, tied to a **variant** (not directly to canonical food)

* **units** and **food_units**

  * `units` holds weight conversion factors to grams where applicable
  * `food_units` can encode per-food conversions where needed (e.g., tbsp → grams for peanut butter)

---

## Schema initialization & migrations

### `FoodRepository.init_db()`

This method does two things:

1. `Base.metadata.create_all(...)`
   Creates tables for ORM models (including `inventory_items` / `food_variants` / etc.) if missing.

2. **Lightweight migration for `foods` only**
   Uses `PRAGMA table_info(foods)` then `ALTER TABLE foods ADD COLUMN ...` for newly introduced food columns.
   This is intentionally lightweight and avoids a full migration framework.

3. Seeds default `units` if missing.

**Rule:** if you add new columns to `foods`, extend the `add_col(...)` list in `init_db()`.
If you add a *new table*, it should be created automatically via `create_all()` (but consider data backfills separately).

---

## OCR + parsing pipeline

### Orchestration: `core/usecases.py`

`ocr_image_to_nutrition(image_path)` chooses OCR backend by `settings.ocr_backend`:

* `tesseract` (default): `FoodOCRExtractor()`
* `ollama_vision`: `OllamaVisionOCRExtractor(host, model)`

Then:

* calls `FoodTextProcessor().parse(text)`
* sets `parsed.raw_text = text`

### OCR adapters (infra)

* **Tesseract/OpenCV**: `infra/ocr/extractor.py`

  * lazy imports for OCR deps
  * HEIC/HEIF supported via PIL decode → temp PNG → OpenCV
* **Ollama vision**: `infra/ocr/ollama_vision.py`

  * converts image → PNG bytes → base64
  * calls Ollama using OpenAI-compatible `chat.completions`

**Guardrail:** OCR modules should remain “image → text only”. Parsing stays in `infra/nlp/processor.py`.

---

## Smart search (how it works today)

Smart search is implemented in **service + repository**:

* **Repository: `search_foods_filtered(...)`**

  * fast SQL candidate retrieval with optional filters (category, brand, store)
  * uses `LIKE` prefilter across canonical + variant fields
  * includes a fallback: if `LIKE` yields 0 rows, fetch a filtered candidate pool without the text predicate (so fuzzy matching can still succeed)

* **Service: `search_foods_smart(...)`**

  * scores candidates using `utils.search.fuzzy_score`
  * scores against multiple candidate strings (name, “brand name”, “category name”)
  * thresholded by `min_score`, then sorted

**Rule:** keep “DB narrowing” in repository, and “ranking / heuristics” in services.

---

## Inventory (where it lives)

* Repository methods:

  * `add_inventory_item`, `update_inventory_item`, `delete_inventory_item`
  * `list_inventory_for_variant`
  * `list_inventory_all()` returns joined, display-friendly rows (InventoryItem + Variant + Food)
  * `admin_counts()` returns counts for foods/variants/inventory

* Service methods:

  * thin pass-throughs: `add_inventory_item`, `inventory_all`, etc.

**Rule:** inventory joins/aggregation belongs in repository; any “business interpretation” belongs in services/usecases.

---

## Where to add common features

### 1) Add new CLI commands / flags

* Keep parsing/validation in CLI
* Route behavior to `FoodDatabase` methods (service)
* Avoid importing SQLAlchemy in CLI

### 2) Add a new workflow (multi-step)

Example: “OCR → parse → auto-save with optional overrides”

* Put orchestration in `core/usecases.py`
* Reuse infra adapters + `FoodTextProcessor`
* Persist using `FoodDatabase` service methods

### 3) Extend OCR backends

* Add a new adapter in `infra/ocr/`
* Add a new `OCR_BACKEND` option in config
* Update routing in `core/usecases.ocr_image_to_nutrition`

### 4) Add new columns / evolve schema

* For new **foods** columns: update `FoodRepository.init_db()` migration block
* For new tables: define ORM model in `core/models.py` and rely on `create_all()`
* If you need backfills, add an explicit one-time usecase/command (don’t hide it in UI)

### 5) Improve parsing reliability

* Keep improvements in `infra/nlp/processor.py` (regex, heuristics)
* Add warnings to `ParsedNutrition.warnings` for low confidence / missing fields
* Add “golden” parsing tests with sample label text

---

## Guardrails & reliability tips

* **Single DB path**: CLI + UI must share `settings.db_path` so refresh reflects writes.
* **Optional dependencies**:

  * OCR deps are lazy-imported (don’t import them from core/services)
  * CSV export requires pandas; keep it optional (current behavior)
* **Surface actionable failures**:

  * OCR: raise typed `OCRException` (or `RuntimeError` for missing deps)
  * CLI: exit codes for invalid input; keep messages concise and direct

---

## Testing strategy (what to prioritize)

* Repository tests using temp SQLite files:

  * schema init + seed
  * CRUD for foods/variants/inventory
  * smart search fallback behavior
* Parser tests (no OCR required):

  * parse a set of sample label texts → assert extracted fields + warnings
* Usecase tests:

  * “parse text → ParsedNutrition → add_from_parsed → stored food”

---
