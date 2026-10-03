import os
import json
import numpy as np
import tensorflow as tf
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix

# --- 1. LOAD MODEL AND DATA ---
MODEL_DIR = Path('models')
DATA_DIR = Path('data/processed')

print("Loading model and data...")
model = tf.keras.models.load_model(MODEL_DIR / 'crop_disease_model.keras')

with open(MODEL_DIR / 'class_names.json', 'r') as f:
    class_names = json.load(f)

val_ds = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR / 'val', image_size=(224, 224), batch_size=32, shuffle=False)
test_ds = tf.keras.utils.image_dataset_from_directory(
    DATA_DIR / 'test', image_size=(224, 224), batch_size=32, shuffle=False)

# Get true labels and predictions for TEST set
y_true, y_pred, y_pred_proba = [], [], []

print("Evaluating on Test Set...")
for images, labels in test_ds:
    preds = model.predict(images, verbose=0)
    y_true.extend(labels.numpy())
    y_pred.extend(np.argmax(preds, axis=1))
    y_pred_proba.extend(np.max(preds, axis=1))

y_true = np.array(y_true)
y_pred = np.array(y_pred)
y_pred_proba = np.array(y_pred_proba)

# --- 2. METRICS & CONFUSION MATRIX ---
print("\n--- Test Set Classification Report ---")
print(classification_report(y_true, y_pred, target_names=class_names))

print("Plotting Confusion Matrix...")
cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(14, 10))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=class_names, yticklabels=class_names)
plt.title('Confusion Matrix (Test Set)')
plt.xlabel('Predicted')
plt.ylabel('True')
plt.xticks(rotation=45, ha='right')
plt.yticks(rotation=0)
plt.tight_layout()
plt.savefig(MODEL_DIR / 'confusion_matrix.png', dpi=300)
print(f"Confusion matrix saved to {MODEL_DIR / 'confusion_matrix.png'}")

# --- 3. FALSE POSITIVE RATE ANALYSIS ---
# Define which classes are "Negatives" (should NEVER be predicted as a disease)
negative_classes = ['Maize_healthy', 'Potato_healthy', 'Tomato_healthy', 'Unknown', 'Not_a_leaf']
negative_indices = [class_names.index(c) for c in negative_classes if c in class_names]
disease_indices = [i for i in range(len(class_names)) if i not in negative_indices]

# Filter test set to only negative instances
negative_mask = np.isin(y_true, negative_indices)
y_true_neg = y_true[negative_mask]
y_pred_neg = y_pred[negative_mask]
y_pred_proba_neg = y_pred_proba[negative_mask]


def calculate_fpr_at_threshold(threshold, y_true_neg, y_pred_neg, y_pred_proba_neg, disease_indices):
    fp_count = sum(1 for pred_label, prob in zip(y_pred_neg, y_pred_proba_neg)
                   if prob >= threshold and pred_label in disease_indices)
    return fp_count / len(y_true_neg) if len(y_true_neg) > 0 else 0.0


# --- 4. THRESHOLD TUNING ON VALIDATION SET ---
print("\n--- Threshold Tuning (on Validation Set) ---")
y_val_true, y_val_pred, y_val_proba = [], [], []

for images, labels in val_ds:
    preds = model.predict(images, verbose=0)
    y_val_true.extend(labels.numpy())
    y_val_pred.extend(np.argmax(preds, axis=1))
    y_val_proba.extend(np.max(preds, axis=1))

y_val_true = np.array(y_val_true)
y_val_pred = np.array(y_val_pred)
y_val_proba = np.array(y_val_proba)

val_negative_mask = np.isin(y_val_true, negative_indices)
y_val_true_neg = y_val_true[val_negative_mask]
y_val_pred_neg = y_val_pred[val_negative_mask]
y_val_proba_neg = y_val_proba[val_negative_mask]

