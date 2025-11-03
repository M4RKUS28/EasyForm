// Notification utilities

/**
 * Show error notification
 */
export function notifyError(tabId, message) {
  console.error('[EasyForm Notifications] ❌ Error:', message);
  // Could add chrome.notifications here if needed
}

/**
 * Show info notification
 */
export function notifyInfo(tabId, message) {
  console.log('[EasyForm Notifications] ℹ️ Info:', message);
  // Could add chrome.notifications here if needed
}
