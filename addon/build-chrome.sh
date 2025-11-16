#!/bin/bash
# Build script for Chrome version
# This script prepares the addon for Chrome by copying the Chrome-specific manifest

echo "Building EasyForm for Chrome..."

# Copy Chrome manifest
cp manifest-chrome.json manifest.json

# Extract version from manifest
VERSION=$(grep -oP '"version"\s*:\s*"\K[^"]+' manifest.json)
ZIP_NAME="addon_v${VERSION}_chrome.zip"

echo "✓ Chrome manifest copied"
echo "✓ Version: $VERSION"
echo "✓ Creating package: $ZIP_NAME"

# Create zip file excluding unwanted files
zip -r "$ZIP_NAME" . \
  -x "*.sh" \
  -x "*.bat" \
  -x "*.zip" \
  -x "manifest-firefox.json" \
  -x "BUILD-README.md"

echo "✓ Chrome build ready"
echo "✓ Package created: $ZIP_NAME"
echo ""
echo "background-unified.js works for both Firefox and Chrome!"
