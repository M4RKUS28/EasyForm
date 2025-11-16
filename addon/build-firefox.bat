@echo off
REM Build script for Firefox version (Windows CMD)
REM This script prepares the addon for Firefox by copying the Firefox-specific manifest
REM Requires PowerShell 5.0+ (included in Windows 10+)

echo Building EasyForm for Firefox...
echo.

REM Copy Firefox manifest
copy /Y manifest-firefox.json manifest.json >nul 2>&1

REM Extract version from manifest using PowerShell
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "(Get-Content manifest.json -Raw | ConvertFrom-Json).version"`) do set VERSION=%%i

set ZIP_NAME=addon_v%VERSION%_firefox.zip

echo [OK] Firefox manifest copied
echo [OK] Version: %VERSION%
echo [OK] Creating package: %ZIP_NAME%
echo.

REM Delete old zip if exists
if exist "%ZIP_NAME%" del "%ZIP_NAME%"

REM Create temporary directory for clean packaging
set TEMP_DIR=%TEMP%\easyform_build_%RANDOM%
mkdir "%TEMP_DIR%"

REM Copy all files except excluded ones
for %%F in (*) do (
    if /I not "%%~xF"==".sh" if /I not "%%~xF"==".bat" if /I not "%%~xF"==".zip" if /I not "%%F"=="manifest-chrome.json" if /I not "%%F"=="BUILD-README.md" (
        copy "%%F" "%TEMP_DIR%\" >nul 2>&1
    )
)

REM Copy subdirectories
for /D %%D in (*) do (
    xcopy "%%D" "%TEMP_DIR%\%%D\" /E /I /Q /Y >nul 2>&1
)

REM Create ZIP using PowerShell
powershell -NoProfile -Command "Compress-Archive -Path '%TEMP_DIR%\*' -DestinationPath '%ZIP_NAME%' -CompressionLevel Optimal -Force"

REM Cleanup
rmdir /S /Q "%TEMP_DIR%"

echo [OK] Firefox build ready
echo [OK] Package created: %ZIP_NAME%
echo.
echo background-unified.js works for both Firefox and Chrome!
echo.
