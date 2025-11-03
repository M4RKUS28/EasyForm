// Screenshot capture functionality
// Handles full-page screenshots with scrolling

/**
 * Capture full-page screenshots with scrolling
 */
export async function captureFullPageScreenshots(tabId) {
  try {
    console.log('[EasyForm Screenshots] 📸 Starting full page capture...');

    // Get initial scroll position to restore later
    const initialScrollInfo = await chrome.tabs.sendMessage(tabId, {
      action: 'getScrollInfo'
    });
    const originalScrollX = initialScrollInfo.scrollX;
    const originalScrollY = initialScrollInfo.scrollY;

    // Scroll to top of page
    await chrome.tabs.sendMessage(tabId, {
      action: 'scrollToTop'
    });

    // Wait for scroll to complete
    await new Promise(resolve => setTimeout(resolve, 300));

    // Get page dimensions after scrolling to top
    const scrollInfo = await chrome.tabs.sendMessage(tabId, {
      action: 'getScrollInfo'
    });

    const viewportHeight = scrollInfo.viewportHeight;
    const scrollHeight = scrollInfo.scrollHeight;
    const screenshots = [];

    console.log('[EasyForm Screenshots] 📐 Page dimensions:', {
      viewportHeight,
      scrollHeight,
      estimatedScreenshots: Math.ceil(scrollHeight / viewportHeight)
    });

    // Capture screenshots while scrolling down
    let currentY = 0;
    let screenshotCount = 0;
    const maxScreenshots = 20; // Safety limit

    while (currentY < scrollHeight && screenshotCount < maxScreenshots) {
      // Capture current viewport
      const screenshot = await chrome.tabs.captureVisibleTab(null, {
        format: 'png',
        quality: 90
      });

      // Remove data URL prefix to get just base64 data
      const base64Data = screenshot.replace(/^data:image\/png;base64,/, '');
      screenshots.push(base64Data);

      screenshotCount++;
      console.log(`[EasyForm Screenshots] 📷 Captured screenshot ${screenshotCount} at Y=${currentY}`);

      // Scroll down by viewport height
      currentY += viewportHeight;

      if (currentY < scrollHeight) {
        await chrome.tabs.sendMessage(tabId, {
          action: 'scrollToPosition',
          x: 0,
          y: currentY
        });

        // Wait for scroll and render
        await new Promise(resolve => setTimeout(resolve, 200));
      }
    }

    // Restore original scroll position
    await chrome.tabs.sendMessage(tabId, {
      action: 'restoreScroll',
      x: originalScrollX,
      y: originalScrollY
    });

    console.log(`[EasyForm Screenshots] ✅ Captured ${screenshots.length} screenshots`);
    return screenshots;

  } catch (error) {
    console.error('[EasyForm Screenshots] ❌ Error capturing screenshots:', error);
    throw error;
  }
}
