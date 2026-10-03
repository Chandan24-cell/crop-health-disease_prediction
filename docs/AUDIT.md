# Project audit

Audit date: 2026-10-03 (Asia/Calcutta). No model, data, UI or knowledge-base behavior was changed. Artifacts added: `reports/baseline.json`, `reports/duplicates.json`, `docs/REPO_INVENTORY.md`, and `scripts/run_audit.py`.

## Repository tree

See [REPO_INVENTORY.md](REPO_INVENTORY.md) for the repository tree, descriptions of the project files, data split counts and generated-environment scope. The project contains 13,856 processed image files across train, validation and test; each is an input sample. `venv/` contains generated third-party files and is summarized rather than expanded.

## Baseline metrics

Metrics were reproduced on the existing **test** split using `models/crop_disease_model.keras`, 224×224 RGB images, class ordering from `models/class_names.json`, and the same directory loader convention used by the existing evaluator. The class order matched all 13 data directory classes.

- Accuracy: **95.43%** (1,986 / 2,081)
- Macro-F1: **0.9422**
- Precision, recall and F1 by class:

| Class | Precision | Recall | F1 | Test n |
|---|---:|---:|---:|---:|
| Maize_Common_rust | 1.000 | 0.994 | 0.997 | 179 |
| Maize_Gray_leaf_spot | 0.817 | 0.870 | 0.843 | 77 |
| Maize_Northern_Leaf_Blight | 0.931 | 0.912 | 0.922 | 148 |
| Maize_healthy | 0.994 | 1.000 | 0.997 | 175 |
| Not_a_leaf | 1.000 | 0.994 | 0.997 | 180 |
| Potato_Early_blight | 0.955 | 1.000 | 0.977 | 150 |
| Potato_Late_blight | 0.954 | 0.973 | 0.964 | 150 |
| Potato_healthy | 0.905 | 0.826 | 0.864 | 23 |
| Tomato_Early_blight | 0.908 | 0.853 | 0.880 | 150 |
| Tomato_Late_blight | 0.973 | 0.895 | 0.933 | 287 |
| Tomato_Leaf_Mold | 0.902 | 0.965 | 0.932 | 143 |
| Tomato_healthy | 0.960 | 1.000 | 0.980 | 239 |
| Unknown | 0.956 | 0.972 | 0.964 | 180 |

The full 13×13 confusion matrix, with labels on both axes, is in `reports/baseline.json`. Lowest recall is Potato_healthy (0.826, n=23), followed by Tomato_Early_blight (0.853, n=150) and Maize_Gray_leaf_spot (0.870, n=77). Gray leaf spot and Northern leaf blight account for 23 mutual errors: 10 true gray leaf spot images predicted as northern leaf blight and 13 in the reverse direction.

## Near-duplicate / leakage scan

Scanned all 13,856 processed images. Hash method: grayscale image resized to 32×32; 64-bit DCT pHash built from the 8×8 low-frequency block excluding DC, median threshold; a match is Hamming distance **≤ 6**. Reported leakage counts include only pairs crossing train/val/test boundaries (same-split similarity is not leakage for this audit). No images failed hashing.

- Cross-split near-duplicate pairs: **49**
- Distinct images involved: **94**
- Class counts below count unique images involved and matching pairs involving the class; cross-class pairs contribute to both class rows.

| Class | Images involved | Cross-split pairs |
|---|---:|---:|
| Maize_Common_rust | 0 | 0 |
| Maize_Gray_leaf_spot | 0 | 0 |
| Maize_Northern_Leaf_Blight | 0 | 0 |
| Maize_healthy | 0 | 0 |
| Not_a_leaf | 2 | 1 |
| Potato_Early_blight | 7 | 5 |
| Potato_Late_blight | 20 | 19 |
| Potato_healthy | 2 | 2 |
| Tomato_Early_blight | 1 | 1 |
| Tomato_Late_blight | 23 | 14 |
| Tomato_Leaf_Mold | 8 | 5 |
| Tomato_healthy | 13 | 8 |
| Unknown | 18 | 14 |

