from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Compatibility with HEIC/HEIF extension images
from io import BytesIO
from PIL import Image
import tempfile
import pillow_heif


# Enable PIL to open HEIC/HEIF
pillow_heif.register_heif_opener()

@dataclass
class FoodOCRExtractor:
    """OCR extraction using pytesseract + OpenCV.

    This module is optional. Install with:
        uv sync --extra ocr

    And ensure your OS has the `tesseract` binary installed.
    """

    tesseract_cmd: str | None =  r'/opt/homebrew/bin/tesseract'

    def extract_text(self, image_path: Path) -> str:
        try:
            import cv2  # type: ignore
            import numpy as np  # type: ignore
            import pytesseract  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "OCR dependencies not installed. Run: uv sync --extra ocr"
            ) from e

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        
        # Ensure HEIC/HEIF files become readable PNG for cv2
        image_path = self._ensure_readable_image_path(image_path)

        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"Could not read image: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 9, 75, 75)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # small morphology open to reduce noise
        kernel = np.ones((1, 1), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        config = r"--oem 3 --psm 6"
        text = pytesseract.image_to_string(binary, config=config)
        return (text or "").strip()

    @staticmethod
    def save_uploaded_image_to_tempfile(uploaded_file) -> Path:
        """
        Streamlit UploadedFile -> temp PNG path.
        Works for heic/heif via pillow-heif, and for jpg/png/webp via PIL.
        """
        data = uploaded_file.getvalue()
        img = Image.open(BytesIO(data)).convert("RGB")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format="PNG")
        tmp.close()
        return Path(tmp.name)
    
    @staticmethod
    def _ensure_readable_image_path(image_path: Path) -> Path:
        """
        If HEIC/HEIF, convert file to a temp PNG path.
        Otherwise return original.
        """
        suffix = image_path.suffix.lower()
        if suffix not in {".heic", ".heif"}:
            return image_path

        data = image_path.read_bytes()
        img = Image.open(BytesIO(data)).convert("RGB")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        img.save(tmp.name, format="PNG")
        tmp.close()
        return Path(tmp.name)