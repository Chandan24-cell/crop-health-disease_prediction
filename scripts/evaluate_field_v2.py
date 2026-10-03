"""Evaluate only on images declared field_test; this split is never read by training code."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from evaluate_v2 import OUT, ROOT, predict_paths
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from v2_metrics import apply_temperature, energy_score, expected_calibration_error

FIELD_MANIFEST = ROOT / "data/field_test_manifest.csv"
UNKNOWN = {"Unknown", "Not_a_leaf"}


def evaluate_field(model_path: Path) -> dict[str, object]:
    labels_path = model_path.parent / "labels.json"
    if not labels_path.exists():
        labels_path = ROOT / "models/class_names.json"
    class_names = json.loads(labels_path.read_text(encoding="utf-8"))
    calibration_path = ROOT / "reports/v2/lab_validation_calibration.json"
    calibration = json.loads(calibration_path.read_text(encoding="utf-8")) if calibration_path.exists() else None
    with FIELD_MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        result: dict[str, object] = {
            "status": "NOT MEASURED",
            "count": 0,
            "reason": "data/field_test_manifest.csv contains no verified field images",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "field_test_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (OUT / "field_test_report.md").write_text(
            "# Field test evaluation\n\n**NOT MEASURED:** no verified real field images have been registered.\n",
            encoding="utf-8",
        )
        return result
    unverified = [row for row in rows if row.get("label_verified", "no").lower() not in {"yes", "true", "1"}]
    if unverified:
        result = {
            "status": "NOT MEASURED",
            "count": len(rows),
            "unverified_count": len(unverified),
            "reason": "Field image labels require independent review before accuracy metrics are valid",
        }
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "field_test_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (OUT / "field_test_report.md").write_text(
            f"# Field test evaluation\n\n**NOT MEASURED:** {len(unverified)} of {len(rows)} labels are unverified.\n",
            encoding="utf-8",
        )
        return result
    unknown_labels = sorted({row["label"] for row in rows} - set(class_names))
    if unknown_labels:
        raise ValueError(f"Field labels not present in model labels: {unknown_labels}")
    label_map = {name: index for index, name in enumerate(class_names)}
    paths = [str(ROOT / row["path"]) for row in rows]
    y_true = np.array([label_map[row["label"]] for row in rows])
    model = tf.keras.models.load_model(model_path, compile=False)
    raw, latency, logits = predict_paths(model, paths)
    temperature = float(calibration["temperature"]) if calibration else 1.0
    probabilities = apply_temperature(raw, temperature)
    prediction = probabilities.argmax(axis=1)
    unknown_ids = [i for i, name in enumerate(class_names) if name in UNKNOWN]
    unknown_mask = np.isin(y_true, unknown_ids)
    threshold = float(calibration["energy_threshold"]) if calibration else None
    scores = energy_score(logits, temperature)
    result = {
        "status": "MEASURED",
        "count": len(rows),
        "accuracy": float(np.mean(prediction == y_true)),
        "macro_f1": float(f1_score(y_true, prediction, average="macro")),
        "ece": expected_calibration_error(probabilities, y_true),
        "wrong_crop_rate": float(
            np.mean(
                [
                    class_names[truth].split("_", 1)[0] != class_names[pred].split("_", 1)[0]
                    for truth, pred in zip(y_true, prediction, strict=True)
                    if class_names[truth].split("_", 1)[0] in {"Maize", "Tomato", "Potato"}
                    and class_names[pred].split("_", 1)[0] in {"Maize", "Tomato", "Potato"}
                ]
            )
        ),
        "ood_false_accept_rate": float(np.mean(scores[unknown_mask] <= threshold))
        if np.any(unknown_mask) and threshold is not None
        else None,
        "cpu_batch_latency_ms_per_image": latency,
        "per_class": classification_report(
            y_true,
            prediction,
            labels=np.arange(len(class_names)),
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(y_true, prediction, labels=np.arange(len(class_names))).tolist(),
        "source_counts": dict(__import__("collections").Counter(row.get("source_name", "unknown") for row in rows)),
        "field_test_manifest": "data/field_test_manifest.csv",
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "field_test_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    table = "\n".join(
        f"| {label} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1-score']:.3f} | {int(m['support'])} |"
        for label, m in result["per_class"].items()
        if label in class_names
    )
    (OUT / "field_test_report.md").write_text(
        f"# Field test evaluation\n\nImages: {len(rows)}\n\nMacro-F1: {result['macro_f1']:.4f}\n\n"
        "| Class | Precision | Recall | F1 | Support |\n|---|---:|---:|---:|---:|\n" + table + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models/crop_disease_model.keras")
    args = parser.parse_args()
    print(json.dumps(evaluate_field(args.model), indent=2))


if __name__ == "__main__":
    main()
