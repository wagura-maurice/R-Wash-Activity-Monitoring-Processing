#!/usr/bin/env python3
"""Upload processed images to rwash.net via FTPS.

Runs as the final step in the image pipeline:
    006-download_images.py               → acquire from ODK Central
    007-convert_nonstandard_images.py    → normalize extensions and apply orientation correction
    008-upload_sync_images.py            → FTPS upload only

This script uploads all local images to the rwash.net FTP server (explicit FTPS).
Never overwrites existing local or remote files.

Usage:
    python src/008-upload_sync_images.py
"""

import os
import socket
import sys
import time
from ftplib import FTP_TLS, error_perm
from pathlib import Path

from dotenv import load_dotenv
from email_notifier import send_success_email, send_failure_email, send_partial_success_email

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

IMAGES_ROOT = os.path.join(BASE_DIR, "data", "images")

# FTPS credentials for rwash.net image hosting
FTP_HOST = os.getenv("FTP_HOST", "ftp.rwash.net")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER", "root@rwash.net")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "7;B4-Y!7AK74aPj8")
FTP_REMOTE_DIR = os.getenv("FTP_REMOTE_DIR", "/")


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

    Returns a dict with counts: uploaded, skipped, failed, and failed_list.
    """
    local_dir = Path(images_root).resolve()
    if not local_dir.is_dir():
        print(f"[FTP] Images directory not found: {local_dir}", flush=True)
        return {"uploaded": 0, "skipped": 0, "failed": 0, "failed_list": []}

    local_files = sorted(
        p for p in local_dir.iterdir() if p.is_file() and p.stat().st_size > 0
    )
    if not local_files:
        print(f"[FTP] No image files found in {local_dir}", flush=True)
        return {"uploaded": 0, "skipped": 0, "failed": 0, "failed_list": []}

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
                return {"uploaded": 0, "skipped": 0, "failed": len(local_files), "failed_list": []}

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

    return {"uploaded": uploaded, "skipped": skipped, "failed": failed, "failed_list": failed_list}


def main(argv):
    print("\n=== FTPS Upload to rwash.net ===")
    summary = upload_images_to_ftp()
    
    print("\n=== Upload Summary ===")
    print(f"  uploaded={summary['uploaded']}, skipped={summary['skipped']}, failed={summary['failed']}")
    
    # Send email notification
    try:
        email_summary = {
            'FTP Server': f"{FTP_HOST}:{FTP_PORT}",
            'Local Directory': IMAGES_ROOT,
            'Remote Directory': FTP_REMOTE_DIR,
            'Total Files Found': summary['uploaded'] + summary['skipped'] + summary['failed'],
            'Files Uploaded': summary['uploaded'],
            'Files Skipped (Already on Server)': summary['skipped'],
            'Failed Uploads': summary['failed'],
        }

        # Determine status and send appropriate email
        if summary['failed'] > 0:
            # Partial success - some uploads failed
            failed_details = "\n".join([
                f"{item['filename']}: {item['error']}" 
                for item in summary['failed_list']
            ])
            send_partial_success_email("008-upload_sync_images.py", email_summary, failed_details)
        elif summary['uploaded'] == 0 and summary['skipped'] > 0:
            # All files were already on server - this is still success but worth noting
            skip_details = f"All {summary['skipped']} files were already present on the remote server."
            send_success_email("008-upload_sync_images.py", email_summary, skip_details)
        else:
            # Complete success with actual uploads
            success_details = f"Successfully uploaded {summary['uploaded']} new files to the FTP server."
            send_success_email("008-upload_sync_images.py", email_summary, success_details)

    except Exception as email_exc:
        print(f"WARNING: Failed to send email notification: {email_exc}", flush=True)
    
    return 0 if summary['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
