import io
from pathlib import Path

import httpx
import numpy as np
import pytest
from PIL import Image, ImageFilter

from backend.app.main import app
from backend.app.schemas import PredictResponse


def create_synthetic_leaf(
    base_color: tuple[int, int, int] = (45, 130, 45),
    pattern: str | None = None,
    blur: bool = False,
    dark: bool = False,
    size: tuple[int, int] = (256, 256),
) -> bytes:
    """Generate in-memory synthetic images for contract and edge-case testing."""
    if dark:
        img_arr = np.full((size[1], size[0], 3), (12, 18, 12), dtype=np.uint8)
        img = Image.fromarray(img_arr)
    elif pattern == "noise":
        img_arr = np.random.randint(0, 256, (size[1], size[0], 3), dtype=np.uint8)
        img = Image.fromarray(img_arr)
    else:
        # Green foliage background with leaf vein structure
        img_arr = np.full((size[1], size[0], 3), base_color, dtype=np.uint8)
        # Add texture variations
        noise = np.random.randint(-15, 15, (size[1], size[0], 3))
        img_arr = np.clip(img_arr.astype(int) + noise, 0, 255).astype(np.uint8)

        # Add disease spot patterns
        if pattern == "rust":
            # Rust reddish pustules
            for _ in range(15):
                rx, ry = np.random.randint(40, 210, 2)
                img_arr[ry : ry + 8, rx : rx + 6] = (165, 42, 42)
        elif pattern == "concentric_blight":
            # Dark brown spots with target rings
            for _ in range(5):
                cx, cy = np.random.randint(60, 190, 2)
                for r in range(14, 0, -3):
                    c_val = 40 if r % 6 == 0 else 75
                    img_arr[cy - r : cy + r, cx - r : cx + r] = (c_val, c_val // 2, 20)
        elif pattern == "lesions":
            # Water-soaked greasy patches
            for _ in range(4):
                lx, ly = np.random.randint(50, 180, 2)
                img_arr[ly : ly + 25, lx : lx + 35] = (60, 70, 50)

        img = Image.fromarray(img_arr)

    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=8))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.mark.anyio
async def test_contract_blurry_image_triggers_retake() -> None:
    blurry_bytes = create_synthetic_leaf(blur=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("blurry_leaf.jpg", blurry_bytes, "image/jpeg")},
        )
    assert res.status_code == 200
    data = res.json()
    validated = PredictResponse(**data)
    assert validated.status == "retake"
    assert any("blur" in issue.lower() for issue in validated.quality.issues)
    assert "X-Request-ID" in res.headers
    assert res.headers.get("X-Content-Type-Options") == "nosniff"


@pytest.mark.anyio
async def test_contract_dark_image_triggers_retake() -> None:
    dark_bytes = create_synthetic_leaf(dark=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("dark_leaf.jpg", dark_bytes, "image/jpeg")},
        )
    assert res.status_code == 200
    data = res.json()
    validated = PredictResponse(**data)
    assert validated.status == "retake"
    assert any(
        "dark" in issue.lower() or "brightness" in issue.lower()
        for issue in validated.quality.issues
    )


@pytest.mark.anyio
async def test_contract_non_leaf_noise() -> None:
    noise_bytes = create_synthetic_leaf(pattern="noise")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("noise.jpg", noise_bytes, "image/jpeg")},
        )
    assert res.status_code == 200
    data = res.json()
    validated = PredictResponse(**data)
    assert validated.status in {"unsupported", "uncertain", "retake", "ok"}


@pytest.mark.anyio
async def test_contract_healthy_leaf() -> None:
    healthy_bytes = create_synthetic_leaf(base_color=(38, 142, 45))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("healthy_leaf.jpg", healthy_bytes, "image/jpeg")},
            data={"crop_hint": "Maize"},
        )
    assert res.status_code == 200
    data = res.json()
    validated = PredictResponse(**data)
    assert len(validated.top3) == 3
    assert validated.latency_ms > 0
    assert validated.model_version is not None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "pattern_type,crop_hint",
    [
        ("rust", "Maize"),
        ("concentric_blight", "Tomato"),
        ("lesions", "Potato"),
        (None, "Tomato"),
    ],
)
async def test_contract_disease_patterns(
    pattern_type: str | None, crop_hint: str
) -> None:
    img_bytes = create_synthetic_leaf(pattern=pattern_type)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("leaf.jpg", img_bytes, "image/jpeg")},
            data={"crop_hint": crop_hint, "language": "en"},
        )
    assert res.status_code == 200
    data = res.json()
    validated = PredictResponse(**data)
    assert validated.quality.blur_score > 0
    assert validated.severity.category in {"Mild", "Moderate", "Severe", "Not assessed"}
    assert validated.calibrated_confidence >= 0.0


@pytest.mark.anyio
async def test_contract_demo_images_if_present() -> None:
    demo_dir = Path("demo_images")
    if not demo_dir.exists():
        pytest.skip("Demo images not found")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        for img_path in demo_dir.glob("*.jpg"):
            img_bytes = img_path.read_bytes()
            res = await client.post(
                "/api/v1/predict",
                files={"image": (img_path.name, img_bytes, "image/jpeg")},
            )
            assert res.status_code == 200
            data = res.json()
            PredictResponse(**data)


@pytest.mark.anyio
async def test_contract_empty_upload_fails_400() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("empty.jpg", b"", "image/jpeg")},
        )
    assert res.status_code == 400


@pytest.mark.anyio
async def test_contract_invalid_image_type_fails_415() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://fieldnote.test"
    ) as client:
        res = await client.post(
            "/api/v1/predict",
            files={"image": ("script.sh", b"#!/bin/bash\necho test", "text/plain")},
        )
    assert res.status_code == 415
