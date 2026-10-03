import json
from pathlib import Path
from typing import Any

import numpy as np


class ModelRegistry:
    """Loads one configured Keras model and its metadata once per application lifespan."""

    def __init__(self, root: Path, version: str = "latest") -> None:
        self.root = root
        self.version = version
        self.model: Any | None = None
        self.labels: list[str] = []
        self.calibration: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {}

    def load(self) -> None:
        version_dir = self.root / self.version
        if self.version == "latest":
            versions = (
                sorted(p for p in self.root.iterdir() if p.is_dir())
                if self.root.exists()
                else []
            )
            version_dir = versions[-1] if versions else self.root
        if (version_dir / "model.keras").exists():
            model_path = version_dir / "model.keras"
            labels_path = version_dir / "labels.json"
            self.version = version_dir.name
        else:
            # Backward-compatible layout; artifacts remain untouched until migrated intentionally.
            model_path = self.root / "crop_disease_model.keras"
            labels_path = self.root / "class_names.json"
            self.version = "legacy"
        if not model_path.exists() or not labels_path.exists():
            raise FileNotFoundError(f"Model assets were not found under {self.root}")
        import tensorflow as tf

        self.model = tf.keras.models.load_model(model_path, compile=False)
        self.labels = json.loads(labels_path.read_text(encoding="utf-8"))
        if (version_dir / "calibration.json").exists():
            self.calibration = json.loads(
                (version_dir / "calibration.json").read_text(encoding="utf-8")
            )
        if (version_dir / "metadata.json").exists():
            self.metadata = json.loads(
                (version_dir / "metadata.json").read_text(encoding="utf-8")
            )

    def predict(self, rgb: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model has not been loaded")
        import cv2

        resized = cv2.resize(rgb, (224, 224)).astype(np.float32)[None, ...]
        values = np.asarray(self.model.predict(resized, verbose=0))[0].astype(float)
        temperature = float(self.calibration.get("temperature", 1.0))
        if temperature != 1.0:
            logits = np.log(np.maximum(values, 1e-9)) / temperature
            values = np.exp(logits - np.max(logits))
            values /= values.sum()
        return values
