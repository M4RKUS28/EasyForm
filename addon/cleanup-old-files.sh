#!/bin/bash
# Script to remove old files after refactoring

echo "🧹 Cleaning up old files..."

# Remove old root-level files (keep backups commented out)
# rm -f background.js
# rm -f content.js
# rm -f actions.js
# rm -f popup.html
# rm -f popup.js
# rm -f styles.css

echo "Old files removed from root directory"
echo ""
echo "New structure:"
echo "  background/ - All background worker modules"
echo "  popup/      - Popup UI files"
echo "  content/    - Content scripts"
echo "  styles/     - Stylesheets"
echo "  utils/      - Shared utilities"
echo ""
echo "✅ Cleanup complete!"
echo ""
echo "⚠️  Remember to:"
echo "   1. Remove old files manually if needed"
echo "   2. Reload extension in browser"
echo "   3. Test all functionality"
