"""Evaluate lesion masks and severity against a corrected, held-out annotation manifest."""

from __future__ import annotations

import argparse
import base64
import csv
import io
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.severity import estimate_severity  # noqa: E402


def _read_gray(path: str) -> np.ndarray:
    value = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if value is None:
        raise ValueError(f"Cannot read annotation mask: {path}")
    return value


def evaluate(annotations: Path, report: Path, model_path: Path | None = None) -> dict[str, object]:
    rows: list[dict[str, str]] = []
    if annotations.exists():
        with annotations.open(encoding="utf-8", newline="") as stream:
            rows = [
                row for row in csv.DictReader(stream)
                if row.get("split") == "test" and row.get("review_status") in {"corrected", "verified"}
            ]
    else:
        rows = []
    rows = [
        row for row in rows if row.get("image_path") and row.get("leaf_mask_path") and row.get("lesion_mask_path")
    ]
    if len(rows) < 100:
        result: dict[str, object] = {"status": "NOT MEASURED", "annotated_test_images": len(rows), "required": 100}
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            "# Severity segmentation evaluation\n\n"
            f"**NOT MEASURED:** {len(rows)}/100 corrected, held-out test images are available.\n\n"
            "No IoU, Dice, or severity MAE is reported until 100 manually corrected test masks are supplied. "
            "Pseudo-labels are not ground truth and are excluded.\n",
            encoding="utf-8",
        )
        return result
    model = None
    if model_path is not None and model_path.exists():
        import tensorflow as tf

        model = tf.keras.models.load_model(model_path, compile=False)
    ious: list[float] = []
    dices: list[float] = []
    absolute_errors: list[float] = []
    for row in rows:
        bgr = cv2.imread(row["image_path"])
        if bgr is None:
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        leaf_gt = _read_gray(row["leaf_mask_path"]) > 0
        lesion_gt = _read_gray(row["lesion_mask_path"]) > 0
        lesion_gt &= leaf_gt
        result = estimate_severity(rgb, lesion_model=model)
        raw = base64.b64decode(str(result["lesion_mask_png_b64"]))
        lesion_pred = np.asarray(Image.open(io.BytesIO(raw)).convert("L")) > 0
        if lesion_pred.shape != lesion_gt.shape:
            lesion_pred = cv2.resize(lesion_pred.astype(np.uint8), (lesion_gt.shape[1], lesion_gt.shape[0])) > 0
        lesion_pred &= leaf_gt
        intersection = int(np.count_nonzero(lesion_pred & lesion_gt))
        union = int(np.count_nonzero(lesion_pred | lesion_gt))
        predicted_area, actual_area = int(lesion_pred.sum()), int(lesion_gt.sum())
        ious.append(intersection / union if union else 1.0)
        dices.append(2 * intersection / (predicted_area + actual_area) if predicted_area + actual_area else 1.0)
        actual_percent = 100.0 * actual_area / max(1, int(leaf_gt.sum()))
        absolute_errors.append(abs(float(result["percent"]) - actual_percent))
    if len(ious) < 100:
        metrics: dict[str, object] = {"status": "NOT MEASURED", "evaluated_test_images": len(ious), "required": 100}
    else:
        metrics = {
            "status": "MEASURED",
            "evaluated_test_images": len(ious),
            "lesion_iou_mean": float(np.mean(ious)),
            "lesion_dice_mean": float(np.mean(dices)),
            "severity_mae_percentage_points": float(np.mean(absolute_errors)),
        }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Severity segmentation evaluation\n\n"
        + "\n".join(f"- **{name}:** {value}" for name, value in metrics.items())
        + "\n\nMetrics use corrected test annotations only; pseudo-labels are excluded.\n",
        encoding="utf-8",
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=Path("data/severity/annotations.csv"))
    parser.add_argument("--model", type=Path, default=Path("models/severity/lesion_unet.keras"))
    parser.add_argument("--report", type=Path, default=Path("reports/severity.md"))
    args = parser.parse_args()
    model_path = args.model if args.model.exists() else None
    print(evaluate(args.annotations, args.report, model_path))


if __name__ == "__main__":
    main()
