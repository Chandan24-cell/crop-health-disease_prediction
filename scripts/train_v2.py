"""Train hierarchical v2 candidates. Run the full 3-seed grid on a CUDA GPU."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/splits_v2.csv"
RUNS = ROOT / "models/v2/runs"
ARCHITECTURES = ("mobilenetv2", "efficientnetv2b0", "convnexttiny", "mobilenetv3large")
STAGES = ("crop", "maize", "tomato", "potato")


def stage_label(label: str, stage: str) -> str | None:
    if stage == "crop":
        return "Other" if label == "Unknown" else "Not_a_leaf" if label == "Not_a_leaf" else label.split("_", 1)[0]
    return label if label.startswith(stage.capitalize() + "_") else None


def get_rows(split: str, stage: str) -> tuple[list[str], list[int], list[str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as stream:
        rows = [row for row in csv.DictReader(stream) if row["split"] == split]
    pairs = [
        (str(ROOT / row["path"]), mapped) for row in rows if (mapped := stage_label(row["label"], stage)) is not None
    ]
    labels = sorted({label for _, label in pairs})
    encode = {label: i for i, label in enumerate(labels)}
    return [path for path, _ in pairs], [encode[label] for _, label in pairs], labels


def _load_example(path: tf.Tensor, label: tf.Tensor, count: int) -> tuple[tf.Tensor, tf.Tensor]:
    image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
    image.set_shape([None, None, 3])
    image = tf.image.resize(image, [256, 256])
    image = tf.image.random_crop(image, [224, 224, 3])
    image = tf.image.random_flip_left_right(image)
    image = tf.image.rot90(image, k=tf.random.uniform([], 0, 4, dtype=tf.int32))
    image = tf.image.random_brightness(image, max_delta=35.0)
    image = tf.image.random_contrast(image, lower=0.65, upper=1.35)
    image = tf.image.random_saturation(image / 255.0, lower=0.65, upper=1.4) * 255.0
    image = tf.clip_by_value(image, 0.0, 255.0)
    image = tf.cond(
        tf.random.uniform([]) < 0.15,
        lambda: tf.clip_by_value(image + tf.random.normal(tf.shape(image), stddev=8.0), 0, 255),
        lambda: image,
    )
    image = tf.cond(
        tf.random.uniform([]) < 0.12,
        lambda: tf.cast(tf.image.decode_jpeg(tf.io.encode_jpeg(tf.cast(image, tf.uint8), quality=48)), tf.float32),
        lambda: image,
    )
    image.set_shape([224, 224, 3])

    def blur() -> tf.Tensor:
        kernel = tf.constant([[1, 2, 1], [2, 4, 2], [1, 2, 1]], dtype=tf.float32) / 16.0
        kernel = tf.tile(kernel[:, :, None, None], [1, 1, 3, 1])
        return tf.nn.depthwise_conv2d(image[None, ...], kernel, [1, 1, 1, 1], "SAME")[0]

    image = tf.cond(tf.random.uniform([]) < 0.12, blur, lambda: image)
    # One random erasing patch; a field-scene background patch is used when supplied.
    background_paths = [
        path
        for path in tf.io.gfile.glob(str(ROOT / "data/backgrounds/*"))
        if Path(path).suffix.lower() in {".jpg", ".jpeg", ".png"}
    ]
    if background_paths:
        choice = tf.random.uniform([], 0, len(background_paths), dtype=tf.int32)
        background = tf.io.decode_image(
            tf.io.read_file(tf.gather(background_paths, choice)), channels=3, expand_animations=False
        )
        background = tf.image.resize(background, [224, 224])
        use_scene = tf.random.uniform([]) < 0.20
    else:
        background = tf.zeros_like(image)
        use_scene = tf.constant(False)
    erase = tf.random.uniform([]) < 0.35
    y = tf.random.uniform([], 0, 192, dtype=tf.int32)
    x = tf.random.uniform([], 0, 192, dtype=tf.int32)
    yy, xx = tf.meshgrid(tf.range(224), tf.range(224), indexing="ij")
    cutout_mask = tf.cast((yy < y) | (yy >= y + 32) | (xx < x) | (xx >= x + 32), tf.float32)[..., None]
    fill = tf.where(use_scene, background, tf.zeros_like(image))
    image = tf.where(erase, image * cutout_mask + fill * (1 - cutout_mask), image)
    one_hot = tf.one_hot(label, count)
    return image, one_hot


def _batch_mix(images: tf.Tensor, labels: tf.Tensor, weights: tf.Tensor) -> tuple[tf.Tensor, tf.Tensor, tf.Tensor]:
    batch_size = tf.shape(images)[0]
    permutation = tf.random.shuffle(tf.range(batch_size))
    other_images, other_labels = tf.gather(images, permutation), tf.gather(labels, permutation)
    other_weights = tf.gather(weights, permutation)
    g1, g2 = tf.random.gamma([], 0.4), tf.random.gamma([], 0.4)
    ratio = g1 / (g1 + g2 + 1e-7)
    mix = tf.random.uniform([]) < 0.5
    mixed = images * ratio + other_images * (1 - ratio)
    mix_labels = labels * ratio + other_labels * (1 - ratio)
    mix_weights = weights * ratio + other_weights * (1 - ratio)
    # CutMix branch swaps a random rectangular patch for every image in the batch.
    height = tf.shape(images)[1]
    width = tf.shape(images)[2]
    cut_ratio = tf.sqrt(1 - ratio)
    cut_h = tf.cast(tf.cast(height, tf.float32) * cut_ratio, tf.int32)
    cut_w = tf.cast(tf.cast(width, tf.float32) * cut_ratio, tf.int32)
    cy, cx = tf.random.uniform([], 0, height, dtype=tf.int32), tf.random.uniform([], 0, width, dtype=tf.int32)
    y1, y2 = tf.maximum(0, cy - cut_h // 2), tf.minimum(height, cy + cut_h // 2)
    x1, x2 = tf.maximum(0, cx - cut_w // 2), tf.minimum(width, cx + cut_w // 2)
    yy, xx = tf.meshgrid(tf.range(height), tf.range(width), indexing="ij")
    region = ((yy >= y1) & (yy < y2) & (xx >= x1) & (xx < x2))[None, ..., None]
    cut_images = tf.where(region, other_images, images)
    actual_ratio = 1 - tf.cast((y2 - y1) * (x2 - x1), tf.float32) / tf.cast(height * width, tf.float32)
    cut_labels = labels * actual_ratio + other_labels * (1 - actual_ratio)
    cut_weights = weights * actual_ratio + other_weights * (1 - actual_ratio)
    return tf.cond(mix, lambda: (mixed, mix_labels, mix_weights), lambda: (cut_images, cut_labels, cut_weights))


def _load_eval_example(path: tf.Tensor, label: tf.Tensor, count: int) -> tuple[tf.Tensor, tf.Tensor]:
    image = tf.io.decode_image(tf.io.read_file(path), channels=3, expand_animations=False)
    image.set_shape([None, None, 3])
    return tf.image.resize(image, [224, 224]), tf.one_hot(label, count)


def make_dataset(
    split: str, stage: str, labels: list[str], batch_size: int, training: bool, class_weights: np.ndarray | None = None
) -> tf.data.Dataset:
    paths, targets, observed_labels = get_rows(split, stage)
    if observed_labels != labels:
        remap = {label: index for index, label in enumerate(labels)}
        targets = [remap[label] for _, label in zip(paths, [labels[index] for index in targets], strict=True)]
    ds = tf.data.Dataset.from_tensor_slices((paths, targets))
    if training:
        ds = ds.shuffle(min(len(paths), 5000), reshuffle_each_iteration=True)
    loader = (
        (lambda path, label: _load_example(path, label, len(labels)))
        if training
        else (lambda path, label: _load_eval_example(path, label, len(labels)))
    )
    ds = ds.map(loader, num_parallel_calls=tf.data.AUTOTUNE)
    ds = ds.batch(batch_size, drop_remainder=training)
    if training:
        assert class_weights is not None
        weights = tf.constant(class_weights, dtype=tf.float32)
        ds = ds.map(lambda x, y: (x, y, tf.reduce_sum(y * weights, axis=1)), num_parallel_calls=tf.data.AUTOTUNE)
        ds = ds.map(_batch_mix, num_parallel_calls=tf.data.AUTOTUNE)
    return ds.prefetch(tf.data.AUTOTUNE)


def build_model(architecture: str, num_classes: int) -> tuple[tf.keras.Model, tf.keras.Model]:
    constructors = {
        "mobilenetv2": lambda: tf.keras.applications.MobileNetV2(
            include_top=False, weights="imagenet", input_shape=(224, 224, 3)
        ),
        "efficientnetv2b0": lambda: tf.keras.applications.EfficientNetV2B0(
            include_top=False, weights="imagenet", input_shape=(224, 224, 3)
        ),
        "convnexttiny": lambda: tf.keras.applications.ConvNeXtTiny(
            include_top=False, weights="imagenet", input_shape=(224, 224, 3)
        ),
        "mobilenetv3large": lambda: tf.keras.applications.MobileNetV3Large(
            include_top=False, weights="imagenet", input_shape=(224, 224, 3)
        ),
    }
    if architecture not in constructors:
        raise ValueError(f"Unknown architecture: {architecture}")
    backbone = constructors[architecture]()
    backbone.trainable = False
    inputs = tf.keras.Input((224, 224, 3))
    x = tf.keras.layers.Rescaling(1.0 / 127.5, offset=-1.0)(inputs) if architecture == "mobilenetv2" else inputs
    x = tf.keras.layers.RandomFlip("horizontal")(x)
    x = tf.keras.layers.RandomRotation(0.15)(x)
    x = tf.keras.layers.RandomZoom(0.15)(x)
    x = tf.keras.layers.RandomBrightness(0.12, value_range=(0, 255))(x)
    x = tf.keras.layers.RandomContrast(0.20)(x)
    x = tf.keras.layers.GaussianNoise(5.0)(x)
    x = backbone(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.35)(x)
    output = tf.keras.layers.Dense(num_classes, activation="softmax", dtype="float32")(x)
    return tf.keras.Model(inputs, output), backbone


def train_one(stage: str, architecture: str, seed: int, batch_size: int) -> Path:
    random.seed(seed)
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)
    gpu_available = bool(tf.config.list_physical_devices("GPU"))
    tf.keras.mixed_precision.set_global_policy("mixed_float16" if gpu_available else "float32")
    train_paths, train_ids, labels = get_rows("train", stage)
    counts = np.bincount(train_ids, minlength=len(labels)).astype(np.float64)
    weights = np.power(counts.sum() / np.maximum(counts, 1), 0.5)
    weights /= weights.mean()
    name_to_index = {name: index for index, name in enumerate(labels)}
    for left, right in [
        ("Maize_Gray_leaf_spot", "Maize_Northern_Leaf_Blight"),
        ("Tomato_Early_blight", "Tomato_Late_blight"),
        ("Potato_Early_blight", "Potato_Late_blight"),
    ]:
        for hard_name in (left, right):
            if hard_name in name_to_index:
                weights[name_to_index[hard_name]] *= 2.0
    weights /= weights.mean()
    model, backbone = build_model(architecture, len(labels))
    out_dir = RUNS / stage / architecture / f"seed_{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    train_ds = make_dataset("train", stage, labels, batch_size, True, weights)
    val_ds = make_dataset("val", stage, labels, batch_size, False)
    best_path = out_dir / "model.keras"
    stage1_path = out_dir / "stage1.keras"
    stage1_callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(stage1_path, monitor="val_loss", save_best_only=True),
    ]
    steps = max(1, len(train_paths) // batch_size)
    lr = tf.keras.optimizers.schedules.CosineDecay(1e-3, steps * 8, alpha=0.02)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(lr),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )
    model.fit(train_ds, validation_data=val_ds, epochs=8, callbacks=stage1_callbacks, verbose=2)
    backbone.trainable = True
    for layer in backbone.layers[:-40]:
        layer.trainable = False
    model.compile(
        optimizer=tf.keras.optimizers.Adam(tf.keras.optimizers.schedules.CosineDecay(1e-5, steps * 20, alpha=0.05)),
        loss=tf.keras.losses.CategoricalCrossentropy(label_smoothing=0.1),
        metrics=["accuracy"],
    )
    stage2_callbacks = [
        tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True),
        tf.keras.callbacks.ModelCheckpoint(best_path, monitor="val_loss", save_best_only=True),
    ]
    model.fit(train_ds, validation_data=val_ds, epochs=20, callbacks=stage2_callbacks, verbose=2)
    val_probs = np.concatenate([np.asarray(model(x, training=False)) for x, y in val_ds])
    _, val_y, _ = get_rows("val", stage)
    macro_f1 = float(f1_score(val_y, val_probs.argmax(axis=1), average="macro"))
    (out_dir / "metrics.json").write_text(
        json.dumps(
            {
                "stage": stage,
                "architecture": architecture,
                "seed": seed,
                "val_macro_f1": macro_f1,
                "epochs": 28,
                "gpu": gpu_available,
                "batch_size": batch_size,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return best_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=(*STAGES, "all"), default="all")
    parser.add_argument("--architectures", nargs="+", choices=(*ARCHITECTURES, "all"), default=["all"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 29, 47])
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    stages = STAGES if args.stage == "all" else (args.stage,)
    architectures = ARCHITECTURES if "all" in args.architectures else args.architectures
    for stage in stages:
        for architecture in architectures:
            for seed in args.seeds:
                print(f"Training {stage}/{architecture}/seed_{seed}")
                train_one(stage, architecture, seed, args.batch_size)


if __name__ == "__main__":
    main()
