import os
import json
import numpy as np
import tensorflow as tf
from pathlib import Path

# --- 1. GPU CHECK & CONFIG ---
print("Num GPUs Available: ", len(tf.config.list_physical_devices('GPU')))

DATA_DIR = Path('data/processed')
MODEL_DIR = Path('models')
MODEL_DIR.mkdir(exist_ok=True)

IMG_SIZE = (224, 224)
BATCH_SIZE = 16  # Kept at 16 for 4GB VRAM safety
EPOCHS_STAGE1 = 5
EPOCHS_STAGE2 = 8

# --- 2. LOAD DATASETS ---
print("Loading datasets...")
train_ds = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR / 'train', image_size=IMG_SIZE, batch_size=BATCH_SIZE, shuffle=True, seed=42)
val_ds = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR / 'val', image_size=IMG_SIZE, batch_size=BATCH_SIZE, shuffle=False)
test_ds = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR / 'test', image_size=IMG_SIZE, batch_size=BATCH_SIZE, shuffle=False)

class_names = train_ds.class_names
num_classes = len(class_names)
print(f"Found {num_classes} classes: {class_names}")

# Save class names for the app later
with open(MODEL_DIR / 'class_names.json', 'w') as f:
    json.dump(class_names, f)

# Optimize dataset performance
AUTOTUNE = tf.data.AUTOTUNE
train_ds = train_ds.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
val_ds = val_ds.cache().prefetch(buffer_size=AUTOTUNE)
test_ds = test_ds.cache().prefetch(buffer_size=AUTOTUNE)

# --- 3. CALCULATE CLASS WEIGHTS (for imbalance) ---
# Get counts for each class in the training set
class_counts = np.zeros(num_classes)
for images, labels in train_ds:
    for label in labels:
        class_counts[label.numpy()] += 1

total_images = sum(class_counts)
class_weights = {i: total_images / (num_classes * count) if count > 0 else 1.0
                 for i, count in enumerate(class_counts)}
print("Class weights calculated to handle imbalance.")

# --- 4. BUILD MODEL (Stage 1: Frozen Base) ---
print("Building MobileNetV2 model...")
data_augmentation = tf.keras.Sequential([
    tf.keras.layers.RandomFlip('horizontal'),
    tf.keras.layers.RandomRotation(0.2),
    tf.keras.layers.RandomZoom(0.2),
    tf.keras.layers.RandomBrightness(0.2),
])

base_model = tf.keras.applications.MobileNetV2(
    input_shape=IMG_SIZE + (3,), include_top=False, weights='imagenet')
base_model.trainable = False  # Freeze the base model

inputs = tf.keras.Input(shape=IMG_SIZE + (3,))
x = data_augmentation(inputs)
x = tf.keras.applications.mobilenet_v2.preprocess_input(x)
x = base_model(x, training=False)
x = tf.keras.layers.GlobalAveragePooling2D()(x)
x = tf.keras.layers.Dropout(0.5)(x)
x = tf.keras.layers.Dense(128, activation='relu')(x)
outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)

model = tf.keras.Model(inputs, outputs)

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Callbacks
early_stop = tf.keras.callbacks.EarlyStopping(monitor='val_accuracy', patience=3, restore_best_weights=True)
checkpoint = tf.keras.callbacks.ModelCheckpoint(str(MODEL_DIR / 'best_model.keras'), monitor='val_accuracy', save_best_only=True)

# --- 5. TRAIN STAGE 1 ---
print("\n--- Starting Stage 1: Training Top Layers (Frozen Base) ---")
history1 = model.fit(
    train_ds, validation_data=val_ds,
    epochs=EPOCHS_STAGE1,
    class_weight=class_weights,
    callbacks=[early_stop, checkpoint]
)

# --- 6. TRAIN STAGE 2 (Fine-Tuning Top 30 Layers) ---
print("\n--- Starting Stage 2: Fine-Tuning Top 30 Layers ---")
base_model.trainable = True

# Freeze all layers except the top 30
for layer in base_model.layers[:-30]:
    layer.trainable = False

# Recompile with a much lower learning rate
model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

history2 = model.fit(
    train_ds, validation_data=val_ds,
    epochs=EPOCHS_STAGE2,
    class_weight=class_weights,
    callbacks=[early_stop, checkpoint]
)

# --- 7. SAVE FINAL MODEL ---
final_model_path = MODEL_DIR / 'crop_disease_model.keras'
model.save(final_model_path)
print(f"\nTraining Complete! Final model saved to {final_model_path}")