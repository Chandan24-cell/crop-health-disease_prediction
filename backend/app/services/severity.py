"""Leaf-masked lesion segmentation and configurable severity estimation."""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np

DEFAULT_BANDS: dict[str, dict[str, float]] = {
    "default": {"mild_max": 5.0, "moderate_max": 25.0},
}


@lru_cache(maxsize=8)
def load_severity_bands(path: str) -> dict[str, dict[str, float]]:
    """Read crop-specific category thresholds, falling back to conservative defaults."""
    config_path = Path(path)
    if not config_path.is_file():
        return dict(DEFAULT_BANDS)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    bands: dict[str, dict[str, float]] = {}
    for crop, values in raw.get("crops", {}).items():
        mild = float(values["mild_max"])
        moderate = float(values["moderate_max"])
        if not 0 <= mild < moderate <= 100:
            raise ValueError(f"Invalid severity bands for {crop}")
        bands[crop.lower()] = {"mild_max": mild, "moderate_max": moderate}
    bands["default"] = {
        "mild_max": float(raw.get("default", {}).get("mild_max", 5.0)),
        "moderate_max": float(raw.get("default", {}).get("moderate_max", 25.0)),
    }
    return bands


def _largest_component(mask: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8
    )
    if count <= 1:
        return np.zeros_like(mask, dtype=np.uint8)
    component = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (labels == component).astype(np.uint8) * 255


