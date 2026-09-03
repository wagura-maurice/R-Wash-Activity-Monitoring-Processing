#!/usr/bin/env python3
"""Scan data/images/ for non-standard image files and convert them to .jpg.

This script handles image standardization by:
- Converting all non-standard image formats (.heic, .bmp, .tiff, .webp, .gif, etc.) to .jpg
- Applying EXIF orientation correction to ensure all images are oriented upright
- Converting .png files to .jpg for uniformity (unless transparent)
- Using a processing log to avoid reprocessing already-processed files

Files already in .jpg or .jpeg are left untouched but still receive orientation correction.
The script maintains a processing log (data/image_processing_log.json) to track which files
have been processed, avoiding redundant work on subsequent runs.

HEIC/HEIF files require the ``pillow-heif`` package. The script will attempt to install
it automatically when HEIC files are detected, or you can install it manually:
    pip install pillow-heif

Usage:
    python src/007-convert_nonstandard_images.py            # normal processing with log
    python src/007-convert_nonstandard_images.py --keep     # keep originals as backup
    python src/007-convert_nonstandard_images.py --dry-run  # report only, no changes
    python src/007-convert_nonstandard_images.py --force    # force reprocess all files
    python src/007-convert_nonstandard_images.py --clear-log # clear log before processing
    python src/007-convert_nonstandard_images.py --no-heic  # skip HEIC/HEIF files even if pillow-heif available
    
Note: HEIC/HEIF files require pillow-heif. The script will attempt to install it automatically
if HEIC files are found, or you can install it manually: pip install pillow-heif
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError
from email_notifier import send_success_email, send_failure_email, send_partial_success_email

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except ImportError:
    HEIF_AVAILABLE = False


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
LOG_FILE = os.path.join(BASE_DIR, "data", "image_processing_log.json")


def _install_pillow_heif():
    """Attempt to install pillow-heif package automatically."""
    print("Attempting to install pillow-heif for HEIC/HEIF support...", flush=True)
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow-heif"])
        print("Successfully installed pillow-heif", flush=True)
        return True
    except subprocess.CalledProcessError as exc:
        print(f"Failed to install pillow-heif: {exc}", flush=True)
        return False
    except Exception as exc:
        print(f"Error installing pillow-heif: {exc}", flush=True)
        return False


def _ensure_heif_support():
    """Ensure HEIF/HEIC support is available, install if possible."""
    global HEIF_AVAILABLE
    
    if HEIF_AVAILABLE:
        return True
    
    print("\n=== HEIC/HEIF Support Required ===", flush=True)
    print("HEIC/HEIF files found but pillow-heif is not installed.", flush=True)
    
    # Try to install automatically
    if _install_pillow_heif():
        # Try to import again
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            HEIF_AVAILABLE = True
            print("HEIC/HEIF support is now available.", flush=True)
            return True
        except ImportError:
            print("Still unable to import pillow-heif after installation.", flush=True)
    
    # If automatic installation failed, provide manual instructions
    print("\nManual installation required:", flush=True)
    print("  pip install pillow-heif", flush=True)
    print("\nOr install all project dependencies:", flush=True)
    print("  pip install -r requirements.txt", flush=True)
    return False


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(BASE_DIR, "data", "images")
LOG_FILE = os.path.join(BASE_DIR, "data", "image_processing_log.json")

STANDARD_EXTS = {".jpg", ".jpeg"}
CONVERTIBLE_EXTS = {
    ".png", ".webp", ".bmp", ".gif", ".tiff", ".tif",
    ".heic", ".heif", ".avif",
}


def _calculate_file_hash(file_path):
    """Calculate MD5 hash of a file for change detection."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _load_processing_log():
    """Load the processing log from disk."""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_processing_log(log):
    """Save the processing log to disk."""
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(log, f, indent=2)
    except IOError as exc:
        print(f"  WARNING  Could not save processing log: {exc}", flush=True)


def _is_file_processed(file_path, log, force_reprocess=False):
    """Check if a file has already been processed.
    
    Returns tuple (is_processed, reason).
    """
    if force_reprocess:
        return False, "force reprocess"
    
    file_key = str(file_path)
    if file_key not in log:
        return False, "not in log"
    
    entry = log[file_key]
    current_hash = _calculate_file_hash(file_path)
    
    if entry.get('file_hash') != current_hash:
        return False, "file modified"
    
    return True, f"processed on {entry.get('timestamp')}"


def _mark_file_processed(file_path, processing_type, log):
    """Mark a file as processed in the log."""
    file_key = str(file_path)
    log[file_key] = {
        'timestamp': datetime.now().isoformat(),
        'file_hash': _calculate_file_hash(file_path),
        'processing_type': processing_type,
        'file_size': file_path.stat().st_size
    }


def _apply_exif_orientation(image):
    """Apply EXIF orientation correction to image using ImageOps.exif_transpose.
    
    This function uses the same approach as the odk-middleman project to ensure
    consistent image orientation handling across the pipeline.
    """
    return ImageOps.exif_transpose(image)


