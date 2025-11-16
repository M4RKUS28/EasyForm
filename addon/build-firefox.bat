@echo off
REM Build script for Firefox version (Windows)
REM This script prepares the addon for Firefox by copying the Firefox-specific manifest

echo Building EasyForm for Firefox...

REM Copy Firefox manifest
copy /Y manifest-firefox.json manifest.json

echo.
echo [OK] Firefox manifest copied
echo [OK] Firefox build ready
echo.
echo background-unified.js works for both Firefox and Chrome!
echo.
echo To test: Load the addon folder in Firefox