def segment_leaf(rgb: np.ndarray, iterations: int = 3) -> tuple[np.ndarray, float]:
    """Segment the main leaf with Lab seed colors and GrabCut refinement."""
    if rgb.ndim != 3 or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 16:
        raise ValueError("Expected an RGB image at least 16x16 pixels")
    image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)
    seed = ((a_channel < 143) & (b_channel > 95) & (lightness > 20)).astype(
        np.uint8
    ) * 255
    seed = np.asarray(
        cv2.morphologyEx(seed, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    )
    seed = _largest_component(seed)
    height, width = seed.shape
    area_fraction = cv2.countNonZero(seed) / float(height * width)
    if area_fraction < 0.015:
        # GrabCut rectangle fallback supports leaves with little green tissue.
        gc_mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
        rect = (
            max(1, width // 20),
            max(1, height // 20),
            max(1, width * 9 // 10),
            max(1, height * 9 // 10),
        )
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(
                image,
                gc_mask,
                rect,
                bgd_model,
                fgd_model,
                iterations,
                cv2.GC_INIT_WITH_RECT,
            )
            leaf = np.where(
                (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0
            ).astype(np.uint8)
            leaf = _largest_component(leaf)
            confidence = 0.35
        except cv2.error:
            leaf, confidence = seed.astype(np.uint8), 0.15
    else:
        gc_mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
        expanded = cv2.dilate(seed, np.ones((19, 19), np.uint8))
        gc_mask[expanded > 0] = cv2.GC_PR_FGD
        sure_foreground = cv2.erode(seed, np.ones((7, 7), np.uint8))
        gc_mask[sure_foreground > 0] = cv2.GC_FGD
        border = max(1, min(height, width) // 100)
        gc_mask[:border] = cv2.GC_BGD
        gc_mask[-border:] = cv2.GC_BGD
        gc_mask[:, :border] = cv2.GC_BGD
        gc_mask[:, -border:] = cv2.GC_BGD
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(
                image,
                gc_mask,
                None,
                bgd_model,
                fgd_model,
                iterations,
                cv2.GC_INIT_WITH_MASK,
            )  # type: ignore[call-overload]
            leaf = np.where(
                (gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0
            ).astype(np.uint8)
            leaf = _largest_component(leaf)
            leaf_fraction = cv2.countNonZero(leaf) / float(height * width)
            confidence = 0.85 if 0.03 <= leaf_fraction <= 0.95 else 0.45
        except cv2.error:
            leaf, confidence = seed.astype(np.uint8), 0.35
    leaf = np.asarray(
        cv2.morphologyEx(leaf, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    )
    return leaf, confidence


def _remove_highlights_and_veins(lab: np.ndarray, leaf_mask: np.ndarray) -> np.ndarray:
    lightness, a_channel, b_channel = cv2.split(lab)
    chroma = cv2.absdiff(a_channel, np.full_like(a_channel, 128)) + cv2.absdiff(
        b_channel, np.full_like(b_channel, 128)
    )
    highlights = (lightness > 242) & (chroma < 34)
    kernel_size = max(9, (min(lab.shape[:2]) // 24) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    whitehat = cv2.morphologyEx(lightness, cv2.MORPH_TOPHAT, kernel)
    vein_like = (whitehat > 22) & (lightness > 120) & (a_channel < 145)
    return np.where((leaf_mask > 0) & ~highlights & ~vein_like, 255, 0).astype(np.uint8)


def _lab_lesion_probabilities(
    rgb: np.ndarray, leaf_mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    valid = _remove_highlights_and_veins(lab, leaf_mask) > 0
    lightness, a_channel, b_channel = cv2.split(lab)
    # Brown necrosis plus dark, locally anomalous tissue. Keep the rule conservative;
    # color-only output is explicitly marked as a lower-confidence fallback.
    brown = (a_channel > 137) & (b_channel > 130) & (lightness < 220)
    local_background = cv2.GaussianBlur(lightness, (0, 0), sigmaX=9)
    dark_spot = (
        local_background.astype(np.int16) - lightness.astype(np.int16) > 24
    ) & (a_channel > 128)
    lesion = np.where(valid & (brown | dark_spot), 255, 0).astype(np.uint8)
    lesion = np.asarray(
        cv2.morphologyEx(lesion, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    )
    # Sensitivity mask widens the color rule to estimate threshold uncertainty.
    relaxed_brown = (a_channel > 132) & (b_channel > 125) & (lightness < 230)
    relaxed = np.where(valid & (relaxed_brown | dark_spot), 255, 0).astype(np.uint8)
    return lesion, relaxed


def _model_lesion_mask(
    rgb: np.ndarray, leaf_mask: np.ndarray, model: Any
) -> np.ndarray:
    height, width = rgb.shape[:2]
    model_height, model_width = (int(x) for x in model.input_shape[1:3])
    resized = cv2.resize(rgb, (model_width, model_height)).astype(np.float32) / 255.0
    prediction = np.asarray(model.predict(resized[None, ...], verbose=0))[0]
    probability = prediction[..., 0] if prediction.ndim == 3 else prediction
    mask = cv2.resize(probability.astype(np.float32), (width, height)) >= 0.5
    valid = (
        _remove_highlights_and_veins(cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB), leaf_mask)
        > 0
    )
    return np.where(mask & valid, 255, 0).astype(np.uint8)


def _encode_png(image: np.ndarray) -> str:
    ok, raw = cv2.imencode(".png", image)
    return base64.b64encode(raw).decode("ascii") if ok else ""


def has_conflicting_signals(
    predicted_label: str, percent: float, category: str
) -> bool:
    """Flag materially inconsistent healthy/diseased classifier and lesion signals."""
    if category == "Not assessed" or predicted_label in {"Unknown", "Not_a_leaf"}:
        return False
    is_healthy = predicted_label.lower().endswith("healthy")
    return (is_healthy and percent > 10.0) or (not is_healthy and percent <= 10.0)


def estimate_severity(
    rgb: np.ndarray,
    crop: str | None = None,
    bands_path: Path | None = None,
    lesion_model: Any | None = None,
) -> dict[str, object]:
    """Estimate lesion area as a fraction of segmented leaf area, never image background."""
    leaf_mask, leaf_confidence = segment_leaf(rgb)
    leaf_area = int(cv2.countNonZero(leaf_mask))
    if leaf_area == 0:
        return {
            "percent": 0.0,
            "category": "Not assessed",
            "confidence": 0.0,
            "uncertainty_percent": 100.0,
            "method": "grabcut_failed",
            "lesion_mask_png_b64": _encode_png(np.zeros_like(leaf_mask)),
            "leaf_outline_png_b64": _encode_png(np.zeros_like(leaf_mask)),
        }
    if lesion_model is None:
        lesion_mask, relaxed_mask = _lab_lesion_probabilities(rgb, leaf_mask)
        method = "leaf_grabcut+lab_texture_fallback"
        model_confidence = 0.55
    else:
        lesion_mask = _model_lesion_mask(rgb, leaf_mask, lesion_model)
        relaxed_mask = lesion_mask
        method = "leaf_grabcut+lesion_unet"
        model_confidence = 0.85
    lesion_area = int(cv2.countNonZero(lesion_mask))
    percent = 100.0 * lesion_area / leaf_area
    relaxed_percent = 100.0 * cv2.countNonZero(relaxed_mask) / leaf_area
    uncertainty = abs(relaxed_percent - percent) + (1.0 - leaf_confidence) * 10.0
    confidence = max(
        0.0,
        min(
            1.0,
            leaf_confidence
            * model_confidence
            * (1.0 - min(uncertainty, 100.0) / 150.0),
        ),
    )
    config = load_severity_bands(str(bands_path or Path("data/kb/severity.json")))
    limits = config.get((crop or "").lower(), config["default"])
    if percent <= limits["mild_max"]:
        category = "Mild"
    elif percent <= limits["moderate_max"]:
        category = "Moderate"
    else:
        category = "Severe"
    outline = np.zeros_like(leaf_mask)
    contours, _ = cv2.findContours(
        leaf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    cv2.drawContours(outline, contours, -1, (255, 255, 255), 2)  # type: ignore[call-overload]
    return {
        "percent": round(float(percent), 2),
        "category": category,
        "confidence": round(float(confidence), 4),
        "uncertainty_percent": round(float(uncertainty), 2),
        "method": method,
        "conflicting_signals": False,
        "leaf_area_px": leaf_area,
        "lesion_area_px": lesion_area,
        "lesion_mask_png_b64": _encode_png(lesion_mask),
        "leaf_outline_png_b64": _encode_png(outline),
    }
