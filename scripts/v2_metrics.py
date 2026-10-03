"""Calibration, threshold selection and metrics shared by the v2 tools."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.metrics import precision_recall_curve


def calibrate_temperature(probabilities: np.ndarray, labels: np.ndarray) -> float:
    logits = np.log(np.clip(probabilities, 1e-9, 1.0))

    def nll(temperature: float) -> float:
        scaled = logits / temperature
        scaled -= scaled.max(axis=1, keepdims=True)
        logsumexp = np.log(np.exp(scaled).sum(axis=1))
        return float(np.mean(logsumexp - scaled[np.arange(labels.size), labels]))

    result = minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded")
    return float(result.x)


def apply_temperature(probabilities: np.ndarray, temperature: float) -> np.ndarray:
    logits = np.log(np.clip(probabilities, 1e-9, 1.0)) / temperature
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    return exp / exp.sum(axis=1, keepdims=True)


def expected_calibration_error(probabilities: np.ndarray, labels: np.ndarray, bins: int = 15) -> float:
    confidence = probabilities.max(axis=1)
    correct = probabilities.argmax(axis=1) == labels
    edges = np.linspace(0.0, 1.0, bins + 1)
    return float(
        sum(
            np.mean((confidence >= edges[i]) & (confidence < edges[i + 1]))
            * abs(
                float(np.mean(correct[(confidence >= edges[i]) & (confidence < edges[i + 1])]))
                - float(np.mean(confidence[(confidence >= edges[i]) & (confidence < edges[i + 1])]))
            )
            for i in range(bins)
            if np.any((confidence >= edges[i]) & (confidence < edges[i + 1]))
        )
    )


def class_thresholds(
    probabilities: np.ndarray, labels: np.ndarray, class_names: list[str], minimum_precision: float = 0.95
) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for class_index, name in enumerate(class_names):
        truth = (labels == class_index).astype(np.uint8)
        precision, recall, thresholds = precision_recall_curve(truth, probabilities[:, class_index])
        eligible = np.flatnonzero(precision[:-1] >= minimum_precision)
        result[name] = float(thresholds[eligible[np.argmax(recall[eligible])]]) if eligible.size else None
    return result


def energy_score(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Negative log-sum-exp energy; larger values are treated as more OOD."""
    scaled = logits / temperature
    maximum = scaled.max(axis=1)
    return -temperature * (maximum + np.log(np.exp(scaled - maximum[:, None]).sum(axis=1)))


def ood_threshold(
    logits: np.ndarray,
    labels: np.ndarray,
    class_names: list[str],
    target_false_accept: float = 0.01,
    temperature: float = 1.0,
) -> float:
    unknown_ids = [i for i, name in enumerate(class_names) if name in {"Unknown", "Not_a_leaf", "Other"}]
    unknown_mask = np.isin(labels, unknown_ids)
    scores = energy_score(logits, temperature)
    if np.any(unknown_mask):
        ordered = np.sort(scores[unknown_mask])
        accepted_unknowns = int(np.floor(target_false_accept * len(ordered)))
        return float(np.nextafter(ordered[accepted_unknowns], -np.inf))
    return float(np.max(scores))
