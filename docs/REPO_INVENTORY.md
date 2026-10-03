# Repository inventory

Root: `C:\Users\Saurav Shah\crop-health-app`. The local virtual environment is intentionally summarized rather than expanded (its installed package files are generated dependencies, not project source).

```text
crop-health-app/
├── app.py — Streamlit application: image checks, predictions, severity and advice
├── requirements.txt — Python runtime dependencies
├── temp_uploaded_image.jpg — scratch image written by the running UI
├── data/
│   └── processed/{train,val,test}/<class>/*.jpg — labeled image samples; every image is a source example
├── demo_images/
│   ├── 1_diseased_tomato.jpg — demo diseased tomato sample
│   ├── 2_healthy_maize.jpg — demo healthy maize sample
│   ├── 3_unknown_leaf.jpg — demo unsupported/unknown leaf sample
│   └── 4_not_a_leaf.jpg — demo non-leaf sample
├── models/
│   ├── best_model.keras — best validation checkpoint
│   ├── class_names.json — output-index to class-name order
│   ├── confusion_matrix.png — previously generated confusion matrix image
│   ├── crop_disease_model.keras — model loaded by the app and evaluator
│   ├── import streamlit as st.py — extra Streamlit app copy with an anomalous filename
│   └── knowledge_base.json — management guidance keyed by disease class
├── reports/
│   ├── baseline.json — test split metrics and confusion matrix from this audit
│   └── duplicates.json — all cross-split pHash matches and class counts
├── scripts/
│   ├── build_knowledge_base.py — defines/builds advice data and recommendation lookup
│   ├── check_folders.py — checks expected data folder layout
│   ├── evaluate_and_tune.py — test metrics, confusion-matrix image and validation threshold analysis
│   ├── find_data.py — locates candidate dataset files/directories
│   ├── prepare_demo_images.py — prepares demo image assets
│   ├── run_audit.py — reproducible baseline and pHash audit runner added for this step
│   ├── setup_data.py — downloads/assembles and partitions dataset
│   ├── severity_estimator.py — HSV-based disease severity estimate and overlay
│   ├── train_model.py — MobileNetV2 training and fine-tuning pipeline
│   └── verify_data.py — checks dataset contents
├── test_severity_output/*.jpg — five saved severity-overlay examples
└── venv/ — local Python virtual environment (generated third-party files; omitted)
```

`data/processed` contains 13 class folders in each of train, val and test. Counts by split, in class order from `models/class_names.json`:

| Class | Train | Val | Test |
|---|---:|---:|---:|
| Maize_Common_rust | 834 | 179 | 179 |
| Maize_Gray_leaf_spot | 359 | 77 | 77 |
| Maize_Northern_Leaf_Blight | 689 | 148 | 148 |
| Maize_healthy | 813 | 174 | 175 |
| Not_a_leaf | 840 | 180 | 180 |
| Potato_Early_blight | 700 | 150 | 150 |
| Potato_Late_blight | 700 | 150 | 150 |
| Potato_healthy | 106 | 23 | 23 |
| Tomato_Early_blight | 700 | 150 | 150 |
| Tomato_Late_blight | 1,336 | 286 | 287 |
| Tomato_Leaf_Mold | 666 | 143 | 143 |
| Tomato_healthy | 1,113 | 239 | 239 |
| Unknown | 840 | 180 | 180 |

The 13,856 dataset image files are not individually named in this text tree; they are enumerated with paths and duplicate matches in the dataset/report artifacts.
