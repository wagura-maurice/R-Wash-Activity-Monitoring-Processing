#!/usr/bin/env python3
"""Apply orientation correction and upload images to rwash.net via FTPS.

Runs as the final step in the image pipeline:
    006-download_sync_images.py          → acquire from ODK Central
    007-convert_nonstandard_images.py    → normalize extensions to .jpg
    008-upload_sync_images.py            → orientation correction + FTPS upload

This script:
  1. Scans data/images/ for image files and applies EXIF orientation correction.
  2. Uploads all local images to the rwash.net FTP server (explicit FTPS).
  3. Never overwrites existing local or remote files.

Usage:
    # full sync (orientation correction + upload)
    python src/008-upload_sync_images.py

    # orientation correction only, skip upload
    python src/008-upload_sync_images.py --orient-only

    # upload only, skip orientation correction
    python src/008-upload_sync_images.py --upload-only
"""

import os
import socket
import sys
import time
from ftplib import FTP_TLS, error_perm
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

Image.MAX_IMAGE_PIXELS = None

IMAGES_ROOT = os.path.join(BASE_DIR, "data", "images")

# FTPS credentials for rwash.net image hosting
FTP_HOST = os.getenv("FTP_HOST", "ftp.rwash.net")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER", "root@rwash.net")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "7;B4-Y!7AK74aPj8")
FTP_REMOTE_DIR = os.getenv("FTP_REMOTE_DIR", "/")


def _apply_image_orientation(image):
    """Return an image corrected for EXIF orientation and forced to portrait if no EXIF."""
    exif = image.getexif()
    orientation = exif.get(0x0112) if exif else None
    image = ImageOps.exif_transpose(image)
    if orientation is None and image.width > image.height:
        image = image.rotate(90, expand=True)
    return image


def correct_image_orientations(images_root=IMAGES_ROOT, verbose=True):
    """Scan all images in *images_root* and re-save them with correct orientation.

    Uses EXIF orientation metadata (via ``ImageOps.exif_transpose``) to rotate
    each image upright.  For images with no EXIF orientation tag that are in
    landscape mode, a best-effort 90-degree rotation is applied to force
    portrait orientation.

    Files that are already correctly oriented or that cannot be opened as
    images are left untouched.

    Returns a dict with counts: corrected, skipped, failed.
    """
    local_dir = Path(images_root).resolve()
    if not local_dir.is_dir():
        print(f"[ORIENT] Images directory not found: {local_dir}", flush=True)
        return {"corrected": 0, "skipped": 0, "failed": 0}

    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    local_files = sorted(
        p for p in local_dir.iterdir()
        if p.is_file() and p.suffix.lower() in image_exts and p.stat().st_size > 0
    )
    if not local_files:
        print(f"[ORIENT] No image files found in {local_dir}", flush=True)
        return {"corrected": 0, "skipped": 0, "failed": 0}

    corrected = 0
    skipped = 0
    failed = 0

    for idx, local_path in enumerate(local_files, 1):
        try:
            with Image.open(local_path) as image:
                exif = image.getexif()
                orientation = exif.get(0x0112) if exif else None

                needs_correction = False
                if orientation is not None and orientation != 1:
                    needs_correction = True
                elif orientation is None and image.width > image.height:
                    needs_correction = True

                if not needs_correction:
                    skipped += 1
                    continue

                corrected_image = _apply_image_orientation(image)

                suffix = local_path.suffix.lower()
                save_kwargs = {}
                if suffix in {".jpg", ".jpeg"}:
                    if corrected_image.mode not in {"RGB", "L"}:
                        corrected_image = corrected_image.convert("RGB")
                    save_kwargs = {"format": "JPEG", "quality": 85, "optimize": True}
                elif suffix == ".png":
                    if corrected_image.mode not in {"1", "L", "P", "RGB", "RGBA", "LA"}:
                        corrected_image = corrected_image.convert(
                            "RGBA" if "A" in corrected_image.getbands() else "RGB"
                        )
                    save_kwargs = {"format": "PNG", "optimize": True, "compress_level": 9}
                else:
                    if corrected_image.mode not in {"RGB", "RGBA"}:
                        corrected_image = corrected_image.convert(
                            "RGBA" if "A" in corrected_image.getbands() else "RGB"
                        )
                    save_kwargs = {"format": "WEBP", "quality": 85, "method": 6}

                temp_path = local_path.with_suffix(f"{local_path.suffix}.oriented")
                corrected_image.save(temp_path, **save_kwargs)
                temp_path.replace(local_path)
                corrected += 1

                if verbose and idx % 50 == 0:
                    print(f"[ORIENT] Processed {idx}/{len(local_files)}…", flush=True)

        except (OSError, ValueError, UnidentifiedImageError) as exc:
            failed += 1
            if verbose:
                print(f"[ORIENT] FAILED  {local_path.name}: {exc}", flush=True)

    print(
        f"\n[ORIENT] Orientation pass complete: "
        f"corrected={corrected}, skipped={skipped}, failed={failed}",
        flush=True,
    )
    return {"corrected": corrected, "skipped": skipped, "failed": failed}


