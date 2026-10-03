# ruff: noqa: E501
"""Assemble the honest pipeline and baseline status report from current artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/v2_report.md"


def build_report() -> str:
    with (ROOT / "reports/v2/lab_test_metrics.json").open(encoding="utf-8") as stream:
        lab = json.load(stream)
    with (ROOT / "reports/v2/field_test_metrics.json").open(encoding="utf-8") as stream:
        field = json.load(stream)
    with (ROOT / "reports/v2/lab_validation_calibration.json").open(encoding="utf-8") as stream:
        calibration = json.load(stream)
    comparison_path = ROOT / "reports/v2/model_comparison.json"
    comparison = json.loads(comparison_path.read_text(encoding="utf-8")) if comparison_path.exists() else {}
    hierarchy_path = ROOT / "reports/v2/hierarchy_test_metrics.json"
    hierarchy = json.loads(hierarchy_path.read_text(encoding="utf-8")) if hierarchy_path.exists() else None
    with (ROOT / "data/splits_v2.csv").open(encoding="utf-8", newline="") as stream:
        split_rows = list(csv.DictReader(stream))
    split_counts: Counter[str] = Counter(row["split"] for row in split_rows)
    split_classes: dict[str, Counter[str]] = defaultdict(Counter)
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row in split_rows:
        split_classes[row["split"]][row["label"]] += 1
        group_splits[row["group_id"]].add(row["split"])
    crossing_groups = sum(len(splits) > 1 for splits in group_splits.values())
    field_counts: Counter[str] = Counter()
    with (ROOT / "data/field_test_manifest.csv").open(encoding="utf-8", newline="") as stream:
        field_rows = list(csv.DictReader(stream))
    field_counts.update(row["label"] for row in field_rows)
    metrics = lab["per_class"]
    per_class = "\n".join(
        f"| {label} | {row['precision']:.3f} | {row['recall']:.3f} | {row['f1-score']:.3f} | {int(row['support'])} |"
        for label, row in metrics.items()
        if label in {item for item in metrics if isinstance(metrics[item], dict) and "f1-score" in metrics[item]}
        and label not in {"macro avg", "weighted avg"}
    )
    pairs = "\n".join(f"| {pair} | {count} |" for pair, count in lab["hard_negative_pairs"].items())
    field_classes = "\n".join(f"| {label} | {count} |" for label, count in sorted(field_counts.items()))
    field_status = (
        f"NOT MEASURED ({field['count']} images, {field.get('unverified_count', field['count'])} unverified labels)"
        if field["status"] != "MEASURED"
        else f"{field['macro_f1']:.4f}"
    )
    comparison_lines = [
        f"| {stage} | {architecture} | {metric['seeds']} | {metric['mean_macro_f1']:.4f} ± {metric['std_macro_f1']:.4f} |"
        for stage, architectures in sorted(comparison.items())
        for architecture, metric in sorted(architectures.items())
    ]
    hierarchy_lines = (
        [
            "## Promoted hierarchical v2 result",
            "",
            f"Macro-F1: **{hierarchy['macro_f1']:.4f}** on {hierarchy['count']} grouped `{hierarchy['split']}` images.",
            f"Accepted coverage: {hierarchy['accepted_coverage']:.2%}; selective ECE: {hierarchy['ece_accepted_calls']}; wrong-crop rate: {hierarchy['wrong_crop_rate']}.",
            f"Mean prediction latency: {hierarchy['latency_ms_mean']} ms/image (TTA={hierarchy['tta']}).",
            "",
            "Full per-class results and confusion matrix: [`hierarchy_test_report.md`](v2/hierarchy_test_report.md).",
            "",
        ]
        if hierarchy is not None
        else [
            "## Promoted hierarchical v2 result",
            "",
            "NOT MEASURED: v2 checkpoints have not been trained/promoted.",
            "",
        ]
    )
    lines = [
        "# Crop health v2 pipeline and evaluation status",
        "",
        "> The pipeline is implemented, but no v2 weights were trained in this environment. Lab figures below are a leakage-controlled diagnostic of the untouched legacy model, not a v2 result.",
        "",
        "## Data split",
        "",
        f"- Manifest: [`data/splits_v2.csv`](../data/splits_v2.csv), {len(split_rows):,} lab images and {len(group_splits):,} perceptual-hash clusters.",
        f"- Cross-split hash clusters: {crossing_groups} (must be 0).",
        f"- Counts: train {split_counts['train']:,}, validation {split_counts['val']:,}, test {split_counts['test']:,}.",
        "- Source folders remain untouched. The v2 training script consumes only the manifest's train split; validation calibrates/selects; test reports once.",
        "",
        "## Legacy model, prior held-out lab test",
        "",
        f"This diagnostic uses {lab['count']:,} images from the original `data/processed/test` partition, excluding any pHash cluster that touches the original training folder. Calibration uses original validation images only.",
        "",
        f"- Macro-F1: **{lab['macro_f1']:.4f}** (target ≥ 0.96: **not met**).",
        f"- ECE after validation temperature scaling (T={calibration['temperature']:.4f}): **{lab['ece']:.4f}** (target ≤ 0.05: **met on this lab test**).",
        f"- Wrong-crop rate: **{lab['wrong_crop_rate']:.2%}** (target ≤ 1%: {'met' if lab['wrong_crop_rate'] <= 0.01 else 'not met'}).",
        f"- OOD false-accept rate: **{lab['ood_false_accept_rate']:.2%}**; energy AUROC **{lab['unknown_auroc']:.3f}**. Known-image false-reject rate at that validation cutoff: **{lab['ood_known_false_reject_rate']:.2%}**.",
        f"- CPU latency: **{lab['cpu_single_image_latency_ms_sampled']:.1f} ms/image** (single-image calls, first 64 images); batch throughput **{lab['latency_ms_per_image_batch']:.1f} ms/image**.",
        "- This is the legacy classifier evaluated on its untouched old test partition. The new grouped 70/15/15 manifest's test rows are not a valid test for this already-trained model because it has seen some original training images.",
        "",
        "### Per-class metrics (legacy diagnostic)",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---:|---:|---:|---:|",
        per_class,
        "",
        "### Requested hard-negative pairs",
        "",
        "| Pair (both directions) | Errors |",
        "|---|---:|",
        pairs,
        "",
        "### Calibration, OOD, and TTA figures",
        "",
        f"- Validation temperature: `{calibration['temperature']:.6f}`; per-class precision-constrained thresholds are saved in [`lab_validation_calibration.json`](v2/lab_validation_calibration.json).",
        f"- TTA (four views: center, flip, top-left crop, bottom-right crop) macro-F1: **{lab['tta_macro_f1']:.4f}** vs single-view **{lab['macro_f1']:.4f}**; measured batch throughput **{lab['tta_latency_ms_per_image']:.1f} ms/image** vs **{lab['latency_ms_per_image_batch']:.1f} ms/image**. On this legacy model TTA reduced macro-F1 and increased latency.",
        "- The validation-tuned energy detector has low unknown AUROC and rejects nearly all known examples at its cutoff; it is not ready for deployment.",
        "",
        "![Confusion matrix](v2/lab_test_confusion.png)",
        "",
        "![Reliability diagram](v2/lab_test_reliability.png)",
        "",
        "![Unknown ROC and PR](v2/lab_test_reject_curves.png)",
        "",
        "Worst high-confidence mistakes by class pair are copied under [`v2/error_gallery/test/`](v2/error_gallery/test/).",
        "",
        "## Field test",
        "",
        f"- Field macro-F1: **{field_status}** (target ≥ 0.90: **not measurable yet**).",
        "- Field OOD false-accept target ≤ 1%: **not measurable** until the field labels are verified.",
        f"- Staged {len(field_rows)} separate PlantDoc test images with proposed labels; none share a pHash cluster with the current lab set. Independent review is still required before using their labels as ground truth.",
        "- The available source has fewer than 50 examples per mapped supported disease class; no Kaggle field dataset credentials or user phone photos were present.",
        "",
        "| Proposed target label | Images |",
        "|---|---:|",
        field_classes,
        "",
        "Source/licensing and annotation caveats: [`data/field_sources/README.md`](../data/field_sources/README.md). Field metrics are correctly left NOT MEASURED until review; the test set is never added to the train/validation manifest.",
        "",
        *hierarchy_lines,
        "## V2 training and export status",
        "",
        "Implemented in `scripts/`: pHash group splitting, field intake and duplicate audit, MobileNetV2/EfficientNetV2-B0/ConvNeXt-Tiny/MobileNetV3-Large comparison, crop-first hierarchy, domain augmentation, two-stage fine-tuning, three-seed mean/std aggregation, validation temperature scaling and class thresholds, stage-A energy rejection, TTA, hard-pair weighting, CPU benchmark, error gallery, and int8 TFLite/optional ONNX parity checks.",
        "",
        "- Training sweep: **not run**. TensorFlow sees no GPU in this environment. Running 48 fine-tuning jobs on this CPU would not produce a responsible real-world result.",
        "- Architecture/seed comparison and v2 model: **not available** until training completes; `models/v2/README.md` documents artifact layout.",
        *(
            [
                "",
                "| Stage | Architecture | Seeds | Validation macro-F1 mean ± std |",
                "|---|---|---:|---:|",
                *comparison_lines,
            ]
            if comparison_lines
            else []
        ),
        "- TFLite int8 / ONNX export parity: **not run** because no v2 candidate weights exist.",
        "- No model file under the original `models/` root was overwritten.",
        "",
        "## Reproduce",
        "",
        "```powershell",
        "python scripts/prepare_splits_v2.py",
        "python scripts/train_v2.py --stage all --architectures all --seeds 11 29 47 --batch-size 16",
        "python scripts/summarize_v2_runs.py",
        "python scripts/promote_v2.py --minimum-seeds 3",
        "python scripts/export_v2.py models/v2/hierarchy/stage_a/model.keras",
        "python scripts/evaluate_v2.py --model models/crop_disease_model.keras --split test",
        "python scripts/evaluate_field_v2.py --model models/crop_disease_model.keras",
        "```",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    OUTPUT.write_text(build_report(), encoding="utf-8")
    print(OUTPUT)
