# Lesion segmentation annotations

There are currently no manually corrected lesion masks in this repository. HSV/Lab pseudo-masks are not ground truth and must not be counted as validation or test annotations.

To bootstrap review images:

```powershell
python scripts/bootstrap_severity_masks.py data/leaf_photos
```

Manually correct the saved leaf and lesion masks. Keep train/validation/test split assignments separated by source image (and perceptual-hash group). The CSV must contain `image_path,leaf_mask_path,lesion_mask_path,split,review_status`; use `review_status=corrected` or `verified`. Reserve at least 100 independently corrected images in `split=test` before reporting metrics.

Train on corrected train rows and validate on corrected validation rows:

```powershell
python scripts/train_severity_unet.py --annotations data/severity/annotations.csv
python scripts/evaluate_severity.py --annotations data/severity/annotations.csv
```

The optional model path is `models/severity/lesion_unet.keras`. The API uses it when present and otherwise applies the leaf-masked Lab/texture fallback.
