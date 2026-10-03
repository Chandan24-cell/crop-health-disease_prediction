import io
import json
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from PIL import Image

from backend.app.services.advice import AdviceService
from backend.app.services.quality import (
    assess_quality,
    decode_image,
    detect_image_format,
)
from backend.app.services.report import ScanStore
from backend.app.services.severity import (
    estimate_severity,
    has_conflicting_signals,
    load_severity_bands,
    segment_leaf,
)


def png_bytes(
    color: tuple[int, int, int] = (40, 180, 40), size: tuple[int, int] = (240, 240)
) -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format="PNG")
    return stream.getvalue()


def test_detect_and_decode_png() -> None:
    decoded = decode_image(png_bytes())
    assert decoded.format == "PNG"
    assert (decoded.width, decoded.height) == (240, 240)
    assert decoded.rgb.shape == (240, 240, 3)


def test_rejects_bad_bytes_and_unsupported_format() -> None:
    with pytest.raises(ValueError, match="Unsupported image"):
        detect_image_format(b"not an image")
    with pytest.raises(ValueError, match="Only JPEG"):
        decode_image(b"GIF89a" + b"0" * 32)


def test_decode_rejects_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        decode_image(png_bytes(size=(5000, 20)), max_dimension=4096)


def test_quality_reports_blur_darkness_and_small_size() -> None:
    result = assess_quality(np.zeros((80, 80, 3), dtype=np.uint8))
    assert set(cast(list[str], result["issues"])) == {
        "blurry",
        "too_dark",
        "low_resolution",
    }
    assert result["resolution"] == [80, 80]


def test_severity_returns_masks() -> None:
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:] = (20, 170, 30)
    result = estimate_severity(image)
    assert cast(float, result["percent"]) >= 0
    assert result["category"] in {"Mild", "Moderate", "Severe"}
    assert result["lesion_mask_png_b64"]
    assert result["leaf_outline_png_b64"]
    assert 0.0 <= cast(float, result["confidence"]) <= 1.0
    assert cast(float, result["uncertainty_percent"]) >= 0.0


def test_severity_excludes_background_from_denominator(tmp_path: Path) -> None:
    image = np.zeros((128, 128, 3), dtype=np.uint8)
    image[:] = (115, 65, 35)  # brown background must not count as leaf lesion
    image[24:104, 32:96] = (35, 165, 45)
    bands = tmp_path / "severity.json"
    bands.write_text(
        json.dumps({"default": {"mild_max": 5, "moderate_max": 25}, "crops": {}})
    )
    result = estimate_severity(image, crop="tomato", bands_path=bands)
    assert cast(int, result["leaf_area_px"]) < image.shape[0] * image.shape[1]
    assert result["percent"] == 0.0


def test_severity_bands_are_crop_specific(tmp_path: Path) -> None:
    config = tmp_path / "severity.json"
    config.write_text(
        json.dumps(
            {
                "default": {"mild_max": 5, "moderate_max": 25},
                "crops": {"tomato": {"mild_max": 3, "moderate_max": 18}},
            }
        )
    )
    assert load_severity_bands(str(config))["tomato"] == {
        "mild_max": 3.0,
        "moderate_max": 18.0,
    }


def test_severity_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="RGB image"):
        segment_leaf(np.zeros((8, 8, 3), dtype=np.uint8))


def test_severity_invalid_bands_raise(tmp_path: Path) -> None:
    config = tmp_path / "invalid.json"
    config.write_text(
        json.dumps({"crops": {"tomato": {"mild_max": 30, "moderate_max": 20}}})
    )
    with pytest.raises(ValueError, match="Invalid severity bands"):
        load_severity_bands(str(config))


def test_severity_uses_optional_lesion_model_inside_leaf() -> None:
    class AllLesionModel:
        input_shape = (None, 32, 32, 3)

        @staticmethod
        def predict(images: np.ndarray, verbose: int = 0) -> np.ndarray:
            return np.ones((len(images), 32, 32, 1), dtype=np.float32)

    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:] = (125, 70, 40)
    image[20:80, 20:80] = (40, 160, 50)
    result = estimate_severity(image, lesion_model=AllLesionModel())
    assert result["method"] == "leaf_grabcut+lesion_unet"
    assert cast(int, result["lesion_area_px"]) <= cast(int, result["leaf_area_px"])


def test_severity_failed_leaf_segmentation_returns_not_assessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cv2

    def fail_grabcut(*args: object, **kwargs: object) -> None:
        raise cv2.error("forced GrabCut failure")

    monkeypatch.setattr(cv2, "grabCut", fail_grabcut)
    result = estimate_severity(np.full((64, 64, 3), (20, 30, 180), dtype=np.uint8))
    assert result["category"] == "Not assessed"
    assert result["confidence"] == 0.0


def test_classifier_and_severity_conflicts() -> None:
    assert has_conflicting_signals("Tomato_healthy", 12.0, "Mild")
    assert has_conflicting_signals("Tomato_Early_blight", 4.0, "Mild")
    assert not has_conflicting_signals("Tomato_healthy", 10.0, "Moderate")
    assert not has_conflicting_signals("Unknown", 70.0, "Severe")
    assert not has_conflicting_signals("Tomato_Early_blight", 0.0, "Not assessed")


def test_advice_lookup(tmp_path: Path) -> None:
    path = tmp_path / "kb.json"
    path.write_text(
        json.dumps(
            {"Tomato_Test": {"crop": "Tomato", "severity_advice": {"mild": "Monitor"}}}
        )
    )
    service = AdviceService(path)
    assert service.get("Tomato_Test", "Mild")["specific_advice"] == "Monitor"
    assert service.get("missing", "Mild") == {}


def test_scan_store_keeps_newest_and_caps() -> None:
    store = ScanStore(limit=2)
    store.add_scan({"n": 1})
    store.add_scan({"n": 2})
    store.add_scan({"n": 3})
    assert list(store.records) == [{"n": 3}, {"n": 2}]
