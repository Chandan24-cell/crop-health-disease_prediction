"""Extract PlantDoc's original test images with Windows-safe names and proposed labels."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import subprocess
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/field_sources/plantdoc_test"
MAPPING = ROOT / "data/plantdoc_field_test_proposals.csv"

# Conservative target mapping. Unsupported or ambiguous PlantDoc classes become Unknown.
TARGETS = {
    "Corn Gray leaf spot": "Maize_Gray_leaf_spot",
    "Corn rust leaf": "Maize_Common_rust",
    "Potato leaf early blight": "Potato_Early_blight",
    "Potato leaf late blight": "Potato_Late_blight",
    "Tomato Early blight leaf": "Tomato_Early_blight",
    "Tomato leaf late blight": "Tomato_Late_blight",
    "Tomato mold leaf": "Tomato_Leaf_Mold",
}


def extract(repo: Path) -> dict[str, int]:
    if not (repo / ".git").exists():
        raise FileNotFoundError("Fetch the PlantDoc repository first; see data/field_sources/README.md")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    listing = subprocess.check_output(["git", "ls-tree", "-r", "-z", "--name-only", "HEAD", "test"], cwd=repo)
    files = [part.decode("utf-8", errors="replace") for part in listing.split(b"\0") if part]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "LICENSE.txt").write_bytes(subprocess.check_output(["git", "show", "HEAD:LICENSE.txt"], cwd=repo))
    (OUTPUT / "README.md").write_text(
        f"PlantDoc source test images, commit `{commit}`. Proposed labels are not independently verified. "
        "See ../README.md for source, license, and split caveats.\n",
        encoding="utf-8",
    )
    counts: dict[str, int] = {}
    rows: list[dict[str, str]] = []
    for relative in files:
        match = re.match(r"test/(.+)/(.+)", relative)
        if not match:
            continue
        source_label, filename = match.groups()
        extension_match = re.search(r"\.(jpe?g|png)$", filename, re.IGNORECASE)
        if not extension_match:
            continue
        target_label = TARGETS.get(source_label, "Unknown")
        image_bytes = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=repo)
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError):
            continue
        digest = hashlib.sha256(image_bytes).hexdigest()
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).stem)[:60].strip("._") or "image"
        output_name = f"{digest[:10]}_{safe_stem}{extension_match.group(0).lower()}"
        output_path = OUTPUT / target_label / output_name
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        relpath = output_path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "source_path": relpath,
                "source_label": source_label,
                "target_label": target_label,
                "split": "field_test",
                "source_name": "PlantDoc",
                "source_version": commit,
                "label_verified": "no",
                "session_id": f"plantdoc_{digest[:16]}",
            }
        )
        counts[target_label] = counts.get(target_label, 0) + 1
    with MAPPING.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0])
            if rows
            else [
                "source_path",
                "source_label",
                "target_label",
                "split",
                "source_name",
                "source_version",
                "label_verified",
                "session_id",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=ROOT / "data/field_sources/PlantDoc-Dataset")
    args = parser.parse_args()
    print(extract(args.repo))


if __name__ == "__main__":
    main()
