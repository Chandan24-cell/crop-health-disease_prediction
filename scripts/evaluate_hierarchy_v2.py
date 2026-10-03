"""Evaluate the promoted crop-first v2 hierarchy on grouped lab or reviewed field holdout."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from inference_v2 import HierarchicalPredictor
from sklearn.metrics import ConfusionMatrixDisplay, classification_report, confusion_matrix, f1_score
from v2_metrics import expected_calibration_error

ROOT = Path(__file__).resolve().parents[1]
HIERARCHY = ROOT / "models/v2/hierarchy"
LAB_MANIFEST = ROOT / "data/splits_v2.csv"
FIELD_MANIFEST = ROOT / "data/field_test_manifest.csv"
OUT = ROOT / "reports/v2"


def _load_records(split: str, field: bool) -> list[dict[str, str]]:
    manifest = FIELD_MANIFEST if field else LAB_MANIFEST
    with manifest.open(encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    if field:
        unverified = sum(row.get("label_verified", "no").lower() not in {"yes", "true", "1"} for row in records)
        if unverified:
            raise ValueError(f"Field accuracy not measured: {unverified}/{len(records)} labels are unverified")
        return records
    return [row for row in records if row["split"] == split]


def evaluate(split: str = "test", use_tta: bool = True, field: bool = False) -> dict[str, object]:
    records = _load_records(split, field)
    class_names = json.loads((ROOT / "models/class_names.json").read_text(encoding="utf-8"))
    class_ids = {label: index for index, label in enumerate(class_names)}
    missing = sorted({row["label"] for row in records} - set(class_ids))
    if missing:
        raise ValueError(f"Evaluation labels missing in model taxonomy: {missing}")
    predictor = HierarchicalPredictor(HIERARCHY, use_tta=use_tta)
    predictor.load()
    y_true: list[int] = []
    y_pred: list[int] = []
    confidences: list[float] = []
    latencies: list[float] = []
    accepted_calls: list[bool] = []
    rejections = defaultdict(int)
    errors: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for row in records:
        image_path = ROOT / row["path"]
        import cv2

        bgr = cv2.imread(str(image_path))
        if bgr is None:
            continue
        result = predictor.predict(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        true_label = row["label"]
        if result["status"] == "ok":
            predicted_label = str(result["top3"][0]["label"])
        else:
            predicted_label = "Not_a_leaf" if result["top3"][0]["label"] == "Not_a_leaf" else "Unknown"
            rejections[str(result["status"])] += 1
        if predicted_label not in class_ids:
            predicted_label = "Unknown"
        true_id, pred_id = class_ids[true_label], class_ids[predicted_label]
        confidence = float(result["calibrated_confidence"])
        y_true.append(true_id)
        y_pred.append(pred_id)
        confidences.append(confidence)
        latencies.append(float(result["latency_ms"]))
        accepted_calls.append(result["status"] == "ok")
        if true_id != pred_id:
            errors[(true_label, predicted_label)].append((confidence, str(row["path"])))

    truth = np.asarray(y_true)
    prediction = np.asarray(y_pred)
    confidence_array = np.asarray(confidences)
    cm = confusion_matrix(truth, prediction, labels=np.arange(len(class_names)))
    per_class = classification_report(
        truth,
        prediction,
        labels=np.arange(len(class_names)),
        target_names=class_names,
        output_dict=True,
        zero_division=0,
    )
    # Calibration is reported on accepted disease calls, where the returned score is a joint calibrated probability.
    accepted = np.asarray(accepted_calls, dtype=bool)
    ece = (
        expected_calibration_error(
            np.eye(len(class_names))[prediction[accepted]] * confidence_array[accepted, None]
            + (1.0 - confidence_array[accepted, None]) / len(class_names),
            truth[accepted],
        )
        if np.any(accepted)
        else None
    )
    report_key = "field" if field else split
    gallery_root = OUT / "hierarchy_error_gallery" / report_key
    if gallery_root.exists():
        shutil.rmtree(gallery_root)
    gallery_root.mkdir(parents=True, exist_ok=True)
    gallery_rows: list[tuple[str, str, float, str]] = []
    for (true_name, pred_name), mistakes in errors.items():
        mistakes.sort(reverse=True)
        pair_dir = gallery_root / f"{true_name}__as__{pred_name}"
        pair_dir.mkdir(parents=True, exist_ok=True)
        for score, source in mistakes[:20]:
            image_source = ROOT / source
            target = pair_dir / image_source.name
            shutil.copy2(image_source, target)
            gallery_rows.append((true_name, pred_name, score, target.relative_to(OUT).as_posix()))
    confusion_fig, ax = plt.subplots(figsize=(13, 11))
    ConfusionMatrixDisplay(cm, display_labels=class_names).plot(ax=ax, xticks_rotation=90, colorbar=False)
    confusion_fig.tight_layout()
    confusion_fig.savefig(OUT / f"hierarchy_{report_key}_confusion.png", dpi=160)
    plt.close(confusion_fig)
    macro_f1 = float(f1_score(truth, prediction, average="macro")) if len(truth) else 0.0
    result: dict[str, object] = {
        "status": "MEASURED" if records else "NOT MEASURED",
        "split": report_key,
        "count": len(truth),
        "accuracy": float(np.mean(truth == prediction)) if len(truth) else 0.0,
        "macro_f1": macro_f1,
        "ece_accepted_calls": ece,
        "accepted_coverage": float(np.mean(accepted)) if len(accepted) else 0.0,
        "wrong_crop_rate": float(
            np.mean(
                [
                    class_names[truth[index]].split("_", 1)[0] != class_names[prediction[index]].split("_", 1)[0]
                    for index in range(len(truth))
                    if accepted[index]
                    and class_names[truth[index]].split("_", 1)[0] in {"Maize", "Potato", "Tomato"}
                    and class_names[prediction[index]].split("_", 1)[0] in {"Maize", "Potato", "Tomato"}
                ]
            )
        )
        if np.any(accepted)
        else None,
        "latency_ms_mean": float(np.mean(latencies)) if latencies else None,
        "rejections": dict(rejections),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "tta": use_tta,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"hierarchy_{report_key}_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    table = "\n".join(
        f"| {name} | {metric['precision']:.3f} | {metric['recall']:.3f} "
        f"| {metric['f1-score']:.3f} | {int(metric['support'])} |"
        for name, metric in per_class.items()
        if name in class_names
    )
    gallery = "\n".join(
        f"| {truth_name} | {pred_name} | {score:.3f} | [{Path(path).name}]({path}) |"
        for truth_name, pred_name, score, path in gallery_rows
    )
    (OUT / f"hierarchy_{report_key}_report.md").write_text(
        f"# Hierarchical v2 evaluation: {report_key}\n\n"
        f"Images: {len(truth)}\n\nMacro-F1: {macro_f1:.4f}\n\n"
        f"Accepted coverage: {result['accepted_coverage']:.2%}\n\n"
        f"Selective ECE: {ece}\n\nMean latency: {result['latency_ms_mean']} ms/image\n\n"
        "| Class | Precision | Recall | F1 | Support |\n|---|---:|---:|---:|---:|\n"
        f"{table}\n\n![Confusion matrix](hierarchy_{report_key}_confusion.png)\n\n"
        "## Error gallery\n\n| True | Predicted | Confidence | Image |\n|---|---|---:|---|\n"
        f"{gallery or '| — | — | — | No errors |'}\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--field", action="store_true")
    parser.add_argument("--no-tta", action="store_true")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.split, not args.no_tta, args.field), indent=2))


if __name__ == "__main__":
    main()
