#!/bin/bash

# R-WASH Activity Monitoring Pipeline Script
# This script runs the image pipeline stages in sequence
# Intended for use with cron jobs on Ubuntu VPS

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "R-WASH Activity Monitoring Pipeline"
echo "Started at: $(date)"
echo "=========================================="

# Activate virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "ERROR: Virtual environment not found at $SCRIPT_DIR/venv"
    echo "Please create it first: python3 -m venv venv"
    exit 1
fi

# Stage 6: Download images
echo ""
echo "=========================================="
echo "Stage 6: Download Images from ODK Central"
echo "=========================================="
python3 src/006-download_images.py
DOWNLOAD_STATUS=$?

if [ $DOWNLOAD_STATUS -ne 0 ]; then
    echo "ERROR: Stage 6 (Download Images) failed with status $DOWNLOAD_STATUS"
    exit 1
fi

# Stage 7: Convert non-standard images
echo ""
echo "=========================================="
echo "Stage 7: Convert Non-Standard Images"
echo "=========================================="
python3 src/007-convert_nonstandard_images.py
CONVERT_STATUS=$?

if [ $CONVERT_STATUS -ne 0 ]; then
    echo "ERROR: Stage 7 (Convert Images) failed with status $CONVERT_STATUS"
    exit 1
fi

# Stage 8: Upload images to FTPS server
echo ""
echo "=========================================="
echo "Stage 8: Upload Images to FTPS Server"
echo "=========================================="
python3 src/008-upload_sync_images.py
UPLOAD_STATUS=$?

if [ $UPLOAD_STATUS -ne 0 ]; then
    echo "ERROR: Stage 8 (Upload Images) failed with status $UPLOAD_STATUS"
    exit 1
fi

# Pipeline completed successfully
echo ""
echo "=========================================="
echo "Pipeline Completed Successfully"
echo "Finished at: $(date)"
echo "=========================================="

exit 0