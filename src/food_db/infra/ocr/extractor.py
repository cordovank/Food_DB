from __future__ import annotations

import cv2
import numpy as np
import pytesseract
import tempfile

from dataclasses import dataclass, field
from pathlib import Path
from io import BytesIO
from PIL import Image
import pillow_heif

from food_db.config import settings

# Enable PIL to open HEIC/HEIF
pillow_heif.register_heif_opener()

@dataclass
class FoodOCRExtractor:
    """OCR extraction using pytesseract + OpenCV.

    tesseract_cmd: path to the tesseract binary.
      - None (default) → use whatever is on PATH (works on Linux + most macOS).
      - Set via OCR_TESSERACT_CMD env var or .env to override
        (e.g. /opt/homebrew/bin/tesseract on macOS Apple Silicon).
    """

    # tesseract_cmd: str | None =  r'/opt/homebrew/bin/tesseract'
    tesseract_cmd: str | None = field(
        default_factory=lambda: settings.ocr_tesseract_cmd
    )

    def extract_text(self, image_path: Path) -> str:
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        
        # Ensure HEIC/HEIF files become readable PNG for cv2
        resolved = self._ensure_readable_image_path(image_path)
        # Track whether we created a temp file so we can clean it up
        temp_created = resolved != image_path

        try:
            img = cv2.imread(str(image_path))
            if img is None:
                raise FileNotFoundError(f"Could not read image: {resolved}")

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.bilateralFilter(gray, 9, 75, 75)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # small morphology open to reduce noise
            kernel = np.ones((1, 1), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

            config = r"--oem 3 --psm 6"
            text = pytesseract.image_to_string(binary, config=config)
            return (text or "").strip()
        finally:
            if temp_created:
                resolved.unlink(missing_ok=True)

    @staticmethod
    def save_uploaded_image_to_tempfile(uploaded_file) -> Path:
        """
        Streamlit UploadedFile -> temp PNG path.
        Works for heic/heif via pillow-heif, and for jpg/png/webp via PIL.
        Caller is responsible for unlinking the file after use.
        """
        data = uploaded_file.getvalue()
        img = Image.open(BytesIO(data)).convert("RGB")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format="PNG")
        tmp.close()
        return Path(tmp.name)
    
    @staticmethod
    def _ensure_readable_image_path(image_path: Path) -> Path:
        """If HEIC/HEIF, convert file to a temp PNG path. Otherwise return original."""
        if image_path.suffix.lower() not in {".heic", ".heif"}:
            return image_path

        data = image_path.read_bytes()
        img = Image.open(BytesIO(data)).convert("RGB")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format="PNG")
        tmp.close()
        return Path(tmp.name)