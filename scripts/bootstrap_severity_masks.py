"""Create reviewable pseudo lesion masks from Lab/texture rules and leaf GrabCut."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.severity import _lab_lesion_probabilities, segment_leaf  # noqa: E402


def bootstrap(source: Path, output: Path, manifest: Path) -> int:
    image_paths = sorted(
        path for path in source.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
    output.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with manifest.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["image_path", "leaf_mask_path", "lesion_mask_path", "review_status"],
        )
        writer.writeheader()
        for index, image_path in enumerate(image_paths):
            bgr = cv2.imread(str(image_path))
            if bgr is None:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            leaf_mask, _ = segment_leaf(rgb)
            lesion_mask, _ = _lab_lesion_probabilities(rgb, leaf_mask)
            leaf_path = output / f"{index:06d}_leaf.png"
            lesion_path = output / f"{index:06d}_lesion.png"
            cv2.imwrite(str(leaf_path), leaf_mask)
            cv2.imwrite(str(lesion_path), lesion_mask)
            writer.writerow(
                {
                    "image_path": image_path.resolve(),
                    "leaf_mask_path": leaf_path.resolve(),
                    "lesion_mask_path": lesion_path.resolve(),
                    "review_status": "pseudo_label_requires_manual_correction",
                }
            )
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Directory of leaf photos")
    parser.add_argument("--output", type=Path, default=Path("data/severity/pseudo_masks"))
    parser.add_argument("--manifest", type=Path, default=Path("data/severity/annotations.csv"))
    args = parser.parse_args()
    print(f"Wrote {bootstrap(args.source, args.output, args.manifest)} pseudo-mask pairs for manual correction")


if __name__ == "__main__":
    main()