def upload_images_to_ftp(
    images_root=IMAGES_ROOT,
    host=FTP_HOST,
    port=FTP_PORT,
    user=FTP_USER,
    password=FTP_PASSWORD,
    remote_dir=FTP_REMOTE_DIR,
    verbose=True,
):
    """Upload images from *images_root* to the rwash.net FTP server via explicit FTPS.

    Files that already exist on the remote server are never overwritten.
    The function checks the remote directory listing before each upload and
    skips any filename that is already present.

    Returns a dict with counts: uploaded, skipped, failed.
    """
    local_dir = Path(images_root).resolve()
    if not local_dir.is_dir():
        print(f"[FTP] Images directory not found: {local_dir}", flush=True)
        return {"uploaded": 0, "skipped": 0, "failed": 0}

    local_files = sorted(
        p for p in local_dir.iterdir() if p.is_file() and p.stat().st_size > 0
    )
    if not local_files:
        print(f"[FTP] No image files found in {local_dir}", flush=True)
        return {"uploaded": 0, "skipped": 0, "failed": 0}

    def _connect_ftp():
        """Create a fresh FTPS connection with generous timeouts."""
        f = FTP_TLS()
        f.connect(host, port, timeout=300)
        f.sock.settimeout(300)
        f.login(user, password)
        f.prot_p()
        if remote_dir and remote_dir != "/":
            f.cwd(remote_dir)
        return f

    print(f"[FTP] Connecting to {host}:{port} as {user} (explicit FTPS)…", flush=True)

    ftp = None
    for attempt in range(3):
        try:
            ftp = _connect_ftp()
            break
        except (socket.timeout, TimeoutError, OSError) as exc:
            if attempt < 2:
                print(f"[FTP] Connection attempt {attempt + 1} failed ({exc}), retrying…", flush=True)
                time.sleep(3)
            else:
                print(f"[FTP] Could not connect after 3 attempts: {exc}", flush=True)
                return {"uploaded": 0, "skipped": 0, "failed": len(local_files)}

    if verbose:
        print(f"[FTP] Connected. Server reply: {ftp.welcome}", flush=True)

    remote_files = None
    try:
        if ftp.sock:
            ftp.sock.settimeout(300)
        remote_files = set(ftp.nlst())
    except (error_perm, socket.timeout, TimeoutError, OSError):
        remote_files = None

    if remote_files is not None:
        if verbose:
            print(f"[FTP] Remote directory has {len(remote_files)} existing files.", flush=True)
    else:
        if verbose:
            print("[FTP] Could not list remote directory; will check each file individually.", flush=True)
        remote_files = set()

    def _remote_file_exists(fname):
        if remote_files is not None:
            return fname in remote_files
        try:
            ftp.size(fname)
            return True
        except error_perm:
            return False

    uploaded = 0
    skipped = 0
    failed = 0
    failed_list = []

    for local_path in local_files:
        filename = local_path.name
        if _remote_file_exists(filename):
            skipped += 1
            if verbose:
                print(f"[FTP] SKIP  {filename} (already exists on server)", flush=True)
            continue

        success = False
        for attempt in range(3):
            try:
                with open(local_path, "rb") as f:
                    ftp.storbinary(f"STOR {filename}", f)
                remote_files.add(filename)
                uploaded += 1
                if verbose:
                    print(f"[FTP] UPLOADED  {filename} ({local_path.stat().st_size} bytes)", flush=True)
                success = True
                break
            except (socket.timeout, TimeoutError) as exc:
                if attempt < 2:
                    print(f"[FTP] Timeout on {filename}, retrying ({attempt + 1}/3)…", flush=True)
                    time.sleep(2)
                    try:
                        ftp.quit()
                    except Exception:
                        ftp.close()
                    ftp = _connect_ftp()
                    continue
                failed += 1
                failed_list.append({"filename": filename, "error": str(exc)})
                print(f"[FTP] FAILED  {filename}: {exc}", flush=True)
                success = True
                break
            except Exception as exc:
                failed += 1
                failed_list.append({"filename": filename, "error": str(exc)})
                print(f"[FTP] FAILED  {filename}: {exc}", flush=True)
                success = True
                break
        if not success:
            failed += 1
            failed_list.append({"filename": filename, "error": "exhausted retries"})

    try:
        ftp.quit()
    except Exception:
        try:
            ftp.close()
        except Exception:
            pass

    print(
        f"\n[FTP] Upload complete: uploaded={uploaded}, skipped={skipped}, failed={failed}",
        flush=True,
    )
    if failed_list:
        print(f"[FTP] Failed files ({len(failed_list)}):", flush=True)
        for item in failed_list:
            print(f"  {item['filename']}: {item['error']}", flush=True)

    return {"uploaded": uploaded, "skipped": skipped, "failed": failed}


def main(argv):
    orient_only = "--orient-only" in argv
    upload_only = "--upload-only" in argv

    do_orient = not upload_only
    do_upload = not orient_only

    summary = {}

    if do_orient:
        print("\n=== Image Orientation Correction ===")
        summary["orientation"] = correct_image_orientations()

    if do_upload:
        print("\n=== FTPS Upload to rwash.net ===")
        summary["ftp_upload"] = upload_images_to_ftp()

    print("\n=== Sync Summary ===")
    for step, stats in summary.items():
        print(f"  {step:20s} {stats}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
