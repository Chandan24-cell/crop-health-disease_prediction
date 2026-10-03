import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Security: Protect against decompression bomb attacks
Image.MAX_IMAGE_PIXELS = 16_000_000


@dataclass
class DecodedImage:
    rgb: np.ndarray
    format: str
    width: int
    height: int


def detect_image_format(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "GIF"
    if (
        len(data) > 12
        and data[4:8] == b"ftyp"
        and data[8:12] in (b"heic", b"heix", b"hevc", b"mif1")
    ):
        return "HEIC"
    raise ValueError("Unsupported image content; upload JPEG or PNG")


def decode_image(
    data: bytes, max_dimension: int = 4096, strip_gps: bool = True
) -> DecodedImage:
    fmt = detect_image_format(data)
    if fmt not in {"JPEG", "PNG"}:
        raise ValueError("Only JPEG and PNG images are supported")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as opened_image:
            image: Image.Image = ImageOps.exif_transpose(opened_image)
            width, height = image.size
            if width > max_dimension or height > max_dimension:
                raise ValueError(f"Image dimensions must not exceed {max_dimension}px")
            if strip_gps and image.getexif():
                exif = image.getexif()
                if 34853 in exif:
                    del exif[34853]
                    cleaned = Image.new(image.mode, image.size)
                    cleaned.putdata(list(image.getdata()))
                    image = cleaned
            rgb = np.asarray(image.convert("RGB"))
            return DecodedImage(rgb=rgb, format=fmt, width=width, height=height)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Image could not be safely decoded") from exc


def assess_quality(rgb: np.ndarray) -> dict[str, object]:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    h, w = rgb.shape[:2]
    issues: list[str] = []
    if blur < 100:
        issues.append("blurry")
    if brightness < 50:
        issues.append("too_dark")
    if min(w, h) < 128:
        issues.append("low_resolution")
    return {
        "blur_score": blur,
        "brightness": brightness,
        "resolution": [w, h],
        "issues": issues,
    }
