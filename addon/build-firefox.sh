#!/bin/bash
# Build script for Firefox version
# This script prepares the addon for Firefox by copying the Firefox-specific manifest

echo "Building EasyForm for Firefox..."

# Copy Firefox manifest
cp manifest-firefox.json manifest.json

# Extract version from manifest
VERSION=$(grep -oP '"version"\s*:\s*"\K[^"]+' manifest.json)
ZIP_NAME="addon_v${VERSION}_firefox.zip"

echo "✓ Firefox manifest copied"
echo "✓ Version: $VERSION"
echo "✓ Creating package: $ZIP_NAME"

# Create zip file excluding unwanted files
zip -r "$ZIP_NAME" . \
  -x "*.sh" \
  -x "*.bat" \
  -x "*.zip" \
  -x "manifest-chrome.json" \
  -x "BUILD-README.md"

echo "✓ Firefox build ready"
echo "✓ Package created: $ZIP_NAME"
echo ""
