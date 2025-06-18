#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Updating apt-get and installing Tesseract OCR ---"
apt-get update
apt-get install -y tesseract-ocr

echo "--- Installing Python dependencies ---"
pip install -r requirements.txt

echo "--- Build complete ---"