Pair-level paths, split, class and exact Hamming distance are in `reports/duplicates.json`. Review these matches before making any split changes; the scan is a candidate detector and does not delete or move data.

## Class-name alignment: model, knowledge base and UI

The model has 13 output classes. `models/knowledge_base.json` has eight keys. The UI (`app.py`) uses model labels directly for diagnosis, explicitly handles the three healthy labels and the `Unknown`/`Not_a_leaf` labels, and sends a severity-ready label to `get_recommendation`. Three healthy labels bypass the recommendation lookup. `Unknown` and `Not_a_leaf` bypass it in normal mode, but demo mode skips those safeguards and can reach the lookup, where advice is absent.

| Model class | KB key exists? | UI handling / finding |
|---|---|---|
| Maize_Common_rust | Yes | Disease prediction can reach advice lookup |
| Maize_Gray_leaf_spot | Yes | Disease prediction can reach advice lookup |
| Maize_Northern_Leaf_Blight | Yes | Disease prediction can reach advice lookup |
| Maize_healthy | No | Explicit healthy response; no advice lookup |
| Not_a_leaf | No | Normal mode returns unsupported-leaf response; demo mode may reach missing-key error |
| Potato_Early_blight | Yes | Disease prediction can reach advice lookup |
| Potato_Late_blight | Yes | Disease prediction can reach advice lookup |
| Potato_healthy | No | Explicit healthy response; no advice lookup |
| Tomato_Early_blight | Yes | Disease prediction can reach advice lookup |
| Tomato_Late_blight | Yes | Disease prediction can reach advice lookup |
| Tomato_Leaf_Mold | Yes | Disease prediction can reach advice lookup |
| Tomato_healthy | No | Explicit healthy response; no advice lookup |
| Unknown | No | Normal mode returns uncertain/unsupported response depending confidence; demo mode may reach missing-key error |

**Actual key mismatches:** `Maize_healthy`, `Potato_healthy`, `Tomato_healthy`, `Not_a_leaf`, and `Unknown` are model labels absent from the knowledge base. There are no extra knowledge-base keys outside the model output set. This explains why the fallback “Disease not found in knowledge base” can appear for the unsupported classes in demo mode; the three healthy classes currently avoid the lookup.

No class spelling mismatch was found among the eight disease labels shared by model and knowledge base. `app.py` derives disease candidate labels from the model list by excluding the five special labels; that exclusion set matches the current model labels. UI diagnosis text uses the raw model class string except for the unsupported/ambiguous branches.

## Prioritized fix list (recommendations only; no fixes applied)

1. **High — eliminate cross-split leakage.** Review the 49 pHash candidate pairs and assign each source image/near-duplicate family to one split, then retrain and recompute an untouched holdout score. Preserve original data until reviewed.
2. **High — prevent unsupported outputs from being treated as diseases.** Define intended UI outcomes for `Unknown` and `Not_a_leaf`, including demo mode, so these labels do not produce disease severity estimates or misleading advice errors.
3. **High — validate severity measurement.** Replace or calibrate HSV-only severity against expert-labeled lesion masks/area; report uncertainty and verify whole-leaf outlines do not count as damage.
4. **Medium — improve weak class performance and coverage.** Prioritize Maize gray leaf spot/Northern leaf blight separation and Tomato early blight recall; increase/validate Potato healthy representation (only 23 test images, 106 train) and use per-class metrics.
5. **Medium — align training and inference preprocessing.** Verify the app's RGB 0–255 tensor handling against training's in-model `mobilenet_v2.preprocess_input`; add a fixed inference contract and regression examples before changing behavior.
6. **Medium — harden the advice mapping.** Ensure every diagnosis value that can reach the recommendation lookup has a deliberate result, and add a mapping completeness check for class names versus KB keys.
7. **Low — make evaluation reproducible.** Keep the generated JSON report, record dataset/model hashes and environment versions, and separate threshold tuning from the final holdout evaluation.

## Scope notes

This step only audited and generated reports/documentation. No source behavior or data was modified, and nothing was deleted.
