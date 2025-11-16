@echo off
REM Build script for Chrome version (Windows)
REM This script prepares the addon for Chrome by copying the Chrome-specific manifest

echo Building EasyForm for Chrome...

REM Copy Chrome manifest
copy /Y manifest-chrome.json manifest.json

echo.
echo [OK] Chrome manifest copied
echo [OK] Chrome build ready
echo.
echo background-unified.js works for both Firefox and Chrome!
echo.
echo To test: Load the addon folder in Chrome
