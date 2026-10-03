"""Train a MobileNetV2-encoder U-Net from manually corrected lesion masks."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import tensorflow as tf

SIZE = 224


def read_pairs(csv_path: Path, split: str) -> list[tuple[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as stream:
        return [
            (row["image_path"], row["lesion_mask_path"])
            for row in csv.DictReader(stream)
            if row.get("split", "") == split and row.get("review_status", "corrected") in {"corrected", "verified"}
        ]


def make_dataset(pairs: list[tuple[str, str]], training: bool, batch_size: int) -> tf.data.Dataset:
    image_paths, mask_paths = zip(*pairs, strict=True)
    dataset = tf.data.Dataset.from_tensor_slices((list(image_paths), list(mask_paths)))

    def load(image_path: tf.Tensor, mask_path: tf.Tensor) -> tuple[tf.Tensor, tf.Tensor]:
        image = tf.io.decode_image(tf.io.read_file(image_path), channels=3, expand_animations=False)
        mask = tf.io.decode_image(tf.io.read_file(mask_path), channels=1, expand_animations=False)
        image = tf.image.resize(image, [SIZE, SIZE]) / 255.0
        mask = tf.image.resize(mask, [SIZE, SIZE], method="nearest") / 255.0
        if training and tf.random.uniform([]) < 0.5:
            image, mask = tf.image.flip_left_right(image), tf.image.flip_left_right(mask)
        return image, tf.cast(mask > 0.5, tf.float32)

    if training:
        dataset = dataset.shuffle(len(pairs), reshuffle_each_iteration=True)
    return dataset.map(load, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(tf.data.AUTOTUNE)


def build_unet() -> tf.keras.Model:
    encoder = tf.keras.applications.MobileNetV2(
        input_shape=(SIZE, SIZE, 3), include_top=False, weights="imagenet"
    )
    encoder.trainable = False
    skip_names = ["block_1_expand_relu", "block_3_expand_relu", "block_6_expand_relu", "block_13_expand_relu"]
    outputs = [encoder.get_layer(name).output for name in skip_names] + [encoder.output]
    backbone = tf.keras.Model(encoder.input, outputs)
    inputs = tf.keras.Input((SIZE, SIZE, 3), name="rgb_0_1")
    x = inputs * 2.0 - 1.0
    skips = backbone(x, training=False)
    x = skips[-1]
    for filters, skip in zip((512, 256, 128, 64), reversed(skips[:-1]), strict=True):
        x = tf.keras.layers.Conv2DTranspose(filters, 3, strides=2, padding="same", activation="relu")(x)
        x = tf.keras.layers.Concatenate()([x, skip])
        x = tf.keras.layers.Conv2D(filters, 3, padding="same", activation="relu")(x)
        x = tf.keras.layers.Conv2D(filters, 3, padding="same", activation="relu")(x)
    x = tf.keras.layers.Conv2DTranspose(32, 3, strides=2, padding="same", activation="relu")(x)
    output = tf.keras.layers.Conv2D(1, 1, activation="sigmoid", name="lesion_probability")(x)
    return tf.keras.Model(inputs, output, name="MobileNetV2LesionUNet")


def dice_loss(y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
    axes = (1, 2, 3)
    intersection = tf.reduce_sum(y_true * y_pred, axis=axes)
    denominator = tf.reduce_sum(y_true + y_pred, axis=axes)
    return 1.0 - tf.reduce_mean((2.0 * intersection + 1.0) / (denominator + 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=Path("data/severity/annotations.csv"))
    parser.add_argument("--output", type=Path, default=Path("models/severity/lesion_unet.keras"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=40)
    args = parser.parse_args()
    train_pairs, val_pairs = read_pairs(args.annotations, "train"), read_pairs(args.annotations, "val")
    if len(train_pairs) < 80 or len(val_pairs) < 20:
        raise SystemExit("Need corrected annotations with at least 80 train and 20 validation image/mask pairs")
    model = build_unet()
    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss=lambda y_true, y_pred: tf.keras.losses.BinaryCrossentropy()(y_true, y_pred) + dice_loss(y_true, y_pred),
        metrics=[tf.keras.metrics.BinaryIoU(target_class_ids=[1], threshold=0.5, name="lesion_iou")],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    model.fit(
        make_dataset(train_pairs, True, args.batch_size),
        validation_data=make_dataset(val_pairs, False, args.batch_size),
        epochs=args.epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=7, restore_best_weights=True, monitor="val_loss"),
            tf.keras.callbacks.ModelCheckpoint(args.output, save_best_only=True, monitor="val_loss"),
        ],
    )


if __name__ == "__main__":
    main()
