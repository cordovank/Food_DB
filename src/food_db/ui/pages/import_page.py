from __future__ import annotations
import streamlit as st
from food_db.core.usecases import parse_text_to_nutrition, ocr_image_to_nutrition
from food_db.ui.state import KEY_PARSED
from food_db.ui.components.form_food import render_food_form


def render_page(*, db, settings):
    st.subheader("Import")

    # OCR backend info is a developer detail — tuck it away
    with st.expander("OCR settings", expanded=False):
        st.caption(f"Backend: {settings.ocr_backend}")
        if (settings.ocr_backend or "").lower() == "ollama_vision":
            st.caption(f"Ollama host: {settings.ollama_host}")
            st.caption(f"Vision model: {settings.ollama_vision_model}")

    t1, t2 = st.tabs(["Paste text", "Upload image"])

    with t1:
        raw = st.text_area("Paste label text", height=160)
        if st.button("Parse text", type="primary"):
            if not raw.strip():
                st.warning("Paste some text first.")
            else:
                st.session_state[KEY_PARSED] = parse_text_to_nutrition(raw)
                st.success("Parsed — review below.")

    with t2:
        img = st.file_uploader(
            "Upload label image",
            type=["png", "jpg", "jpeg", "webp", "heic", "heif"],
        )
        if st.button("Run OCR", type="primary"):
            if img is None:
                st.warning("Upload an image first.")
            else:
                _run_ocr(img, settings)

    st.divider()
    parsed = st.session_state.get(KEY_PARSED)
    if not parsed:
        st.info("Nothing staged yet.")
        return

    if parsed.warnings:
        for w in parsed.warnings:
            st.warning(w)

    # Clean preview — not a raw dict
    st.markdown("#### Staged fields")
    preview = {
        "Name":          parsed.name,
        "Brand":         parsed.brand,
        "Category":      parsed.category,
        "Serving size":  f"{parsed.serving_size} {parsed.serving_unit}" if parsed.serving_size else None,
        "Calories":      parsed.calories,
        "Protein (g)":   parsed.protein_g,
        "Carbs (g)":     parsed.carbs_g,
        "Fat (g)":       parsed.fat_g,
    }
    for label, val in preview.items():
        c1, c2 = st.columns([2, 3])
        c1.write(label)
        c2.write(str(val) if val is not None else "—")

    with st.expander("Raw extracted text", expanded=False):
        st.code(parsed.raw_text or "", language="text")

    # Duplicate warning (Fix 2)
    if parsed.name:
        existing = db.get_food_by_name(parsed.name)
        if existing:
            st.warning(
                f"⚠️ **{parsed.name}** already exists (id={existing.id}). "
                "Saving will overwrite it."
            )

    st.markdown("#### Review & save")
    data = render_food_form(
        mode="add", db=db, current=None, prefill=parsed,
        form_key="import_save_form",
    )
    if data:
        db.upsert_food(data)
        st.success("Saved to library.")
        st.session_state[KEY_PARSED] = None
        st.rerun()


def _run_ocr(img, settings):
    """Run OCR with typed, actionable error handling."""
    try:
        from food_db.infra.ocr.extractor import FoodOCRExtractor
        from food_db.infra.ocr.errors import OCRException, OCRErrorType

        tmp_png = FoodOCRExtractor.save_uploaded_image_to_tempfile(img)

        try:
            from food_db.core.usecases import ocr_image_to_nutrition
            st.session_state[KEY_PARSED] = ocr_image_to_nutrition(tmp_png)
            st.success("OCR complete — review below.")

        except OCRException as e:
            st.error(f"OCR failed: {e.message}")
            _ocr_hint(e.error_type, settings)

    except RuntimeError as e:
        st.error(str(e))
        st.info("Install OCR extras: `uv sync --extra ocr`")
    except Exception as e:
        st.error(f"Unexpected error: {e}")


def _ocr_hint(error_type, settings):
    from food_db.infra.ocr.errors import OCRErrorType
    hints = {
        OCRErrorType.IMAGE_NOT_FOUND:    "The uploaded file could not be read. Try re-uploading.",
        OCRErrorType.INVALID_IMAGE:      "Unsupported image format. Use JPG, PNG, WEBP, or HEIC.",
        OCRErrorType.OLLAMA_UNREACHABLE: f"Cannot reach Ollama at {settings.ollama_host}. Is it running?",
        OCRErrorType.OLLAMA_MODEL_ERROR: f"Model '{settings.ollama_vision_model}' returned an error. Check Ollama logs.",
        OCRErrorType.OLLAMA_BAD_RESPONSE:"Ollama returned an empty response. Try a clearer image.",
        OCRErrorType.PROCESSING_ERROR:   "Text extraction failed. Try a higher-contrast image.",
    }
    hint = hints.get(error_type)
    if hint:
        st.info(hint)