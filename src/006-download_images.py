#!/usr/bin/env python3
"""Download images from ODK Central into data/images/.

Acquires image attachments for all configured projects and saves them locally
as raw files without any processing, validation, or transformation.
Existing files are never overwritten (reused as-is).

Image processing (format conversion, orientation correction) is handled by
007-convert_nonstandard_images.py, and uploading to rwash.net is handled by
008-upload_sync_images.py.

Usage:
    # download images for all projects
    python src/006-download_images.py

    # download images for specific projects only
    python src/006-download_images.py SomaliaGarowe EthiopiaV3

    # list available project names
    python src/006-download_images.py --list
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

import odk_sql_helpers as odk_helpers
from email_notifier import send_success_email, send_failure_email, send_partial_success_email

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Track attachments that failed to download so we can report them at the end.
FAILED_ATTACHMENTS = []


class SyncImageDownloader(odk_helpers.ODKImageDownloader):
    """ODKImageDownloader that is resilient and downloads raw files.

    - Skips a failed attachment instead of aborting the whole run.
    - Downloads files as-is without any processing, validation, or transformation.
    """

    def _compress_and_write_image(self, content, target_path):
        """Write raw content to target path without any processing."""
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
        f"[{name}] image download complete: "
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


def main(argv):
    if "--list" in argv:
        print("Available projects:")
        for name, (pid, fid) in PROJECTS.items():
            print(f"  {name:30s} project_id={pid:<3d} form_id={fid}")
        return 0

    selected = [a for a in argv if not a.startswith("-")]
    if not selected:
        selected = list(PROJECTS.keys())

    unknown = [s for s in selected if s not in PROJECTS]
    if unknown:
        print(f"Unknown project(s): {unknown}")
        print(f"Available: {', '.join(PROJECTS.keys())}")
        return 1

    print(f"Downloading images for: {', '.join(selected)}")
    print(f"Images root: {Path(IMAGES_ROOT).resolve()}")

    summary = {}

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

    # Send email notification
    try:
        # Calculate overall statistics
        total_submissions = sum(stats.get('submissions', 0) for stats in summary.values() if isinstance(stats, dict))
        total_processed = sum(stats.get('processed', 0) for stats in summary.values() if isinstance(stats, dict))
        total_downloaded = sum(stats.get('downloaded', 0) for stats in summary.values() if isinstance(stats, dict))
        total_reused = sum(stats.get('reused', 0) for stats in summary.values() if isinstance(stats, dict))
        total_failed = sum(stats.get('failed', 0) for stats in summary.values() if isinstance(stats, dict))
        total_errors = sum(1 for stats in summary.values() if isinstance(stats, dict) and 'error' in stats)

        email_summary = {
            'Projects Processed': len(summary),
            'Total Submissions': total_submissions,
            'Total Images Processed': total_processed,
            'New Downloads': total_downloaded,
            'Reused Existing': total_reused,
            'Failed Downloads': total_failed,
            'Project Errors': total_errors,
        }

        # Determine status and send appropriate email
        if total_errors > 0:
            # Complete failure for some projects
            error_details = "\n".join([
                f"{name}: {stats.get('error', 'Unknown error')}" 
                for name, stats in summary.items() 
                if isinstance(stats, dict) and 'error' in stats
            ])
            send_failure_email("006-download_images.py", email_summary, error_details)
            return 1
        elif total_failed > 0:
            # Partial success - some downloads failed
            failed_details = "\n".join([
                f"project={f['project_id']} form={f['form_id']} "
                f"submission={f['instance_id']} file={f['filename']}\n"
                f"    error: {f['error']}"
                for f in FAILED_ATTACHMENTS
            ])
            send_partial_success_email("006-download_images.py", email_summary, failed_details)
            return 0
        else:
            # Complete success
            success_details = "\n".join([
                f"{name}: {stats}" 
                for name, stats in summary.items() 
                if isinstance(stats, dict)
            ])
            send_success_email("006-download_images.py", email_summary, success_details)
            return 0

    except Exception as email_exc:
        print(f"WARNING: Failed to send email notification: {email_exc}", flush=True)
        return 0  # Don't fail the script just because email failed


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