def convert_to_jpg(src_path, dst_path, quality=95):
    """Convert *src_path* to JPEG at *dst_path* with orientation correction.

    Applies EXIF orientation correction to ensure images are displayed correctly.
    Handles transparent PNGs by keeping them as PNG rather than converting to JPEG.

    Returns True on success, False on failure.
    """
    try:
        with Image.open(src_path) as image:
            # Apply EXIF orientation correction (from odk-middleman logic)
            image = _apply_exif_orientation(image)

            # Check if image has transparency (PNG specific)
            if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
                # Keep as PNG if transparent, just optimize with orientation correction
                image.save(dst_path, format="PNG", optimize=True)
                return True

            # Convert to RGB for JPEG output
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")

            image.save(dst_path, format="JPEG", quality=quality, optimize=True)
        return True
    except (OSError, ValueError, UnidentifiedImageError, NotImplementedError) as exc:
        print(f"  FAILED  {src_path.name}: {exc}", flush=True)
        return False


def convert_and_log(src_path, dst_path, log, force_reprocess, quality=95):
    """Convert file and log the operation if successful."""
    # Check if already processed
    is_processed, reason = _is_file_processed(src_path, log, force_reprocess)
    if is_processed:
        print(f"  SKIP    {src_path.name} ({reason})", flush=True)
        return "skipped"
    
    # Perform conversion
    if convert_to_jpg(src_path, dst_path, quality):
        _mark_file_processed(src_path, "conversion", log)
        return "converted"
    else:
        return "failed"


def correct_standard_image_orientation(image_path, quality=95):
    """Apply EXIF orientation correction to standard image formats (.jpg, .jpeg).
    
    This function ensures that standard images are properly oriented without
    changing their format. Uses the same orientation correction logic as
    the odk-middleman project.

    Returns True on success, False on failure.
    """
    try:
        with Image.open(image_path) as image:
            # Apply EXIF orientation correction
            corrected_image = _apply_exif_orientation(image)
            
            # Save with same format but optimized
            suffix = image_path.suffix.lower()
            save_kwargs = {}
            
            if suffix in {".jpg", ".jpeg"}:
                if corrected_image.mode not in {"RGB", "L"}:
                    corrected_image = corrected_image.convert("RGB")
                save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}
            
            # Write to temporary file first, then replace
            temp_path = image_path.with_suffix(f"{image_path.suffix}.oriented")
            corrected_image.save(temp_path, **save_kwargs)
            temp_path.replace(image_path)
            
        return True
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        print(f"  FAILED  {image_path.name}: {exc}", flush=True)
        return False


def correct_orientation_and_log(image_path, log, force_reprocess, quality=95):
    """Correct orientation and log the operation if successful."""
    # Check if already processed
    is_processed, reason = _is_file_processed(image_path, log, force_reprocess)
    if is_processed:
        print(f"  SKIP    {image_path.name} ({reason})", flush=True)
        return "skipped"
    
    # Perform orientation correction
    if correct_standard_image_orientation(image_path, quality):
        _mark_file_processed(image_path, "orientation_correction", log)
        return "corrected"
    else:
        return "failed"


