#!/usr/bin/env python3
"""Synchronized ODK image download + FTPS upload.

Downloads images from ODK Central and immediately uploads any new files to
rwash.net via explicit FTPS, without overwriting existing local or remote files.

Uses helpers in odk_sql_helpers.py for ODK Central access.

Usage:
    # sync (download + upload) all projects
    python src/006-download_sync_images.py

    # sync specific projects only
    python src/006-download_sync_images.py SomaliaGarowe EthiopiaV3

    # download only
    python src/006-download_sync_images.py --download-only

    # upload existing local images only
    python src/006-download_sync_images.py --upload-only

    # list available project names
    python src/006-download_sync_images.py --list
"""

import os
import sys
from ftplib import FTP_TLS, error_perm
from io import BytesIO
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError

import odk_sql_helpers as odk_helpers

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Increase PIL image size limit to handle large images (set to None to disable limit)
Image.MAX_IMAGE_PIXELS = None


def _apply_image_orientation(image):
    """Return an image corrected for EXIF orientation and forced to portrait if no EXIF."""
    exif = image.getexif()
    orientation = exif.get(0x0112) if exif else None
    image = ImageOps.exif_transpose(image)
    if orientation is None and image.width > image.height:
        # No EXIF guidance; rotate to portrait orientation as a best effort.
        image = image.rotate(90, expand=True)
    return image


# Track attachments that failed to download so we can report them at the end.
FAILED_ATTACHMENTS = []


class SyncImageDownloader(odk_helpers.ODKImageDownloader):
    """ODKImageDownloader that is resilient and applies orientation correction.

    - Skips a failed attachment instead of aborting the whole run.
    - Applies EXIF orientation and, for images without EXIF guidance, rotates
      landscape captures to portrait.
    """

    def _compress_and_write_image(self, content, target_path):
        suffix = target_path.suffix.lower()

        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            self._write_raw_bytes(content, target_path)
            return

        try:
            with Image.open(BytesIO(content)) as image:
                image = _apply_image_orientation(image)
                save_kwargs = {}
                processed_image = image

                if suffix in {".jpg", ".jpeg"}:
                    if image.mode not in {"RGB", "L"}:
                        processed_image = image.convert("RGB")
                    save_kwargs = {
                        "format": "JPEG",
                        "quality": self.jpeg_quality,
                        "optimize": True,
                    }
                elif suffix == ".png":
                    if image.mode not in {"1", "L", "P", "RGB", "RGBA", "LA"}:
                        processed_image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    save_kwargs = {
                        "format": "PNG",
                        "optimize": True,
                        "compress_level": self.png_compress_level,
                    }
                else:
                    if image.mode not in {"RGB", "RGBA"}:
                        processed_image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    save_kwargs = {
                        "format": "WEBP",
                        "quality": self.webp_quality,
                        "method": 6,
                    }

                temp_path = target_path.with_suffix(f"{target_path.suffix}.part")
                processed_image.save(temp_path, **save_kwargs)
                temp_path.replace(target_path)
        except (OSError, ValueError, UnidentifiedImageError):
            self._write_raw_bytes(content, target_path)

    def download_attachment(self, project_id, form_id, instance_id, filename, table_name=None):
        try:
            return super().download_attachment(
                project_id, form_id, instance_id, filename, table_name=table_name
            )
        except Exception as exc:
            FAILED_ATTACHMENTS.append(
                {
                    "project_id": project_id,
                    "form_id": form_id,
                    "instance_id": instance_id,
                    "filename": filename,
                    "error": str(exc),
                }
            )
            self.processed_count += 1
            self._report_progress()
            return filename


# Central server credentials (same as PullODK.ipynb)
CENTRAL_URL = os.getenv("ODK_CENTRAL_URL", "https://r-washingtesting.com")
CENTRAL_EMAIL = os.getenv("ODK_CENTRAL_EMAIL", "abarasa@unicef.org")
CENTRAL_PASSWORD = os.getenv("ODK_CENTRAL_PASSWORD", "RWASHVision@!2026")

IMAGES_ROOT = os.path.join(BASE_DIR, "data", "images")

# FTPS credentials for rwash.net image hosting
FTP_HOST = os.getenv("FTP_HOST", "ftp.rwash.net")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER", "root@rwash.net")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "7;B4-Y!7AK74aPj8")
FTP_REMOTE_DIR = os.getenv("FTP_REMOTE_DIR", "/")  # root directory on the remote server

# Mirrors the export cells in PullODK.ipynb.
# name -> (project_id, form_id)
PROJECTS = {
    "SomaliaGarowe": (21, "RWASH_Activity_20250730"),
    "SomaliaDollow": (20, "RWASH_Activity_20250730"),
    "EthiopiaV3": (36, "RWASH_Activity_20250924"),
    "EthiopiaV2": (26, "RWASH_Activity_20250831"),
    "SudanActivityMonitoringV2": (37, "R-WASH Activity Monitoring Questionnaire - Sudan - v2"),
    "Ethiopia": (5, "RWASH_Activity_20240815"),
    "Somalia": (8, "RWASH_Activity_20240924"),
    "Sudan": (14, "R-WASH Activity Monitoring Questionnaire - Sudan - Translated"),
    "SomaliaDollowV3": (42, "RWASH_Activity_20260405"),
}


