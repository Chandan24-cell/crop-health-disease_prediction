"""Export a selected Keras stage model to int8 TFLite and optional ONNX with parity checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parents[1]


def representative_data(manifest: Path, limit: int = 256) -> list[np.ndarray]:
    import csv

    with manifest.open(encoding="utf-8", newline="") as stream:
        paths = [ROOT / row["path"] for row in csv.DictReader(stream) if row["split"] == "train"][:limit]
    result = []
    for path in paths:
        image = tf.io.decode_image(tf.io.read_file(str(path)), channels=3, expand_animations=False)
        result.append(tf.image.resize(image, [224, 224]).numpy()[None, ...].astype(np.float32))
    return result


def _run_tflite(path: Path, images: np.ndarray) -> np.ndarray:
    interpreter = tf.lite.Interpreter(model_path=str(path))
    interpreter.allocate_tensors()
    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]
    results = []
    for image in images:
        tensor = image[None, ...]
        scale, zero = input_detail["quantization"]
        if np.issubdtype(input_detail["dtype"], np.integer):
            tensor = np.clip(
                np.rint(tensor / scale + zero), np.iinfo(input_detail["dtype"]).min, np.iinfo(input_detail["dtype"]).max
            ).astype(input_detail["dtype"])
        interpreter.set_tensor(input_detail["index"], tensor.astype(input_detail["dtype"]))
        interpreter.invoke()
        output = interpreter.get_tensor(output_detail["index"])
        output_scale, output_zero = output_detail["quantization"]
        if np.issubdtype(output_detail["dtype"], np.integer) and output_scale:
            output = (output.astype(np.float32) - output_zero) * output_scale
        results.append(output[0])
    return np.asarray(results)


def export(model_path: Path, manifest: Path, tolerance: float) -> dict[str, object]:
    output_dir = model_path.parent
    model = tf.keras.models.load_model(model_path, compile=False)
    reps = representative_data(manifest)
    if not reps:
        raise ValueError("No training images for int8 representative calibration")
    sample = np.concatenate(reps[:16])
    keras_output = np.asarray(model(sample, training=False))
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = lambda: ((item,) for item in reps)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    converter.inference_input_type = tf.uint8
    converter.inference_output_type = tf.uint8
    tflite_path = output_dir / "model_int8.tflite"
    tflite_path.write_bytes(converter.convert())
    tflite_output = _run_tflite(tflite_path, sample)
    max_error = float(np.max(np.abs(keras_output - tflite_output)))
    agreement = float(np.mean(keras_output.argmax(axis=1) == tflite_output.argmax(axis=1)))
    result: dict[str, object] = {
        "tflite": str(tflite_path.relative_to(ROOT)),
        "int8_max_absolute_probability_error": max_error,
        "argmax_agreement": agreement,
        "tolerance": tolerance,
        "int8_within_tolerance": max_error <= tolerance,
    }
    try:
        import onnxruntime as ort
        import tf2onnx

        onnx_path = output_dir / "model.onnx"
        signature = (tf.TensorSpec((None, 224, 224, 3), tf.float32, name="image"),)
        tf2onnx.convert.from_keras(model, input_signature=signature, output_path=str(onnx_path), opset=13)
        session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        onnx_input = session.get_inputs()[0].name
        onnx_output = session.run(None, {onnx_input: sample})[0]
        onnx_error = float(np.max(np.abs(keras_output - onnx_output)))
        result.update(
            {
                "onnx": str(onnx_path.relative_to(ROOT)),
                "onnx_max_absolute_probability_error": onnx_error,
                "onnx_argmax_agreement": float(np.mean(keras_output.argmax(axis=1) == onnx_output.argmax(axis=1))),
                "onnx_within_tolerance": onnx_error <= tolerance,
            }
        )
    except ImportError as exc:
        result["onnx"] = f"NOT EXPORTED: install export extra ({exc.name})"
    (output_dir / "export_verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    if max_error > tolerance:
        raise RuntimeError(f"TFLite int8 parity failed tolerance {tolerance}: max error {max_error:.4f}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path, help="Selected Keras model .keras file")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data/splits_v2.csv")
    parser.add_argument("--tolerance", type=float, default=0.15)
    args = parser.parse_args()
    print(json.dumps(export(args.model, args.manifest, args.tolerance), indent=2))


if __name__ == "__main__":
    main()
