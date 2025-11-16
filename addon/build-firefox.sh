#!/bin/bash
# Build script for Firefox version
# This script prepares the addon for Firefox by copying the Firefox-specific manifest

echo "Building EasyForm for Firefox..."

# Copy Firefox manifest
cp manifest-firefox.json manifest.json

echo "✓ Firefox manifest copied"
echo "✓ Firefox build ready"
echo ""
echo "background-unified.js works for both Firefox and Chrome!"
echo ""
echo "To package: cd addon && zip -r ../easyform-firefox.zip ."