def download_images_for_project(name, project_id, form_id, images_root=IMAGES_ROOT, verbose=True):
    print(f"\n=== {name} (project_id={project_id}, form_id={form_id}) ===", flush=True)

    token = odk_helpers.get_session_token(CENTRAL_URL, CENTRAL_EMAIL, CENTRAL_PASSWORD)
    session = odk_helpers.build_authenticated_session(token)

    dfs = odk_helpers.fetch_all_form_data(
        CENTRAL_URL,
        CENTRAL_EMAIL,
        CENTRAL_PASSWORD,
        project_id,
        form_id,
        token=token,
        session=session,
        verbose=verbose,
    )

    submissions_df = dfs["Submissions"]
    print(f"[{name}] submissions: {len(submissions_df)} rows", flush=True)

    image_downloader = SyncImageDownloader(
        CENTRAL_URL,
        token,
        download_root=images_root,
        session=session,
        verbose=verbose,
    )

    # normalize_activity_begin walks the activity_begin record, finds image
    # filename columns, and calls image_downloader.download_attachment for each.
    # This is the same step PullODK.ipynb runs; we just skip the SQL write.
    activity_df = odk_helpers.normalize_activity_begin(
        submissions_df,
        central_url=CENTRAL_URL,
        project_id=project_id,
        form_id=form_id,
        table_name=name,
        image_downloader=image_downloader,
    )

    image_downloader._report_progress(force=True)
    failed = [f for f in FAILED_ATTACHMENTS if f["project_id"] == project_id and f["form_id"] == form_id]
    print(
        f"[{name}] image processing complete: "
        f"processed={image_downloader.processed_count}, "
        f"downloaded={image_downloader.downloaded_count}, "
        f"reused={image_downloader.reused_count}, "
        f"failed={len(failed)}",
        flush=True,
    )
    return {
        "submissions": len(submissions_df),
        "processed": image_downloader.processed_count,
        "downloaded": image_downloader.downloaded_count,
        "reused": image_downloader.reused_count,
        "failed": len(failed),
    }


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

    print(f"[FTP] Connecting to {host}:{port} as {user} (explicit FTPS)…", flush=True)

    ftp = FTP_TLS()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, password)
    ftp.prot_p()  # upgrade to protected (encrypted) data connection

    if verbose:
        print(f"[FTP] Connected. Server reply: {ftp.welcome}", flush=True)

    if remote_dir and remote_dir != "/":
        ftp.cwd(remote_dir)

    # Build a set of filenames already on the remote server so we can skip them.
    try:
        remote_files = set(ftp.nlst())
    except error_perm:
        remote_files = set()
    if verbose:
        print(f"[FTP] Remote directory has {len(remote_files)} existing files.", flush=True)

    uploaded = 0
    skipped = 0
    failed = 0
    failed_list = []

    for local_path in local_files:
        filename = local_path.name
        if filename in remote_files:
            skipped += 1
            if verbose:
                print(f"[FTP] SKIP  {filename} (already exists on server)", flush=True)
            continue

        try:
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {filename}", f)
            remote_files.add(filename)
            uploaded += 1
            if verbose:
                print(f"[FTP] UPLOADED  {filename} ({local_path.stat().st_size} bytes)", flush=True)
        except Exception as exc:
            failed += 1
            failed_list.append({"filename": filename, "error": str(exc)})
            print(f"[FTP] FAILED  {filename}: {exc}", flush=True)

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
    if "--list" in argv:
        print("Available projects:")
        for name, (pid, fid) in PROJECTS.items():
            print(f"  {name:30s} project_id={pid:<3d} form_id={fid}")
        return 0

    download_only = "--download-only" in argv
    upload_only = "--upload-only" in argv

    do_download = not upload_only
    do_upload = not download_only

    selected = [a for a in argv if not a.startswith("-")]
    if do_download and not selected:
        selected = list(PROJECTS.keys())

    unknown = [s for s in selected if s not in PROJECTS]
    if do_download and unknown:
        print(f"Unknown project(s): {unknown}")
        print(f"Available: {', '.join(PROJECTS.keys())}")
        return 1

    summary = {}

    if do_download:
        print(f"Downloading images for: {', '.join(selected)}")
        print(f"Images root: {Path(IMAGES_ROOT).resolve()}")

        for name in selected:
            project_id, form_id = PROJECTS[name]
            try:
                summary[name] = download_images_for_project(name, project_id, form_id)
            except Exception as exc:
                print(f"[{name}] FAILED: {exc}", flush=True)
                summary[name] = {"error": str(exc)}

        print("\n=== Download Summary ===")
        for name, stats in summary.items():
            print(f"  {name:30s} {stats}")

        if FAILED_ATTACHMENTS:
            print(f"\n=== Failed attachments ({len(FAILED_ATTACHMENTS)}) ===")
            for f in FAILED_ATTACHMENTS:
                print(
                    f"  project={f['project_id']} form={f['form_id']} "
                    f"submission={f['instance_id']} file={f['filename']}"
                )
                print(f"    error: {f['error']}")

    if do_upload:
        print("\n=== FTPS Upload to rwash.net ===")
        upload_summary = upload_images_to_ftp()
        summary["ftp_upload"] = upload_summary

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
