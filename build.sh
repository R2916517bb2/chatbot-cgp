#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status.
set -e

echo "--- Starting build for Render deployment ---"

# Check if we're on Render (or similar containerized environment)
if [ -f "/etc/os-release" ]; then
    echo "--- Detected Linux environment ---"
    
    # Try to install tesseract if possible (may fail on read-only systems)
    echo "--- Attempting to install Tesseract OCR ---"
    if command -v apt-get >/dev/null 2>&1; then
        # Only try if we have write access
        if apt-get update 2>/dev/null && apt-get install -y tesseract-ocr 2>/dev/null; then
            echo "--- Tesseract OCR installed successfully ---"
        else
            echo "--- Warning: Could not install Tesseract OCR (read-only filesystem or insufficient permissions) ---"
            echo "--- OCR functionality will be disabled, but PDF text extraction will still work ---"
        fi
    else
        echo "--- apt-get not available, skipping Tesseract installation ---"
    fi
else
    echo "--- Non-Linux environment detected ---"
fi

echo "--- Installing Python dependencies ---"
pip install --upgrade pip
pip install -r requirements.txt

echo "--- Build complete ---"
echo "--- Note: If Tesseract installation failed, the app will run without OCR capabilities ---"