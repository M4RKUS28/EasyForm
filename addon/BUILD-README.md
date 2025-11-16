# EasyForm - Build Instructions

This addon supports both **Firefox** and **Chrome** browsers. Due to differences in Manifest V3 implementation between the browsers, separate **manifest files** are required, but the **same background script** works for both!

## Key Differences

### Firefox
- Uses `background.scripts` array in manifest
- Supports `theme` permission
- Loads browser-polyfill.js via manifest

### Chrome
- Uses `service_worker` in manifest
- Does not support `theme` permission
- browser-polyfill.js is loaded via `importScripts()` (auto-detected in code)

## Unified Background Script

The `background-unified.js` file works for **both browsers**! It auto-detects the environment:
- In **Chrome** (service worker): Uses `importScripts()` to load browser-polyfill
- In **Firefox**: Polyfill already loaded via manifest

## Build Scripts

### For Firefox

**Linux/Mac:**
```bash
cd addon
./build-firefox.sh
```

**Windows:**
```cmd
cd addon
build-firefox.bat
```

This will:
- Copy `manifest-firefox.json` → `manifest.json`
- `background-unified.js` stays as-is (works for both browsers)

### For Chrome

**Linux/Mac:**
```bash
cd addon
./build-chrome.sh
```

**Windows:**
```cmd
cd addon
build-chrome.bat
```

This will:
- Copy `manifest-chrome.json` → `manifest.json`
- `background-unified.js` stays as-is (works for both browsers)

## Testing

### Firefox
1. Run the Firefox build script
2. Open Firefox
3. Navigate to `about:debugging#/runtime/this-firefox`
4. Click "Load Temporary Add-on"
5. Select any file in the `addon` folder

### Chrome
1. Run the Chrome build script
2. Open Chrome
3. Navigate to `chrome://extensions/`
4. Enable "Developer mode"
5. Click "Load unpacked"
6. Select the `addon` folder

## File Structure

- `manifest-firefox.json` - Firefox-specific manifest (source)
- `manifest-chrome.json` - Chrome-specific manifest (source)
- `manifest.json` - **Generated file** (do not edit directly, edit the browser-specific versions)
- `background-unified.js` - Unified background script that works for both browsers
- `browser-polyfill.js` - Mozilla's WebExtension polyfill

## Important Notes

⚠️ **Do not commit `manifest.json`** after running build scripts - it's a generated file.

⚠️ **Always run the appropriate build script** before testing or packaging for each browser.

## Packaging for Distribution

### Firefox
```bash
cd addon
./build-firefox.sh
zip -r ../easyform-firefox.zip . -x "*.sh" -x "*.bat" -x "manifest-chrome.json" -x "BUILD-README.md"
```

### Chrome
```bash
cd addon
./build-chrome.sh
zip -r ../easyform-chrome.zip . -x "*.sh" -x "*.bat" -x "manifest-firefox.json" -x "BUILD-README.md"
```

## How It Works

The magic is in `background-unified.js` at the top:

```javascript
// Load browser-polyfill for service workers (Chrome)
// In Firefox, it's already loaded via manifest.json
try {
  if (typeof importScripts !== 'undefined') {
    importScripts('browser-polyfill.js');
  }
} catch (e) {
  // Already loaded via manifest or not in service worker context
}
```

This way you maintain **one single background script** for both browsers!
