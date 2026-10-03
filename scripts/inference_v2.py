"""Inference helpers for four-model crop-first hierarchical v2 checkpoints."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import tensorflow as tf


def calibrate(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-9, 1.0)) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def _views(rgb: np.ndarray) -> np.ndarray:
    base = tf.image.resize(rgb, [256, 256]).numpy()
    crops = [base[16:240, 16:240], np.fliplr(base[16:240, 16:240]), base[:224, :224], base[32:, 32:]]
    return np.asarray([tf.image.resize(image, [224, 224]).numpy() for image in crops])


class HierarchicalPredictor:
    def __init__(self, root: Path, use_tta: bool = True) -> None:
        self.root = root
        self.use_tta = use_tta
        self.models: dict[str, Any] = {}
        self.feature_models: dict[str, Any | None] = {}
        self.labels: dict[str, list[str]] = {}
        self.calibration: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        for stage, filename in [
            ("crop", "stage_a"),
            ("maize", "disease_maize"),
            ("tomato", "disease_tomato"),
            ("potato", "disease_potato"),
        ]:
            folder = self.root / filename
            self.models[stage] = tf.keras.models.load_model(folder / "model.keras", compile=False)
            last_layer = self.models[stage].layers[-1]
            self.feature_models[stage] = (
                tf.keras.Model(self.models[stage].inputs, last_layer.input)
                if isinstance(last_layer, tf.keras.layers.Dense)
                and getattr(last_layer.activation, "__name__", "") == "softmax"
                else None
            )
            self.labels[stage] = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
            self.calibration[stage] = json.loads((folder / "calibration.json").read_text(encoding="utf-8"))

    def _predict(self, stage: str, rgb: np.ndarray) -> tuple[np.ndarray, float]:
        views = _views(rgb) if self.use_tta else tf.image.resize(rgb, [224, 224]).numpy()[None, ...]
        feature_model = self.feature_models[stage]
        if feature_model is None:
            probabilities = np.asarray(self.models[stage](views, training=False))
            logits = np.log(np.clip(probabilities, 1e-9, 1.0))
        else:
            layer = self.models[stage].layers[-1]
            features = feature_model(views, training=False)
            logits_tensor = tf.linalg.matmul(features, layer.kernel)
            if layer.use_bias:
                logits_tensor = tf.nn.bias_add(logits_tensor, layer.bias)
            logits = np.asarray(logits_tensor)
        mean_logits = logits.mean(axis=0, keepdims=True)
        temperature = float(self.calibration[stage]["temperature"])
        probabilities = calibrate(np.exp(mean_logits - mean_logits.max(axis=1, keepdims=True)), temperature)[0]
        scaled = mean_logits[0] / temperature
        maximum = float(np.max(scaled))
        energy = -temperature * (maximum + float(np.log(np.exp(scaled - maximum).sum())))
        return probabilities, energy

    @staticmethod
    def _top(probabilities: np.ndarray, labels: list[str], count: int = 3) -> list[dict[str, object]]:
        indices = np.argsort(probabilities)[::-1][:count]
        return [{"label": labels[int(index)], "probability": float(probabilities[index])} for index in indices]

    def predict(self, rgb: np.ndarray, crop_min_confidence: float = 0.70) -> dict[str, object]:
        if set(self.models) != {"crop", "maize", "tomato", "potato"}:
            raise RuntimeError("Load all four hierarchy models before prediction")
        started = time.perf_counter()
        crop_probs, crop_energy = self._predict("crop", rgb)
        crop_labels = self.labels["crop"]
        crop_top = int(np.argmax(crop_probs))
        crop_name = crop_labels[crop_top]
        crop_confidence = float(crop_probs[crop_top])
        energy_cutoff = self.calibration["crop"].get("energy_threshold")
        if energy_cutoff is not None and crop_energy > float(energy_cutoff):
            return {
                "status": "unsupported",
                "decision_reason": "Crop-stage OOD energy exceeded the validation threshold.",
                "top3": self._top(crop_probs, crop_labels),
                "calibrated_confidence": crop_confidence,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        calibrated_crop_threshold = self.calibration["crop"].get("class_thresholds", {}).get(crop_name)
        crop_threshold = (
            max(crop_min_confidence, float(calibrated_crop_threshold))
            if calibrated_crop_threshold is not None
            else crop_min_confidence
        )
        if crop_confidence < crop_threshold:
            return {
                "status": "uncertain",
                "decision_reason": "Crop stage is uncertain; retake and show top-3 crops.",
                "top3": self._top(crop_probs, crop_labels),
                "calibrated_confidence": crop_confidence,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        if crop_name in {"Other", "Unknown", "Not_a_leaf"}:
            return {
                "status": "unsupported",
                "decision_reason": "Crop stage rejected this as unsupported.",
                "top3": self._top(crop_probs, crop_labels),
                "calibrated_confidence": crop_confidence,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        stage = crop_name.lower()
        probabilities, _ = self._predict(stage, rgb)
        labels = self.labels[stage]
        order = np.argsort(probabilities)[::-1]
        best = int(order[0])
        best_label = labels[best]
        disease_confidence = float(probabilities[best])
        confidence = crop_confidence * disease_confidence
        threshold = self.calibration[stage].get("class_thresholds", {}).get(best_label)
        status = "ok" if threshold is not None and disease_confidence >= float(threshold) else "uncertain"
        reason = (
            "Disease-stage class threshold passed."
            if status == "ok"
            else "No class passed its validation precision threshold; show top-3 and retake if needed."
        )
        top3 = [
            {
                "label": labels[int(index)],
                "crop": crop_name,
                "disease": labels[int(index)].split("_", 1)[-1].replace("_", " "),
                "probability": crop_confidence * float(probabilities[index]),
            }
            for index in order[:3]
        ]
        return {
            "status": status,
            "decision_reason": reason,
            "crop": crop_name,
            "top3": top3,
            "calibrated_confidence": confidence,
            "crop_confidence": crop_confidence,
            "disease_confidence": disease_confidence,
            "latency_ms": (time.perf_counter() - started) * 1000,
        }
