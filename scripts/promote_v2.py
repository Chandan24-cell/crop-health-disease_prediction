"""Promote best-seed hierarchical candidates by architecture mean validation macro-F1."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf
from train_v2 import ROOT, RUNS, STAGES, get_rows
from v2_metrics import (
    apply_temperature,
    calibrate_temperature,
    class_thresholds,
    expected_calibration_error,
    ood_threshold,
)

DEST = ROOT / "models/v2/hierarchy"
VERSION_DIR = ROOT / "models/v2"


def _probabilities(model: tf.keras.Model, paths: list[str]) -> np.ndarray:
    dataset = tf.data.Dataset.from_tensor_slices(paths)

    def load(path: tf.Tensor) -> tf.Tensor:
        image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        return tf.image.resize(image, [224, 224])

    dataset = dataset.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(32)
    return np.concatenate([np.asarray(model(batch, training=False)) for batch in dataset])


def _logits(model: tf.keras.Model, paths: list[str]) -> np.ndarray:
    layer = model.layers[-1]
    if not isinstance(layer, tf.keras.layers.Dense) or getattr(layer.activation, "__name__", "") != "softmax":
        return np.log(np.clip(_probabilities(model, paths), 1e-9, 1.0))
    features_model = tf.keras.Model(model.inputs, layer.input)
    dataset = tf.data.Dataset.from_tensor_slices(paths)

    def load(path: tf.Tensor) -> tf.Tensor:
        image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        return tf.image.resize(image, [224, 224])

    dataset = dataset.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(32)
    results = []
    for batch in dataset:
        features = features_model(batch, training=False)
        logits = tf.linalg.matmul(features, layer.kernel)
        if layer.use_bias:
            logits = tf.nn.bias_add(logits, layer.bias)
        results.append(np.asarray(logits))
    return np.concatenate(results)


def _temperature_scaled_stage(
    model_path: Path, temperature: float, inputs: tf.keras.KerasTensor, name: str
) -> tf.Tensor:
    stage_model = tf.keras.models.load_model(model_path, compile=False)
    final_layer = stage_model.layers[-1]
    has_softmax_head = (
        isinstance(final_layer, tf.keras.layers.Dense)
        and getattr(final_layer.activation, "__name__", "") == "softmax"
    )
    if not has_softmax_head:
        raise ValueError(f"{model_path} must end with a Dense softmax head")
    feature_model = tf.keras.Model(stage_model.inputs, final_layer.input)
    features = feature_model(inputs, training=False)
    scaled_head = tf.keras.layers.Dense(
        final_layer.units,
        activation="softmax",
        dtype="float32",
        name=name,
    )
    probabilities = scaled_head(features)
    weights = final_layer.get_weights()
    scaled_weights = [weights[0] / temperature]
    if final_layer.use_bias:
        scaled_weights.append(weights[1] / temperature)
    scaled_head.set_weights(scaled_weights)
    return probabilities


def _build_flat_registry_model(stage_data: dict[str, dict[str, object]]) -> None:
    """Bake stage temperatures into Dense heads and export a flat calibrated model for API loading."""
    input_tensor = tf.keras.Input((224, 224, 3), name="image")
    crop_labels = json.loads((DEST / "stage_a/labels.json").read_text(encoding="utf-8"))
    crop_temperature = float(json.loads((DEST / "stage_a/calibration.json").read_text(encoding="utf-8"))["temperature"])
    stage_probs: dict[str, tf.Tensor] = {
        "crop": _temperature_scaled_stage(
            DEST / "stage_a/model.keras", crop_temperature, input_tensor, "crop_calibrated_softmax"
        )
    }
    stage_labels: dict[str, list[str]] = {"crop": crop_labels}
    for crop in ("maize", "tomato", "potato"):
        folder = DEST / f"disease_{crop}"
        calibration = json.loads((folder / "calibration.json").read_text(encoding="utf-8"))
        stage_probs[crop] = _temperature_scaled_stage(
            folder / "model.keras", float(calibration["temperature"]), input_tensor,
            f"{crop}_calibrated_softmax",
        )
        stage_labels[crop] = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
    global_labels = json.loads((ROOT / "models/class_names.json").read_text(encoding="utf-8"))
    crop_index = {label: index for index, label in enumerate(crop_labels)}
    concat_values: list[tf.Tensor] = []
    for label in global_labels:
        if label == "Unknown":
            stage, index = "crop", crop_index["Other"]
        elif label == "Not_a_leaf":
            stage, index = "crop", crop_index["Not_a_leaf"]
        else:
            crop = label.split("_", 1)[0].lower()
            stage = crop
            index = stage_labels[crop].index(label)
            crop_selector = tf.keras.layers.Dense(
                1,
                use_bias=False,
                trainable=False,
                name=f"{crop}_gate_{len(concat_values)}",
            )
            crop_probability = crop_selector(stage_probs["crop"])
            crop_weights = np.zeros((len(crop_labels), 1), dtype=np.float32)
            crop_weights[crop_index[label.split("_", 1)[0]], 0] = 1.0
            crop_selector.set_weights([crop_weights])
            disease_selector = tf.keras.layers.Dense(
                1,
                use_bias=False,
                trainable=False,
                name=f"{crop}_class_{len(concat_values)}",
            )
            conditional_probability = disease_selector(stage_probs[stage])
            disease_weights = np.zeros((len(stage_labels[stage]), 1), dtype=np.float32)
            disease_weights[index, 0] = 1.0
            disease_selector.set_weights([disease_weights])
            concat_values.append(tf.keras.layers.Multiply(name=f"joint_{len(concat_values)}")(
                [crop_probability, conditional_probability]
            ))
            continue
        selector = tf.keras.layers.Dense(1, use_bias=False, trainable=False, name=f"reject_{label.lower()}")
        value = selector(stage_probs[stage])
        weights = np.zeros((len(stage_labels[stage]), 1), dtype=np.float32)
        weights[index, 0] = 1.0
        selector.set_weights([weights])
        concat_values.append(value)
    output = tf.keras.layers.Concatenate(name="calibrated_disease_probabilities")(concat_values)
    composite = tf.keras.Model(input_tensor, output, name="CropHealthHierarchicalV2")
    VERSION_DIR.mkdir(parents=True, exist_ok=True)
    composite.save(VERSION_DIR / "model.keras")
    (VERSION_DIR / "labels.json").write_text(json.dumps(global_labels, indent=2), encoding="utf-8")
    (VERSION_DIR / "calibration.json").write_text(json.dumps({"temperature": 1.0}, indent=2), encoding="utf-8")
    metadata = {
        "version": "v2",
        "architecture": "crop-first hierarchical softmax composition",
        "probabilities": (
            "stage temperatures are baked into the stage heads; disease probabilities are "
            "crop_probability * conditional_disease_probability"
        ),
        "hierarchy_artifacts": "hierarchy/metadata.json",
        "stages": stage_data,
        "manifest": "data/splits_v2.csv",
    }
    (VERSION_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def promote(minimum_seeds: int = 3) -> dict[str, dict[str, object]]:
    scores: dict[str, dict[str, list[tuple[float, Path]]]] = defaultdict(lambda: defaultdict(list))
    for metric_path in RUNS.glob("*/*/seed_*/metrics.json"):
        metric = json.loads(metric_path.read_text(encoding="utf-8"))
        scores[metric["stage"]][metric["architecture"]].append((float(metric["val_macro_f1"]), metric_path.parent))
    if set(scores) != set(STAGES):
        raise RuntimeError(f"All hierarchy stages need candidates; found {sorted(scores)}")
    result: dict[str, dict[str, object]] = {}
    for stage in STAGES:
        ranked = sorted(
            (
                (float(np.mean([score for score, _ in runs])), architecture, runs)
                for architecture, runs in scores[stage].items()
                if len(runs) >= minimum_seeds
            ),
            reverse=True,
        )
        if not ranked:
            raise RuntimeError(f"{stage}: no architecture has {minimum_seeds} seed runs")
        mean_score, architecture, runs = ranked[0]
        seed_score, candidate = max(runs, key=lambda item: item[0])
        folder_name = "stage_a" if stage == "crop" else f"disease_{stage}"
        destination = DEST / folder_name
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(candidate / "model.keras", destination / "model.keras")
        labels = json.loads((candidate / "labels.json").read_text(encoding="utf-8"))
        (destination / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
        paths, target_ids, _ = get_rows("val", stage)
        selected_model = tf.keras.models.load_model(destination / "model.keras", compile=False)
        probs = _probabilities(selected_model, paths)
        logits = _logits(selected_model, paths)
        target_array = np.asarray(target_ids)
        temperature = calibrate_temperature(probs, target_array)
        calibrated = apply_temperature(probs, temperature)
        calibration = {
            "temperature": temperature,
            "class_thresholds": class_thresholds(calibrated, target_array, labels, minimum_precision=0.95),
            "validation_ece": expected_calibration_error(calibrated, target_array),
            "calibration_split": "val",
            "manifest": "data/splits_v2.csv",
        }
        if stage == "crop":
            energy_cutoff = ood_threshold(logits, target_array, labels, temperature=temperature)
            calibration["energy_threshold"] = energy_cutoff
            calibration["ood_score"] = "negative log-sum-exp energy of pre-softmax logits"
        (destination / "calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
        result[stage] = {
            "architecture": architecture,
            "architecture_mean_val_macro_f1": mean_score,
            "selected_seed": candidate.name,
            "selected_seed_val_macro_f1": seed_score,
            "seeds_for_architecture": len(runs),
            "artifact": str((destination / "model.keras").relative_to(ROOT)),
        }
    metadata = {
        "version": "v2-hierarchical",
        "stage_a": "stage_a",
        "stage_b": ["disease_maize", "disease_tomato", "disease_potato"],
        "selection": "highest mean validation macro-F1 across architecture seeds; best seed selected for artifact",
        "manifest": "data/splits_v2.csv",
        "stages": result,
    }
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    _build_flat_registry_model(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minimum-seeds", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(promote(args.minimum_seeds), indent=2))


if __name__ == "__main__":
    main()
