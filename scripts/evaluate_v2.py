"""Evaluate a model using the immutable v2 manifest; validation calibrates, test only measures."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import time
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import tensorflow as tf
from scipy.special import softmax
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    auc,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_curve,
)
from v2_metrics import (
    apply_temperature,
    calibrate_temperature,
    class_thresholds,
    energy_score,
    expected_calibration_error,
    ood_threshold,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/splits_v2.csv"
OUT = ROOT / "reports/v2"
MODEL_OUT = ROOT / "models/v2"
UNKNOWN_LABELS = {"Unknown", "Not_a_leaf"}
HARD_PAIRS = [
    ("Maize_Gray_leaf_spot", "Maize_Northern_Leaf_Blight"),
    ("Tomato_Early_blight", "Tomato_Late_blight"),
    ("Potato_Early_blight", "Potato_Late_blight"),
]


def load_manifest(
    split: str,
    class_order: list[str] | None = None,
    original_source_split: str | None = None,
) -> tuple[list[str], np.ndarray, list[str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        all_rows = list(csv.DictReader(stream))
    rows = [row for row in all_rows if row["split"] == split]
    if original_source_split is not None:
        original_train_groups = {row["group_id"] for row in all_rows if Path(row["path"]).parts[2] == "train"}
        rows = [
            row
            for row in all_rows
            if Path(row["path"]).parts[2] == original_source_split and row["group_id"] not in original_train_groups
        ]
    classes = class_order or sorted({row["label"] for row in rows})
    unknown = sorted({row["label"] for row in rows} - set(classes))
    if unknown:
        raise ValueError(f"Manifest has classes missing from labels.json: {unknown}")
    class_to_index = {label: index for index, label in enumerate(classes)}
    return (
        [str(ROOT / row["path"]) for row in rows],
        np.array([class_to_index[row["label"]] for row in rows]),
        classes,
    )


def predict_paths(
    model: tf.keras.Model, paths: list[str], batch_size: int = 32
) -> tuple[np.ndarray, float, np.ndarray]:
    dataset = tf.data.Dataset.from_tensor_slices(paths)

    def read_image(path: tf.Tensor) -> tf.Tensor:
        image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        return tf.image.resize(image, [224, 224])

    dataset = dataset.map(read_image, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(tf.data.AUTOTUNE)
    last_layer = model.layers[-1]
    dense_softmax = (
        isinstance(last_layer, tf.keras.layers.Dense) and getattr(last_layer.activation, "__name__", "") == "softmax"
    )
    features_model = tf.keras.Model(model.inputs, last_layer.input) if dense_softmax else None
    start = time.perf_counter()
    outputs: list[np.ndarray] = []
    logits_outputs: list[np.ndarray] = []
    for batch in dataset:
        if features_model is not None:
            features = features_model(batch, training=False)
            logits = tf.linalg.matmul(features, last_layer.kernel)
            if last_layer.use_bias:
                logits = tf.nn.bias_add(logits, last_layer.bias)
            batch_logits = np.asarray(logits)
            logits_outputs.append(batch_logits)
            outputs.append(softmax(batch_logits, axis=1))
        else:
            probs = np.asarray(model(batch, training=False))
            outputs.append(probs)
            logits_outputs.append(np.log(np.clip(probs, 1e-9, 1.0)))
    elapsed = (time.perf_counter() - start) * 1000 / max(len(paths), 1)
    return np.concatenate(outputs), elapsed, np.concatenate(logits_outputs)


def benchmark_single_image(model: tf.keras.Model, paths: list[str], sample_count: int = 64) -> float:
    sample = paths[: min(len(paths), sample_count)]
    images = []
    for path in sample:
        image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        images.append(tf.image.resize(image, [224, 224]).numpy())
    batch = np.asarray(images)
    model(batch[:1], training=False)  # warm-up
    start = time.perf_counter()
    for image in batch:
        model(image[None, ...], training=False)
    return (time.perf_counter() - start) * 1000 / max(len(batch), 1)


def tta_predict(model: tf.keras.Model, paths: list[str], batch_size: int = 16) -> tuple[np.ndarray, float]:
    """Four views: original, mirrored, and two opposing crops."""
    outputs: list[np.ndarray] = []
    start = time.perf_counter()
    for offset in range(0, len(paths), batch_size):
        batch_paths = paths[offset : offset + batch_size]
        images = []
        for path in batch_paths:
            raw = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
            raw = tf.image.resize(raw, [256, 256]).numpy()
            views = [raw[16:240, 16:240], np.fliplr(raw[16:240, 16:240]), raw[:224, :224], raw[32:, 32:]]
            images.extend([tf.image.resize(view, [224, 224]).numpy() for view in views])
        prediction = np.asarray(model(np.asarray(images), training=False))
        outputs.append(prediction.reshape(len(batch_paths), 4, -1).mean(axis=1))
    elapsed = (time.perf_counter() - start) * 1000 / max(len(paths), 1)
    return np.concatenate(outputs), elapsed


def _plot_confusion(y_true: np.ndarray, y_pred: np.ndarray, classes: list[str], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(13, 11))
    ConfusionMatrixDisplay(confusion_matrix(y_true, y_pred), display_labels=classes).plot(
        ax=ax, xticks_rotation=90, colorbar=False, values_format="d"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _calibration_plot(probs: np.ndarray, labels: np.ndarray, path: Path) -> None:
    confidence = probs.max(axis=1)
    correct = probs.argmax(axis=1) == labels
    bins = np.linspace(0, 1, 16)
    xs, ys = [], []
    for low, high in zip(bins[:-1], bins[1:], strict=True):
        mask = (confidence >= low) & (confidence < high)
        if np.any(mask):
            xs.append(float(confidence[mask].mean()))
            ys.append(float(correct[mask].mean()))
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="Perfect calibration")
    ax.plot(xs, ys, "o-", label="Model")
    ax.set(xlabel="Mean confidence", ylabel="Accuracy", title="Reliability diagram", xlim=(0, 1), ylim=(0, 1))
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _reject_plots(
    logits: np.ndarray, labels: np.ndarray, classes: list[str], prefix: str, temperature: float
) -> dict[str, float]:
    unknown_indices = [i for i, label in enumerate(classes) if label in UNKNOWN_LABELS]
    is_unknown = np.isin(labels, unknown_indices).astype(np.uint8)
    scores = energy_score(logits, temperature)
    fpr, tpr, _ = roc_curve(is_unknown, scores)
    precision, recall, _ = precision_recall_curve(is_unknown, scores)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].plot(fpr, tpr, label=f"AUROC={auc(fpr, tpr):.3f}")
    axes[0].plot([0, 1], [0, 1], "--", color="gray")
    axes[0].set(title="Unknown / not-a-leaf ROC", xlabel="False positive rate", ylabel="True positive rate")
    axes[0].legend()
    axes[1].plot(recall, precision)
    axes[1].set(title="Unknown / not-a-leaf PR", xlabel="Recall", ylabel="Precision")
    fig.tight_layout()
    fig.savefig(OUT / f"{prefix}_reject_curves.png", dpi=160)
    plt.close(fig)
    return {"auroc": float(auc(fpr, tpr))}


def calibrate_validation(
    model: tf.keras.Model,
    class_names: list[str],
    calibration_path: Path,
    original_source_split: str | None = None,
) -> dict[str, object]:
    paths, labels, actual_classes = load_manifest("val", class_names, original_source_split)
    if actual_classes != class_names:
        raise ValueError("Manifest labels and model labels differ. Align labels before calibration.")
    probs, latency, logits = predict_paths(model, paths)
    temperature = calibrate_temperature(probs, labels)
    calibrated = apply_temperature(probs, temperature)
    known_labels = [label for label in class_names if label not in UNKNOWN_LABELS]
    unknown_ids = [i for i, label in enumerate(class_names) if label in UNKNOWN_LABELS]
    energy_cutoff = ood_threshold(logits, labels, class_names, temperature=temperature)
    calibration = {
        "temperature": temperature,
        "class_thresholds": class_thresholds(calibrated, labels, class_names),
        "energy_threshold": energy_cutoff,
        "ood_score": "negative log-sum-exp energy of pre-softmax logits",
        "validation_ece": expected_calibration_error(calibrated, labels),
        "validation_latency_ms_per_image": latency,
        "validation_unknown_count": int(np.isin(labels, unknown_ids).sum()),
        "known_classes": known_labels,
        "manifest": "data/splits_v2.csv",
    }
    calibration_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_path.write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    _calibration_plot(calibrated, labels, OUT / "lab_validation_reliability.png")
    return calibration


def evaluate_model(model_path: Path, split: str = "test", use_tta: bool = True) -> dict[str, object]:
    OUT.mkdir(parents=True, exist_ok=True)
    model = tf.keras.models.load_model(model_path, compile=False)
    labels_path = model_path.parent / "labels.json"
    if not labels_path.exists():
        labels_path = ROOT / "models/class_names.json"
    class_names = json.loads(labels_path.read_text(encoding="utf-8"))
    deployed_model = model_path.resolve().is_relative_to(MODEL_OUT.resolve())
    calibration_path = (
        model_path.parent / "calibration.json" if deployed_model else OUT / "lab_validation_calibration.json"
    )
    if split == "test" and calibration_path.exists():
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    else:
        calibration = calibrate_validation(
            model,
            class_names,
            calibration_path,
            original_source_split="val" if not deployed_model else None,
        )
    paths, labels, actual_classes = load_manifest(
        split, class_names, original_source_split="test" if not deployed_model else None
    )
    if actual_classes != class_names:
        raise ValueError("Manifest labels and model labels differ.")
    raw, latency, logits = predict_paths(model, paths)
    probabilities = apply_temperature(raw, float(calibration["temperature"]))
    y_pred = probabilities.argmax(axis=1)
    cm = confusion_matrix(labels, y_pred, labels=np.arange(len(class_names)))
    _plot_confusion(labels, y_pred, class_names, OUT / f"lab_{split}_confusion.png")
    _calibration_plot(probabilities, labels, OUT / f"lab_{split}_reliability.png")
    temperature = float(calibration["temperature"])
    reject = _reject_plots(logits, labels, class_names, f"lab_{split}", temperature)
    wrong_crop = []
    for true_idx, pred_idx in zip(labels, y_pred, strict=True):
        true_crop = class_names[true_idx].split("_", 1)[0]
        pred_crop = class_names[pred_idx].split("_", 1)[0]
        if true_crop in {"Maize", "Tomato", "Potato"} and pred_crop in {"Maize", "Tomato", "Potato"}:
            wrong_crop.append(true_crop != pred_crop)
    report = classification_report(
        labels, y_pred, labels=np.arange(len(class_names)), target_names=class_names, output_dict=True, zero_division=0
    )
    gallery_root = OUT / "error_gallery" / split
    if gallery_root.exists():
        shutil.rmtree(gallery_root)
    gallery_root.mkdir(parents=True, exist_ok=True)
    errors: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for path, true_idx, pred_idx, row in zip(paths, labels, y_pred, probabilities, strict=True):
        if true_idx != pred_idx:
            errors[(class_names[true_idx], class_names[pred_idx])].append((float(row[pred_idx]), path))
    gallery_rows = []
    for (truth, prediction), examples in errors.items():
        examples.sort(reverse=True)
        pair_folder = gallery_root / f"{truth}__as__{prediction}"
        pair_folder.mkdir(parents=True, exist_ok=True)
        for confidence, source in examples[:20]:
            target = pair_folder / Path(source).name
            shutil.copy2(source, target)
            gallery_rows.append((truth, prediction, confidence, target.relative_to(ROOT).as_posix()))
    gallery_table = "\n".join(
        f"| {truth} | {pred} | {conf:.3f} | [{Path(path).name}]({path.replace('reports/v2/', '')}) |"
        for truth, pred, conf, path in gallery_rows
    )
    pair_stats = {
        f"{left} ↔ {right}": int(
            cm[class_names.index(left), class_names.index(right)]
            + cm[class_names.index(right), class_names.index(left)]
        )
        for left, right in HARD_PAIRS
        if left in class_names and right in class_names
    }
    threshold = float(calibration["energy_threshold"])
    unknown_ids = [i for i, name in enumerate(class_names) if name in UNKNOWN_LABELS]
    unknown_mask = np.isin(labels, unknown_ids)
    scores = energy_score(logits, temperature)
    ood_far = float(np.mean(scores[unknown_mask] <= threshold)) if np.any(unknown_mask) else None
    known_mask = ~unknown_mask
    ood_frr = float(np.mean(scores[known_mask] > threshold)) if np.any(known_mask) else None
    result = {
        "split": split,
        "count": len(labels),
        "accuracy": float(np.mean(y_pred == labels)),
        "macro_f1": float(f1_score(labels, y_pred, average="macro")),
        "ece": expected_calibration_error(probabilities, labels),
        "latency_ms_per_image_batch": latency,
        "cpu_single_image_latency_ms_sampled": benchmark_single_image(model, paths),
        "wrong_crop_rate": float(np.mean(wrong_crop)) if wrong_crop else None,
        "ood_false_accept_rate": ood_far,
        "ood_known_false_reject_rate": ood_frr,
        "unknown_auroc": reject["auroc"],
        "per_class": report,
        "confusion_matrix": cm.tolist(),
        "hard_negative_pairs": pair_stats,
        "tta_latency_ms_per_image": None,
        "tta_macro_f1": None,
        "calibration": calibration,
    }
    if use_tta:
        tta_probs, tta_latency = tta_predict(model, paths)
        tta_probs = apply_temperature(tta_probs, float(calibration["temperature"]))
        result["tta_latency_ms_per_image"] = tta_latency
        result["tta_macro_f1"] = float(f1_score(labels, tta_probs.argmax(axis=1), average="macro"))
    (OUT / f"lab_{split}_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = [
        f"# v2 Lab Evaluation — {split}",
        "",
        f"Images: {len(labels)}",
        f"Macro-F1: {result['macro_f1']:.4f}",
        f"ECE: {result['ece']:.4f}",
        f"Latency: {result['cpu_single_image_latency_ms_sampled']:.2f} ms/image "
        "(single-image CPU, first 64 test images)",
        f"Wrong-crop rate: {result['wrong_crop_rate']}",
        f"Unknown false-accept rate: {ood_far}",
        f"Unknown AUROC: {reject['auroc']:.4f}",
        "",
        "## Per-class precision / recall / F1",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in class_names:
        metric = report[name]
        lines.append(
            f"| {name} | {metric['precision']:.3f} | {metric['recall']:.3f} "
            f"| {metric['f1-score']:.3f} | {int(metric['support'])} |"
        )
    lines.extend(["", "## Hard confusion pairs", "", "| Pair | Errors |", "|---|---:|"])
    lines.extend(f"| {pair} | {count} |" for pair, count in pair_stats.items())
    lines.extend(
        [
            "",
            "Figures: confusion matrix, reliability diagram, and unknown ROC/PR are in `reports/v2/`.",
            "",
            "## Error gallery",
            "",
            "| True | Predicted | Confidence | Image |",
            "|---|---|---:|---|",
        ]
    )
    lines.append(gallery_table or "| — | — | — | No errors |")
    (OUT / f"lab_{split}_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models/crop_disease_model.keras")
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--no-tta", action="store_true")
    args = parser.parse_args()
    print(json.dumps(evaluate_model(args.model, args.split, not args.no_tta), indent=2))


if __name__ == "__main__":
    main()
