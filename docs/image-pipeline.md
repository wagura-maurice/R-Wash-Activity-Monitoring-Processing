# Image Pipeline

The image pipeline handles acquisition, processing, and synchronization of image attachments from ODK Central to the rwash.net hosting server.

## Overview

```
ODK Central  →  006-download_images.py  →  data/images/  →  007-convert_nonstandard_images.py  →  008-upload_sync_images.py  →  rwash.net
                    (acquire)                (local store)        (normalize to .jpg)                (orient + FTPS upload)
```

## Stage 6: Download (`006-download_images.py`)

### Purpose

Downloads image attachments from ODK Central for all configured projects.

### How it works

1. Authenticates to ODK Central using credentials from `.env`
2. Fetches submission data for each project via `odk_sql_helpers.py`
3. Walks `activity_begin` records to find image filename columns
4. Downloads each attachment via the ODK Central API
5. Applies EXIF orientation correction during save using `ImageOps.exif_transpose`
6. Compresses and saves images to `data/images/`

### No-overwrite logic

The `SyncImageDownloader` class (extends `ODKImageDownloader`) maintains a `_known_files` set populated at startup from existing files in `data/images/`. Files that already exist with non-zero size are skipped — only new files are downloaded.

### Resilience

Failed attachments are caught and recorded in `FAILED_ATTACHMENTS` instead of aborting the run. A summary of failures is printed at the end.

### Usage

```bash
# Download all projects
python src/006-download_images.py

# Download specific projects
python src/006-download_images.py SomaliaGarowe EthiopiaV3

# List available projects
python src/006-download_images.py --list
```

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ODK_CENTRAL_URL` | ODK Central server URL | `https://r-washingtesting.com` |
| `ODK_CENTRAL_EMAIL` | ODK Central account email | — |
| `ODK_CENTRAL_PASSWORD` | ODK Central account password | — |

See [ODK Projects](odk-projects.md) for the full list of configured projects.

## Stage 7: Convert (`007-convert_nonstandard_images.py`)

### Purpose

Converts non-standard image formats to `.jpg` for uniformity.

### Supported conversions

| Source | Target | Notes |
|--------|--------|-------|
| `.heic` / `.heif` | `.jpg` | Requires `pillow-heif` package |
| `.png` | `.jpg` | |
| `.webp` | `.jpg` | |
| `.bmp` | `.jpg` | |
| `.gif` | `.jpg` | |
| `.tiff` / `.tif` | `.jpg` | |
| `.avif` | `.jpg` | |

Standard `.jpg` and `.jpeg` files are left untouched.

### Quality

- Converted images saved at quality=95 with JPEG optimization
- EXIF orientation correction applied during conversion
- Mode conversion to RGB for incompatible color spaces

### Usage

```bash
# Convert and delete originals
python src/007-convert_nonstandard_images.py

# Preview without making changes
python src/007-convert_nonstandard_images.py --dry-run

# Keep originals as backup
python src/007-convert_nonstandard_images.py --keep
```

### HEIC support

HEIC/HEIF files (common from iOS devices) require the `pillow-heif` package:

```bash
pip install pillow-heif
```

If not installed, HEIC files are skipped with a warning.

## Stage 8: Upload (`008-upload_sync_images.py`)

### Purpose

Applies a final orientation correction pass and uploads all local images to rwash.net via FTPS.

### Orientation correction

Scans all `.jpg`, `.jpeg`, `.png`, `.webp` files in `data/images/`:
- Reads EXIF orientation tag (`0x0112`)
- If orientation != 1, applies `ImageOps.exif_transpose` to rotate upright
- If no EXIF tag and image is landscape (width > height), rotates 90° as best-effort
- Files already correctly oriented are skipped
- Re-saves in-place via temp file + atomic replace

### FTPS upload

- Connects to `ftp.rwash.net` using explicit FTPS (TLS)
- 300-second timeout for connection, handshake, and data operations
- 3x retry on connection failures and upload timeouts
- Remote file listing via `nlst()` with fallback to per-file `SIZE` checks
- **Never overwrites** existing remote files

### Usage

```bash
# Full sync (orientation + upload)
python src/008-upload_sync_images.py

# Orientation correction only
python src/008-upload_sync_images.py --orient-only

# Upload only (skip orientation)
python src/008-upload_sync_images.py --upload-only
```

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `FTP_HOST` | FTPS server hostname | `ftp.rwash.net` |
| `FTP_PORT` | FTPS server port | `21` |
| `FTP_USER` | FTPS username | — |
| `FTP_PASSWORD` | FTPS password | — |
| `FTP_REMOTE_DIR` | Remote directory for uploads | `/` |

## Extension normalization in Stage 4

`004-generate_import_array.py` includes a `normalize_image_extension()` helper that rewrites non-standard extensions (`.heic`, `.png`, etc.) to `.jpg` when building the `ImagePath` URL. This ensures the database contains URLs that match the final filenames after Stage 7 conversion:

```
Input:  https://odiousodds.xyz/1723892972121.heic
Output: https://rwash.net/1723892972121.jpg
```

## Shared helper: `odk_sql_helpers.py`

Provides lower-level ODK Central API functions used by Stage 6:

- `get_session_token()` — authenticate and get bearer token
- `build_authenticated_session()` — create requests.Session with auth headers
- `fetch_all_form_data()` — fetch OData tables for a form
- `normalize_activity_begin()` — walk submission records and dispatch image downloads
- `ODKImageDownloader` — base class for attachment download with compression and no-overwrite logic

## Troubleshooting

### FTPS connection timeout

The server at `ftp.rwash.net` can be slow to respond. The script uses 300-second timeouts and 3x retry logic. If all retries fail, check:
1. Network connectivity to `ftp.rwash.net:21`
2. FTP credentials in `.env`
3. Server availability (the server disconnects after 15 minutes of inactivity)

### HEIC files not converting

Install `pillow-heif`:
```bash
pip install pillow-heif
```

### Images not upright

Run the orientation pass separately:
```bash
python src/008-upload_sync_images.py --orient-only
```

This will scan and correct all images without uploading.