def main():
    parser = argparse.ArgumentParser(
        description="Convert non-standard image files to .jpg and apply orientation correction to all images"
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
    parser.add_argument(
        "--force", action="store_true",
        help="Force reprocessing of all files, ignoring the processing log.",
    )
    parser.add_argument(
        "--clear-log", action="store_true",
        help="Clear the processing log before running.",
    )
    parser.add_argument(
        "--no-heic", action="store_true",
        help="Skip HEIC/HEIF files even if pillow-heif could be installed.",
    )
    args = parser.parse_args()

    images_dir = Path(args.dir).resolve()
    if not images_dir.is_dir():
        print(f"Directory not found: {images_dir}", flush=True)
        return 1

    # Handle log file
    if args.clear_log:
        if os.path.exists(LOG_FILE):
            try:
                os.remove(LOG_FILE)
                print(f"Cleared processing log: {LOG_FILE}", flush=True)
            except OSError as exc:
                print(f"WARNING  Could not clear log: {exc}", flush=True)
    
    # Load processing log
    processing_log = _load_processing_log()
    if processing_log and not args.force:
        print(f"Loaded processing log with {len(processing_log)} entries", flush=True)
    elif args.force:
        print("Force mode enabled - ignoring processing log", flush=True)

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

    print(f"  Standard (.jpg/.jpeg):  {len(standard_files)} (will be orientation-corrected)", flush=True)
    print(f"  Convertible:            {len(convertible_files)} (will be converted to .jpg)", flush=True)
    if unknown_files:
        print(f"  Unknown (non-image):    {len(unknown_files)}", flush=True)

    if not convertible_files and not standard_files:
        print("No image files to process.", flush=True)
        return 0

    heic_files = [p for p in convertible_files if p.suffix.lower() in {".heic", ".heif"}]
    if heic_files and not HEIF_AVAILABLE:
        if args.no_heic:
            print(
                f"\nWARNING: {len(heic_files)} HEIC/HEIF files found but --no-heic flag specified.",
                flush=True,
            )
            print("  These files will be skipped.\n", flush=True)
        else:
            # Try to ensure HEIF support
            if not _ensure_heif_support():
                print(
                    f"\nERROR: {len(heic_files)} HEIC/HEIF files found but cannot be converted.",
                    flush=True,
                )
                print("  Run with --no-heic to skip these files, or install pillow-heif manually.", flush=True)
                return 1
            print()  # Add spacing after successful installation

    if args.dry_run:
        print("\n--- Dry run (no changes will be made) ---", flush=True)
        print(f"Processing log: {'ignored in dry-run' if not args.force else 'ignored (force mode)'}", flush=True)
        
        # Report convertible files
        for path in convertible_files:
            dst = path.with_suffix(".jpg")
            is_processed, reason = _is_file_processed(path, processing_log, args.force)
            status = f" (would skip - {reason})" if is_processed and not args.force else ""
            if dst.exists():
                print(f"  WOULD CONVERT  {path.name} -> {dst.name} (dst already exists!){status}", flush=True)
            else:
                print(f"  WOULD CONVERT  {path.name} -> {dst.name}{status}", flush=True)
        
        # Report standard files that will be orientation-corrected
        for path in standard_files:
            is_processed, reason = _is_file_processed(path, processing_log, args.force)
            status = f" (would skip - {reason})" if is_processed and not args.force else ""
            print(f"  WOULD CORRECT ORIENTATION  {path.name}{status}", flush=True)
        
        return 0

    converted = 0
    skipped = 0
    failed = 0
    orientation_corrected = 0
    orientation_failed = 0
    cache_hits = 0

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

        # Use the logging function
        result = convert_and_log(path, dst, processing_log, args.force)
        
        if result == "converted":
            print(f"  CONVERT {path.name} -> {dst.name}", flush=True)
            converted += 1
            if not args.keep:
                try:
                    path.unlink()
                except OSError as exc:
                    print(f"  WARNING  Could not delete original {path.name}: {exc}", flush=True)
        elif result == "skipped":
            cache_hits += 1
        else:  # failed
            failed += 1
            if dst.exists():
                try:
                    dst.unlink()
                except OSError:
                    pass

    # Process standard files for orientation correction
    if standard_files:
        print(f"\n=== Applying orientation correction to standard files ===", flush=True)
        for path in standard_files:
            # Use the logging function
            result = correct_orientation_and_log(path, processing_log, args.force)
            
            if result == "corrected":
                print(f"  CORRECTING ORIENTATION  {path.name}", flush=True)
                orientation_corrected += 1
            elif result == "skipped":
                cache_hits += 1
            else:  # failed
                orientation_failed += 1

    print(
        f"\n=== Processing complete: "
        f"converted={converted}, skipped={skipped}, failed={failed}, "
        f"orientation_corrected={orientation_corrected}, orientation_failed={orientation_failed}, "
        f"cache_hits={cache_hits} ===",
        flush=True,
    )
    
    # Save processing log
    if not args.dry_run:
        _save_processing_log(processing_log)
        print(f"Processing log saved to: {LOG_FILE}", flush=True)
    
    # Send email notification (skip for dry-run and list operations)
    if not args.dry_run:
        try:
            email_summary = {
                'Standard Files Found': len(standard_files),
                'Convertible Files Found': len(convertible_files),
                'Files Converted': converted,
                'Files Skipped': skipped,
                'Conversion Failures': failed,
                'Orientation Corrections': orientation_corrected,
                'Orientation Failures': orientation_failed,
                'Cache Hits (Skipped via Log)': cache_hits,
                'Processing Directory': str(images_dir),
            }

            # Determine status and send appropriate email
            total_failures = failed + orientation_failed
            
            if total_failures > 0:
                # Partial success - some files failed
                failure_details = f"Conversion failures: {failed}\nOrientation correction failures: {orientation_failed}"
                send_partial_success_email("007-convert_nonstandard_images.py", email_summary, failure_details)
            elif converted == 0 and orientation_corrected == 0 and cache_hits > 0:
                # All files were cached - this is still success but worth noting
                cache_details = f"All {cache_hits} files were skipped due to processing log cache."
                send_success_email("007-convert_nonstandard_images.py", email_summary, cache_details)
            else:
                # Complete success with actual processing
                success_details = f"Successfully processed {converted + orientation_corrected} files, {cache_hits} files cached."
                send_success_email("007-convert_nonstandard_images.py", email_summary, success_details)

        except Exception as email_exc:
            print(f"WARNING: Failed to send email notification: {email_exc}", flush=True)
    
    return 0 if (failed == 0 and orientation_failed == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
