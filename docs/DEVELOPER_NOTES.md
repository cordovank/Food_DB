## Developer Notes (Architecture + Where to Add Features)

FoodDB follows a **clean-ish layering** so UI/CLI stay thin and all behavior is testable:

### High-level flow

- **UI / CLI**  
  `src/food_db/ui/app.py` and `src/food_db/cli/main.py` should mostly:
  - collect input
  - call a usecase/service
  - display results/errors

- **Usecases (workflow orchestration)**  
  `src/food_db/core/usecases.py` is where “multi-step” operations live, e.g.:
  - OCR image → text → parse → normalize → upsert food
  - parse text → normalize units → return `FoodCreate`
  - export DB → JSON/CSV

- **Services (business rules)**  
  `src/food_db/core/services.py` holds “domain decisions”, e.g.:
  - how to upsert (unique key rules)
  - variant selection (brand/store priority)
  - validation decisions (what’s required, how to handle missing fields)
  - data cleanup rules (rounding, default units)

- **Repository (data access contract)**  
  `src/food_db/core/repository.py` is the boundary between business logic and persistence:
  - CRUD methods (`upsert_food`, `search_foods`, `add_variant`, `list_units`, etc.)
  - conversion helpers that require DB lookups (unit tables)
  - keep this layer deterministic and easy to unit test (prefer no Streamlit/CLI dependencies)

- **Infra (adapters / external dependencies)**  
  `src/food_db/infra/` is “impure code” and integrations:
  - `infra/db/sql_db.py`: SQLAlchemy engine/session + ORM mapping
  - `infra/ocr/extractor.py`: OCR + HEIC/HEIF compatibility (Pillow -> temp PNG -> OpenCV)
  - `infra/nlp/processor.py`: regex-first parsing / text normalization

- **Core models**  
  `src/food_db/core/models.py` defines the Pydantic models used across layers:
  - `FoodCreate`, `FoodUpdate`, `FoodVariantCreate`, `NutritionParseResult`, etc.
  - This is where schema rules live (types, defaults, optionality).

### Where to add common features

#### 1) “Smart search” (fuzzy + filters)
- Add matching logic in **services**:
  - `core/services.py`: `search_foods_smart(query, filters)`
- Keep SQL filtering in **repository**:
  - `core/repository.py`: add optional filters (category, brand, store)
- UI changes:
  - `ui/app.py`: add filter widgets + call the new service method

#### 2) Inventory forecasting (basic ML / regression)
- Put the “forecast pipeline” in **usecases**:
  - `core/usecases.py`: `forecast_consumption(food_id, horizon_days=30)`
- Store time-series events in DB (new table):
  - extend `infra/db/sql_db.py` with a table like `consumption_events`
- ML logic can live in `core/services.py` or a new module:
  - `core/forecasting.py` (clean separation)

#### 3) LLM integration (meal plans / macro balance)
- Add a new adapter under **infra**:
  - `infra/llm/client.py` (OpenAI/Ollama/etc. behind a simple interface)
- Put orchestration in **usecases**:
  - `core/usecases.py`: `generate_meal_plan(nutrition_dict, preferences)`
- Keep prompt templates in a dedicated folder:
  - `src/food_db/prompts/…` (optional but recommended)
- Avoid importing LLM deps in core; keep it behind the infra adapter.

#### 4) Unit/brand selection dropdowns (DB-driven UI)
- Repository:
  - `list_distinct_brands()`, `list_distinct_stores()`, `list_units()`
- UI:
  - `ui/app.py`: convert text inputs to `selectbox` populated from repo calls
- Services:
  - enforce canonicalization rules (e.g., “Costco Wholesale” vs “Costco”)

#### 5) More robust OCR parsing
- Keep OCR strictly “image -> text” in `infra/ocr/extractor.py`
- Improve parsing in `infra/nlp/processor.py` (regex patterns, label heuristics)
- Glue logic in `core/usecases.py`:
  - apply cleaning + parsing + normalization + warnings

### Guardrails / Engineering tips

- **Don’t let UI/CLI talk to SQLAlchemy sessions directly.**  
  Always go through `FoodDatabase` / repository methods so behavior is consistent.

- **Normalize units at boundaries.**  
  Parsing may return `mg` or `oz`, but `services/usecases` should normalize to:
  - grams for macros (`protein_g`, `fat_g`, etc.)
  - mg for sodium (`sodium_mg`)
  - keep original `serving_unit` but store normalized values consistently

- **Keep OCR optional.**  
  Don’t import OpenCV/pytesseract unless called (lazy import), so base installs stay light.

- **Testing strategy**
  - `tests/test_repository.py`: CRUD + unit conversions using a temp SQLite file
  - `tests/test_processor.py`: parsing reliability from sample label text
  - `tests/test_usecases.py`: end-to-end “parse->upsert” without Streamlit

---