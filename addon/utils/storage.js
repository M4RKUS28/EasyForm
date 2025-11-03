// Storage utilities for EasyForm extension
import { STORAGE_KEYS } from './constants.js';

/**
 * Get stored request ID for a tab
 */
export async function getStoredRequestId(tabId) {
  const data = await chrome.storage.local.get([STORAGE_KEYS.getRequestId(tabId)]);
  return data[STORAGE_KEYS.getRequestId(tabId)] || null;
}

/**
 * Store request ID for a tab
 */
export async function storeRequestId(tabId, requestId) {
  await chrome.storage.local.set({
    [STORAGE_KEYS.getRequestId(tabId)]: requestId
  });
}

/**
 * Get stored start time for a tab
 */
export async function getStoredStartTime(tabId) {
  const data = await chrome.storage.local.get([STORAGE_KEYS.getStartTime(tabId)]);
  return data[STORAGE_KEYS.getStartTime(tabId)] || null;
}

/**
 * Store start time for a tab
 */
export async function storeStartTime(tabId, startTime) {
  await chrome.storage.local.set({
    [STORAGE_KEYS.getStartTime(tabId)]: startTime
  });
}

/**
 * Cleanup request storage for a tab
 */
export async function cleanupRequestStorage(tabId) {
  await chrome.storage.local.remove([
    STORAGE_KEYS.getRequestId(tabId),
    STORAGE_KEYS.getStartTime(tabId)
  ]);
  console.log('[EasyForm Storage] 🧹 Cleaned up storage for tab:', tabId);
}

/**
 * Get config from storage
 */
export async function getConfig() {
  return new Promise((resolve) => {
    chrome.storage.sync.get(
      ['backendUrl', 'mode', 'executionMode', 'analysisMode', 'apiToken'],
      (result) => {
        resolve({
          backendUrl: result.backendUrl,
          mode: result.mode,
          executionMode: result.executionMode || result.mode,
          analysisMode: result.analysisMode || 'basic',
          apiToken: result.apiToken || ''
        });
      }
    );
  });
}

/**
 * Set config in storage
 */
export async function setConfig(updates) {
  return new Promise((resolve) => {
    chrome.storage.sync.set(updates, () => {
      resolve();
    });
  });
}
