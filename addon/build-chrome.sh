#!/bin/bash
# Build script for Chrome version
# This script prepares the addon for Chrome by copying the Chrome-specific manifest

echo "Building EasyForm for Chrome..."

# Copy Chrome manifest
cp manifest-chrome.json manifest.json

echo "✓ Chrome manifest copied"
echo "✓ Chrome build ready"
echo ""
echo "background-unified.js works for both Firefox and Chrome!"
echo ""
echo "To package: cd addon && zip -r ../easyform-chrome.zip ."
