from __future__ import annotations

from io import BytesIO
from pathlib import Path
from PIL import Image
import pillow_heif
import base64

# Enable PIL to open HEIC/HEIF
pillow_heif.register_heif_opener()


def image_path_to_png_bytes(image_path: Path) -> bytes:
    """
    Load any PIL-readable image (jpg/png/webp/heic/heif) and return PNG bytes.
    Keeps the Ollama payload consistent and avoids OpenCV decoding issues.
    """
    data = image_path.read_bytes()
    img = Image.open(BytesIO(data)).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def encode_image(img_bytes):
        return base64.b64encode(img_bytes).decode("utf-8")