val_disease_mask = np.isin(y_val_true, disease_indices)
y_val_true_dis = y_val_true[val_disease_mask]
y_val_pred_dis = y_val_pred[val_disease_mask]
y_val_proba_dis = y_val_proba[val_disease_mask]

print(f"{'Threshold':<10} | {'Disease Recall':<15} | {'False Positive Rate (Negatives)':<30}")
print("-" * 65)

best_threshold = 0.85  # Default safe bet
for thresh in np.arange(0.70, 0.96, 0.05):
    # Recall: % of actual diseases correctly identified with confidence >= thresh
    true_positives = sum(1 for true_l, pred_l, prob in zip(y_val_true_dis, y_val_pred_dis, y_val_proba_dis)
                         if prob >= thresh and pred_l in disease_indices)
    recall = true_positives / len(y_val_true_dis) if len(y_val_true_dis) > 0 else 0.0

    fpr = calculate_fpr_at_threshold(thresh, y_val_true_neg, y_val_pred_neg, y_val_proba_neg, disease_indices)

    print(f"{thresh:<10.2f} | {recall:<15.2%} | {fpr:<30.2%}")

    # Heuristic: We want high recall (>85%) and very low FPR (<5%)
    if recall >= 0.85 and fpr <= 0.05:
        best_threshold = thresh

print(f"\nRecommended Confidence Threshold for App: {best_threshold:.2f}")

# --- 5. PREDICT_WITH_SAFETY FUNCTION TEMPLATE ---
print("\n" + "=" * 60)
print("COPY THIS FUNCTION INTO YOUR STREAMLIT APP (Phase 6):")
print("=" * 60)
print("""
def predict_with_safety(image_array, model, class_names, threshold=0.85):
    import numpy as np
    from tensorflow.keras.applications.mobilenet_v2 import preprocess_input

    # 1. Preprocess and predict
    img_batch = np.expand_dims(image_array, axis=0)
    img_preprocessed = preprocess_input(img_batch)
    preds = model.predict(img_preprocessed, verbose=0)[0]

    # Get top 2 predictions
    top_2_indices = np.argsort(preds)[-2:][::-1]
    top_idx, second_idx = top_2_indices[0], top_2_indices[1]
    top_conf, second_conf = preds[top_idx], preds[second_idx]
    top_class = class_names[top_idx]
    second_class = class_names[second_idx]

    disease_classes = [c for c in class_names if c not in ['Unknown', 'Not_a_leaf', 'Maize_healthy', 'Potato_healthy', 'Tomato_healthy']]

    # 2. Safety Logic: Low Confidence
    if top_conf < threshold:
        return {"diagnosis": "Uncertain", "confidence": float(top_conf), "severity_ready": False,
                "message": "Not sure - please retake the photo or consult an extension officer."}

    # 3. Safety Logic: Unknown or Not a leaf
    if top_class in ['Unknown', 'Not_a_leaf']:
        return {"diagnosis": "Not a supported leaf", "confidence": float(top_conf), "severity_ready": False,
                "message": "This does not look like a supported Maize, Tomato, or Potato leaf."}

    # 4. Safety Logic: Healthy
    if top_class in ['Maize_healthy', 'Potato_healthy', 'Tomato_healthy']:
        return {"diagnosis": top_class, "confidence": float(top_conf), "severity_ready": False,
                "message": "This leaf looks healthy! Keep up the good farming practices."}

    # 5. Safety Logic: Ambiguous between two diseases
    if (top_conf - second_conf) < 0.10 and second_class in disease_classes:
        return {"diagnosis": f"Ambiguous ({top_class} or {second_class})", "confidence": float(top_conf), "severity_ready": True,
                "message": "Confidence is split between two diseases. Please consult an extension officer."}

    # 6. Confirmed Disease
    return {"diagnosis": top_class, "confidence": float(top_conf), "severity_ready": True,
            "message": f"Detected {top_class.replace('_', ' ')} with {top_conf:.1%} confidence."}
""")
print("\nPhase 3 Complete! Review the threshold table above.")