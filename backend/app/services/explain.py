import base64

import cv2
import numpy as np


def create_gradcam(
    registry: object, rgb: np.ndarray, class_index: int, method: str = "gradcam++"
) -> str | None:
    """Return a Grad-CAM or Grad-CAM++ overlay for the selected classifier class."""
    model = getattr(registry, "model", None)
    if model is None:
        return None
    try:
        conv = next(
            layer for layer in reversed(model.layers) if len(layer.output.shape) == 4
        )
        import tensorflow as tf

        activation_model = tf.keras.Model(model.inputs, conv.output)
        classifier_model = tf.keras.Model(conv.output, model.output)
        image = cv2.resize(rgb, (224, 224)).astype(np.float32)[None, ...]
        activations = activation_model(image, training=False)
        if method == "gradcam++":
            with tf.GradientTape() as third_tape:
                third_tape.watch(activations)
                with tf.GradientTape() as second_tape:
                    second_tape.watch(activations)
                    with tf.GradientTape() as first_tape:
                        first_tape.watch(activations)
                        predictions = classifier_model(activations, training=False)
                        score = predictions[:, class_index]
                    first = first_tape.gradient(score, activations)
                second = second_tape.gradient(first, activations)
            third = third_tape.gradient(second, activations)
            first = first[0]
            activations_map = activations[0]
            second = second[0]
            third = third[0]
            denominator = 2.0 * second + tf.reduce_sum(
                activations_map * third, axis=(0, 1), keepdims=True
            )
            alpha = second / (denominator + 1e-8)
            weights = tf.reduce_sum(alpha * tf.nn.relu(first), axis=(0, 1))
        else:
            with tf.GradientTape() as tape:
                tape.watch(activations)
                predictions = classifier_model(activations, training=False)
                score = predictions[:, class_index]
            grads = tape.gradient(score, activations)
            weights = tf.reduce_mean(grads, axis=(1, 2))[0]
        heat = tf.maximum(tf.reduce_sum(activations[0] * weights, axis=-1), 0)
        heat = heat / (tf.reduce_max(heat) + 1e-8)
        heatmap = cv2.resize(heat.numpy(), (rgb.shape[1], rgb.shape[0]))
        colored = cv2.applyColorMap(np.uint8(255 * heatmap), cv2.COLORMAP_JET)  # type: ignore[call-overload]
        overlay = cv2.addWeighted(
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), 0.6, colored, 0.4, 0
        )
        ok, raw = cv2.imencode(".png", overlay)
        return base64.b64encode(raw).decode("ascii") if ok else None
    except (StopIteration, ValueError, TypeError, AttributeError):
        return None
