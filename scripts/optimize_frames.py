from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

FRAME_COUNT = 180
DEFAULT_SOURCE = Path("frontend/assets/leaf-sequence")


def optimize_frames(source: Path, max_mobile_width: int = 720) -> None:
    png_paths = sorted(source.glob("ezgif-frame-*.png"))
    expected_names = {f"ezgif-frame-{index:03}.png" for index in range(1, FRAME_COUNT + 1)}
    actual_names = {path.name for path in png_paths}
    missing = sorted(expected_names - actual_names)
    extra = sorted(actual_names - expected_names)
    print(f"Source PNGs: {len(png_paths)} / {FRAME_COUNT}")
    print(f"Missing frames: {', '.join(missing) if missing else 'none'}")
    print(f"Unexpected frames: {', '.join(extra) if extra else 'none'}")
    if missing or extra:
        raise SystemExit("The source sequence must contain exactly frames 001 through 180.")

    desktop_dir = source / "webp"
    mobile_dir = source / "webp-mobile"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    mobile_dir.mkdir(parents=True, exist_ok=True)
    source_size = sum(path.stat().st_size for path in png_paths)
    desktop_size = 0
    mobile_size = 0
    dimensions: set[tuple[int, int]] = set()
    has_transparency = False

    for index, png_path in enumerate(png_paths, start=1):
        with Image.open(png_path) as opened:
            image = opened.copy()
            has_alpha = "A" in opened.getbands() or "transparency" in opened.info
        dimensions.add(image.size)
        if has_alpha:
            rgba_image = image.convert("RGBA")
            alpha = rgba_image.getchannel("A")
            if alpha.getextrema()[0] < 255:
                has_transparency = True
            alpha.close()
            image.close()
            image = rgba_image
        else:
            image = image.convert("RGB")

        desktop_path = desktop_dir / f"frame-{index:03}.webp"
        image.save(desktop_path, format="WEBP", quality=80, method=6)
        desktop_size += desktop_path.stat().st_size

        mobile_width = min(max_mobile_width, max(1, image.width // 2))
        mobile_height = max(1, round(image.height * mobile_width / image.width))
        mobile_image = image.resize((mobile_width, mobile_height), Image.Resampling.LANCZOS)
        mobile_path = mobile_dir / f"frame-{index:03}.webp"
        mobile_image.save(mobile_path, format="WEBP", quality=80, method=6)
        mobile_size += mobile_path.stat().st_size
        image.close()
        mobile_image.close()

    dimension_report = ", ".join(f"{width}x{height}" for width, height in sorted(dimensions))
    print(f"Frame dimensions: {dimension_report}")
    print(f"PNG transparency present: {'yes' if has_transparency else 'no'}")
    print(f"Source PNG total: {source_size / 1_048_576:.2f} MB")
    print(f"Desktop WebP total: {desktop_size / 1_048_576:.2f} MB")
    print(f"Mobile WebP total: {mobile_size / 1_048_576:.2f} MB")
    print(f"All optimized WebP total: {(desktop_size + mobile_size) / 1_048_576:.2f} MB")
    print(f"Size reduction (source PNGs to both sets): {100 * (1 - (desktop_size + mobile_size) / source_size):.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize the exploded leaf PNG sequence as WebP.")
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--max-mobile-width", type=int, default=720)
    arguments = parser.parse_args()
    optimize_frames(arguments.source, arguments.max_mobile_width)