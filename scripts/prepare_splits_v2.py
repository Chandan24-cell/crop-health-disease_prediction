"""Create reproducible phash-clustered 70/15/15 manifests without moving source images."""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SPLIT_NAMES = ("train", "val", "test")
SPLIT_RATIOS = (0.70, 0.15, 0.15)


def perceptual_hash(path: Path) -> int:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Cannot decode image: {path}")
    resized = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    dct = cv2.dct(resized)[:8, :8].reshape(-1)
    median = float(np.median(dct[1:]))
    value = 0
    for bit in dct:
        value = (value << 1) | int(bit > median)
    return value


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def cluster_hashes(hashes: list[int], distance: int = 6) -> list[int]:
    """Connected components over close pHashes using an 8-band candidate index."""
    parent = list(range(len(hashes)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    bands: list[dict[int, list[int]]] = [defaultdict(list) for _ in range(8)]
    for index, value in enumerate(hashes):
        candidates: set[int] = set()
        for band_index, band in enumerate(bands):
            chunk = (value >> (band_index * 8)) & 0xFF
            candidates.update(band.get(chunk, ()))
        for candidate in candidates:
            if _hamming(value, hashes[candidate]) <= distance:
                union(index, candidate)
        for band_index, band in enumerate(bands):
            band[(value >> (band_index * 8)) & 0xFF].append(index)
    root_ids: dict[int, int] = {}
    return [root_ids.setdefault(find(index), len(root_ids)) for index in range(len(hashes))]


def _assign_groups(labels: list[str], groups: list[int], seed: int) -> list[str]:
    class_names = sorted(set(labels))
    class_index = {name: index for index, name in enumerate(class_names)}
    vectors: dict[int, np.ndarray] = {}
    rng = random.Random(seed)
    for label, group in zip(labels, groups, strict=True):
        vectors.setdefault(group, np.zeros(len(class_names), dtype=np.float64))[class_index[label]] += 1
    target_class = np.array([labels.count(name) for name in class_names], dtype=np.float64)
    targets = [target_class * ratio for ratio in SPLIT_RATIOS]
    assigned = [np.zeros_like(target_class) for _ in SPLIT_RATIOS]
    order = list(vectors)
    rng.shuffle(order)
    order.sort(
        key=lambda group: (float(np.max(vectors[group] / np.maximum(target_class, 1))), float(vectors[group].sum())),
        reverse=True,
    )
    group_split: dict[int, str] = {}
    for group in order:
        vector = vectors[group]
        costs: list[float] = []
        for split_index in range(3):
            trial = [values.copy() for values in assigned]
            trial[split_index] += vector
            class_cost = sum(
                float(np.square((trial[i] - targets[i]) / np.maximum(target_class, 1)).sum()) for i in range(3)
            )
            size_cost = sum(
                (
                    (float(trial[i].sum()) - float(target_class.sum()) * SPLIT_RATIOS[i])
                    / max(float(target_class.sum()), 1)
                )
                ** 2
                for i in range(3)
            )
            costs.append(class_cost + size_cost)
        best = min(range(3), key=lambda index: costs[index])
        assigned[best] += vector
        group_split[group] = SPLIT_NAMES[best]
    return [group_split[group] for group in groups]


def build_manifest(data_root: Path, output: Path, seed: int = 2026) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for path in sorted(data_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        if "field_test" in path.parts or "field_sources" in path.parts:
            continue
        label = path.parent.name
        if label not in {"train", "val", "test"} and path.parent.parent.name in {"train", "val", "test"}:
            label = path.parent.name
        elif path.parent.name in {"train", "val", "test"}:
            continue
        if label.lower() in SPLIT_NAMES:
            continue
        try:
            phash = perceptual_hash(path)
        except (ValueError, cv2.error) as exc:
            print(f"Skipping unreadable image {path}: {exc}")
            continue
        records.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "label": label,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "phash": phash,
            }
        )
    if not records:
        raise RuntimeError(f"No class-folder images found below {data_root}")
    group_ids = cluster_hashes([int(record["phash"]) for record in records])
    split_names = _assign_groups([str(record["label"]) for record in records], group_ids, seed)
    for record, group_id, split in zip(records, group_ids, split_names, strict=True):
        record.update({"group_id": f"ph_{group_id:06d}", "split": split})
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "label", "sha256", "phash", "group_id", "split"])
        writer.writeheader()
        writer.writerows(records)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--output", type=Path, default=ROOT / "data/splits_v2.csv")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    records = build_manifest(args.data_root, args.output, args.seed)
    print(f"Wrote {len(records)} images to {args.output}")
    for split in SPLIT_NAMES:
        class_counts: dict[str, int] = defaultdict(int)
        for record in records:
            if record["split"] == split:
                class_counts[str(record["label"])] += 1
        group_count = len({record["group_id"] for record in records if record["split"] == split})
        print(f"{split}: {sum(class_counts.values())} images / {group_count} groups")
        for label, count in sorted(class_counts.items()):
            print(f"  {label}: {count}")


if __name__ == "__main__":
    main()
