# Model Card: Fieldnote Crop Health Dual-Backbone Classifier

## Model Overview
- **Model Name:** Fieldnote Crop Health Classifier v2
- **Model Architecture:** Dual-Backbone Ensemble / Selective Routing with MobileNetV3-Large (primary lightweight edge/cloud backbone) and EfficientNet-B0 (high-accuracy deep feature extractor).
- **Primary Task:** Multi-class classification of foliar diseases in Solanaceae family crops (Tomato & Potato), coupled with Platt temperature scaling calibration, blur/quality rejection, and Grad-CAM++ saliency mapping.
- **Framework:** TensorFlow / Keras 2.15, ONNX Runtime (for WASM edge deployment).
- **Model Version:** 2.1.0
- **Release Date:** October 2026
- **License:** Apache 2.0

---

## Intended Use & Target Users
- **Primary Intended Use:** Rapid, farmer-first triage and decision-support for smallholder farmers, agricultural extension workers, and crop consultants in East Africa and South Asia.
- **Supported Crops:**
  - **Tomato (*Solanum lycopersicum*)**
  - **Potato (*Solanum tuberosum*)**
- **Supported Disease Classes:**
  1. `tomato_early_blight` (*Alternaria solani*)
  2. `tomato_late_blight` (*Phytophthora infestans*)
  3. `tomato_leaf_mold` (*Passalora fulva*)
  4. `tomato_septoria_leaf_spot` (*Septoria lycopersici*)
  5. `tomato_spider_mites_two_spotted` (*Tetranychus urticae*)
  6. `tomato_target_spot` (*Corynespora cassiicola*)
  7. `tomato_yellow_leaf_curl_virus` (TYLCV)
  8. `potato_early_blight` (*Alternaria solani*)
  9. `potato_late_blight` (*Phytophthora infestans*)
  10. `tomato_healthy` / `potato_healthy`

---

## Training & Validation Datasets
1. **PlantVillage Dataset:**
   - 54,303 curated laboratory-condition leaf images across diverse Solanaceae conditions.
2. **PlantDoc Field Test Dataset:**
   - Real-world in-field images featuring complex agricultural backgrounds, varying sunlight conditions, dirt, shadow occlusions, and multi-leaf foliage.
3. **Data Augmentations:**
   - Color jittering (brightness ±20%, contrast ±15%), affine transformations, random rotations (±30°), random crops, and synthetic blur/illumination gradients.

---

## Quantitative Performance Metrics

### Test Set Performance (Field-Grounded Validation)
| Metric | Laboratory Split | In-Field Test Split | CI Regression Baseline Gate |
| :--- | :--- | :--- | :--- |
| **Top-1 Accuracy** | 98.6% | 86.4% | >= 80.0% |
| **Macro-F1 Score** | 0.982 | 0.842 | >= 0.800 |
| **Top-2 Accuracy** | 99.8% | 94.1% | >= 90.0% |
| **Expected Calibration Error (ECE)** | 0.021 | 0.048 | <= 0.080 |
| **p95 CPU Inference Latency** | 42 ms | 56 ms | < 800 ms |

### Class-Specific F1-Scores on Field Data
- `tomato_late_blight`: 0.88
- `tomato_early_blight`: 0.84
- `tomato_yellow_leaf_curl_virus`: 0.89
- `tomato_septoria_leaf_spot`: 0.82
- `potato_late_blight`: 0.87
- `potato_early_blight`: 0.81
- `healthy_leaves`: 0.91

---

## Confidence Calibration & Quality Gate
- **Platt Temperature Scaling ($T = 1.34$):** Raw logits are divided by learned temperature parameter $T$ before softmax to mitigate overconfidence on out-of-distribution in-field images.
- **Quality Gate:** Images with Laplacian variance $< 40.0$ are flagged as blurry (`is_blurry: true`); mean brightness values $< 30$ or $> 225$ trigger illumination warnings to prompt farmers for retakes.

---

## Explainability & Saliency (Grad-CAM++)
- Visual explanations are computed using Grad-CAM++ targeting the final convolutional layer (`Conv_1` in MobileNetV3).
- Positive gradients quantify spatial importance, rendered as normalized heatmap overlays with jet colormaps to verify that predictions stem from genuine foliar lesions rather than soil or background artifacts.

---

## Out-of-Scope & Limitations
1. **Decision Support Only:** This model provides triage support; it does not replace certified laboratory PCR, fungal culturing, or on-site agronomist inspections.
2. **Lookalike Abiotic Stresses:** Abiotic disorders (e.g., severe magnesium/potassium deficiency, chemical spray burn, herbicide drift, or moisture stress) can produce visual necrotic patterns resembling fungal blights.
3. **Non-Supported Crops & Organs:** The model is strictly trained on tomato and potato foliage. Stems, fruits, roots, tubers, or other crops (e.g., maize, cassava) will result in unreliable predictions.
4. **Lighting Extremes:** Images taken in direct harsh midday glare or severe underexposure may degrade diagnostic accuracy.
