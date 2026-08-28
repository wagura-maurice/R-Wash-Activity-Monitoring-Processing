#!/usr/bin/env python3
"""Scan data/images/ for non-standard image files and convert them to .jpg.

Non-standard extensions include .heic, .bmp, .tiff, .webp, .gif, etc.
Files already in .jpg or .jpeg are left untouched.  .png files are also
converted to .jpg for uniformity.

HEIC support requires the ``pillow-heif`` package:
    pip install pillow-heif

Usage:
    python src/007-convert_nonstandard_images.py            # convert + delete originals
    python src/007-convert_nonstandard_images.py --keep     # keep originals as backup
    python src/007-convert_nonstandard_images.py --dry-run  # report only, no changes
"""

import argparse
import os
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")

STANDARD_EXTS = {".jpg", ".jpeg"}
CONVERTIBLE_EXTS = {
    ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif",
    ".heic", ".heif", ".avif",
}


def convert_to_jpg(src_path, dst_path, quality=95):
    """Convert *src_path* to JPEG at *dst_path* with orientation correction.

    Returns True on success, False on failure.
    """
    try:
        with Image.open(src_path) as image:
            image = ImageOps.exif_transpose(image)

            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            image.save(dst_path, format="JPEG", quality=quality, optimize=True)
        return True
    except (OSError, ValueError, UnidentifiedImageError, NotImplementedError) as exc:
        print(f"  FAILED  {src_path.name}: {exc}", flush=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert non-standard image files in data/images/ to .jpg"
    )
    parser.add_argument(
        "--keep", action="store_true",
        help="Keep original files after conversion (do not delete).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be converted without making any changes.",
    )
    parser.add_argument(
        "--dir", default=IMAGES_DIR,
        help=f"Target directory (default: {IMAGES_DIR}).",
    )
    args = parser.parse_args()

    images_dir = Path(args.dir).resolve()
    if not images_dir.is_dir():
        print(f"Directory not found: {images_dir}", flush=True)
        return 1

    print(f"Scanning: {images_dir}", flush=True)

    standard_files = []
    convertible_files = []
    unknown_files = []

    for path in sorted(images_dir.iterdir()):
        if not path.is_file() or path.stat().st_size == 0:
            continue
        ext = path.suffix.lower()
        if ext in STANDARD_EXTS:
            standard_files.append(path)
        elif ext in CONVERTIBLE_EXTS:
            convertible_files.append(path)
        else:
            unknown_files.append(path)

    print(f"  Standard (.jpg/.jpeg):  {len(standard_files)}", flush=True)
    print(f"  Convertible:            {len(convertible_files)}", flush=True)
    if unknown_files:
        print(f"  Unknown (non-image):    {len(unknown_files)}", flush=True)

    if not convertible_files:
        print("No non-standard image files to convert.", flush=True)
        return 0

    heic_files = [p for p in convertible_files if p.suffix.lower() in {".heic", ".heif"}]
    if heic_files and not HEIF_AVAILABLE:
        print(
            f"\nWARNING: {len(heic_files)} HEIC/HEIF files found but `pillow-heif` is not installed.",
            flush=True,
        )
        print("  Install with: pip install pillow-heif", flush=True)
        print("  These files will be skipped.\n", flush=True)

    if args.dry_run:
        print("\n--- Dry run (no changes will be made) ---", flush=True)
        for path in convertible_files:
            dst = path.with_suffix(".jpg")
            if dst.exists():
                print(f"  WOULD CONVERT  {path.name} -> {dst.name} (dst already exists!)", flush=True)
            else:
                print(f"  WOULD CONVERT  {path.name} -> {dst.name}", flush=True)
        return 0

    converted = 0
    skipped = 0
    failed = 0

    for path in convertible_files:
        ext = path.suffix.lower()
        if ext in {".heic", ".heif"} and not HEIF_AVAILABLE:
            print(f"  SKIP    {path.name} (HEIC support not available)", flush=True)
            skipped += 1
            continue

        dst = path.with_suffix(".jpg")

        if dst.exists():
            print(f"  SKIP    {path.name} (target {dst.name} already exists)", flush=True)
            skipped += 1
            continue

        print(f"  CONVERT {path.name} -> {dst.name}", flush=True)
        if convert_to_jpg(path, dst):
            converted += 1
            if not args.keep:
                try:
                    path.unlink()
                except OSError as exc:
                    print(f"  WARNING  Could not delete original {path.name}: {exc}", flush=True)
        else:
            failed += 1
            if dst.exists():
                try:
                    dst.unlink()
                except OSError:
                    pass

    print(
        f"\n=== Conversion complete: "
        f"converted={converted}, skipped={skipped}, failed={failed} ===",
        flush=True,
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
