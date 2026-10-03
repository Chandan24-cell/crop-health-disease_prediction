"""Register manually labeled field photos; held-out field_test never enters model manifests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
from pathlib import Path

from prepare_splits_v2 import IMAGE_EXTENSIONS, ROOT, perceptual_hash

LAB_MANIFEST = ROOT / "data/splits_v2.csv"
FIELD_ROOT = ROOT / "data/field_v2"
FIELD_TEST_MANIFEST = ROOT / "data/field_test_manifest.csv"


def register(mapping: Path) -> dict[str, int]:
    with mapping.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "source_path",
        "source_label",
        "target_label",
        "split",
        "source_name",
        "source_version",
        "label_verified",
        "session_id",
    }
    if rows and not required.issubset(rows[0]):
        raise ValueError(f"Mapping must contain columns: {sorted(required)}")
    if not LAB_MANIFEST.exists():
        raise FileNotFoundError("Create data/splits_v2.csv before registering field data")
    with LAB_MANIFEST.open(encoding="utf-8", newline="") as stream:
        lab_rows = list(csv.DictReader(stream))
    lab_hashes = [int(row["phash"]) for row in lab_rows if row.get("phash")]
    existing_keys = {(row["path"], row["split"]) for row in lab_rows}
    additions: list[dict[str, str]] = []
    field_test: list[dict[str, str]] = []
    counts: dict[str, int] = {"train": 0, "val": 0, "field_test": 0}
    field_hashes: list[int] = []
    skipped_duplicates = 0
    for row in rows:
        source = (ROOT / row["source_path"]).resolve()
        if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Missing/unsupported image: {row['source_path']}")
        if row["split"] not in {"train", "val", "field_test"}:
            raise ValueError("Field intake split must be train, val, or field_test")
        is_verified = row["label_verified"].strip().lower() in {"yes", "true", "1"}
        if row["split"] != "field_test" and not is_verified:
            raise ValueError(f"Training/validation disease labels must be human verified: {row['source_path']}")
        if not row["target_label"].strip() or not row["source_name"].strip() or not row["session_id"].strip():
            raise ValueError(f"Target label, source, and capture session are required: {row['source_path']}")
        if row["split"] != "field_test" and row["target_label"] not in {r["label"] for r in lab_rows}:
            raise ValueError(f"Training label absent from lab label set: {row['target_label']}")
        phash = perceptual_hash(source)
        if any((phash ^ value).bit_count() <= 6 for value in lab_hashes):
            if row["split"] == "field_test":
                skipped_duplicates += 1
                continue
            raise ValueError(f"Field train/val image resembles a lab image; keep independent: {row['source_path']}")
        if any((phash ^ value).bit_count() <= 6 for value in field_hashes):
            skipped_duplicates += 1
            continue
        field_hashes.append(phash)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        target = FIELD_ROOT / row["split"] / row["target_label"] / f"{digest[:12]}_{source.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        relative = target.relative_to(ROOT).as_posix()
        item = {
            "path": relative,
            "label": row["target_label"],
            "sha256": digest,
            "phash": str(phash),
            "group_id": f"field_{hashlib.sha1(row['session_id'].encode()).hexdigest()[:10]}",
            "source_name": row["source_name"],
            "source_version": row["source_version"],
            "source_label": row["source_label"],
            "session_id": row["session_id"],
            "label_verified": "yes" if is_verified else "no",
        }
        (field_test if row["split"] == "field_test" else additions).append(item)
        counts[row["split"]] += 1
    if additions:
        new_rows = [
            {key: value for key, value in row.items() if key in {"path", "label", "sha256", "phash", "group_id"}}
            | {"split": "train" if row["path"].split("/")[2] == "train" else "val"}
            for row in additions
        ]
        # Set split explicitly from the registered destination folder.
        for new_row in new_rows:
            parts = new_row["path"].split("/")
            new_row["split"] = parts[2]
        with LAB_MANIFEST.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["path", "label", "sha256", "phash", "group_id", "split"])
            writer.writerows(row for row in new_rows if (row["path"], row["split"]) not in existing_keys)
    if field_test:
        FIELD_TEST_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with FIELD_TEST_MANIFEST.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(field_test[0]))
            writer.writeheader()
            writer.writerows(field_test)
    counts["skipped_phash_duplicates"] = skipped_duplicates
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", type=Path, default=ROOT / "data/field_label_map.csv")
    args = parser.parse_args()
    print(register(args.mapping))


if __name__ == "__main__":
    main()
