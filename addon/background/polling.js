// Polling logic for form analysis requests
import { CONFIG, STORAGE_KEYS, ANALYSIS_STATES, POLL_INTERVAL_MS, POLL_TIMEOUT_MS } from '../utils/constants.js';
import { getStoredRequestId, cleanupRequestStorage } from '../utils/storage.js';
import { notifyError, notifyInfo } from './notifications.js';

// Active polling intervals (tabId -> intervalId)
const activePolls = new Map();

/**
 * Start polling for request status
 */
export function startPolling(requestId, tabId, startTime, mode) {
  // Clear any existing poll for this tab
  stopPolling(tabId);

  console.log('[EasyForm Polling] ▶️ Starting poll for tab:', tabId, 'request:', requestId, 'mode:', mode);

  const intervalId = setInterval(async () => {
    try {
      await pollRequestStatus(requestId, tabId, startTime, mode);
    } catch (error) {
      console.error('[EasyForm Polling] ❌ Polling error:', error);
      stopPolling(tabId);
      await chrome.storage.local.set({
        [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
        [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
      });
    }
  }, POLL_INTERVAL_MS);

  activePolls.set(tabId, intervalId);
  console.log('[EasyForm Polling] 📊 Active polls after start:', activePolls.size, 'intervalId:', intervalId);
}

/**
 * Stop polling for a tab
 */
export function stopPolling(tabId) {
  const intervalId = activePolls.get(tabId);
  if (intervalId) {
    clearInterval(intervalId);
    activePolls.delete(tabId);
    console.log('[EasyForm Polling] ⏹️ Stopped polling for tab:', tabId, 'intervalId:', intervalId, 'activePolls size:', activePolls.size);
  } else {
    console.log('[EasyForm Polling] ⚠️ stopPolling called but no active poll for tab:', tabId, 'activePolls size:', activePolls.size);
  }
}

/**
 * Poll request status
 */
async function pollRequestStatus(requestId, tabId, startTime, mode) {
  const elapsed = Date.now() - startTime;

  // Check timeout
  if (elapsed > POLL_TIMEOUT_MS) {
    console.error('[EasyForm Polling] ⏱️ Polling timeout');
    stopPolling(tabId);
    await cancelRequestInternal(tabId);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: 'Analysis timeout (5 minutes)'
    });
    notifyError(tabId, 'Analysis timeout');
    return;
  }

  // Get config for API call
  const config = await chrome.storage.sync.get(['backendUrl', 'apiToken']);
  const baseUrl = config.backendUrl || CONFIG.backendUrl;
  const apiToken = config.apiToken || '';

  // Construct status endpoint
  const statusUrl = baseUrl.endsWith('/')
    ? `${baseUrl}api/form/request/${requestId}/status`
    : `${baseUrl}/api/form/request/${requestId}/status`;

  // Prepare headers
  const headers = {};
  if (apiToken) {
    headers['Authorization'] = `Bearer ${apiToken}`;
  }

  // Fetch status
  const response = await fetch(statusUrl, { method: 'GET', headers });

  if (!response.ok) {
    throw new Error(`Status check failed: ${response.status}`);
  }

  const status = await response.json();
  console.log('[EasyForm Polling] 📡 Poll status:', status.status, `(${Math.round(elapsed / 1000)}s)`);

  // Handle different statuses
  if (status.status === 'completed') {
    console.log('[EasyForm Polling] 🏁 Status completed - checking if polling is still active');
    // Check if polling is still active - this prevents race condition where multiple polls
    // see the 'completed' status before the interval is cleared
    if (!activePolls.has(tabId)) {
      console.log('[EasyForm Polling] ⚠️ Polling already stopped for tab:', tabId, '- ignoring completion');
      return;
    }
    console.log('[EasyForm Polling] ✓ Polling is active, proceeding with completion');
    stopPolling(tabId);
    await handleCompletedRequest(requestId, tabId, mode);
  } else if (status.status === 'failed') {
    console.log('[EasyForm Polling] ❌ Status failed - checking if polling is still active');
    if (!activePolls.has(tabId)) {
      console.log('[EasyForm Polling] ⚠️ Polling already stopped for tab:', tabId, '- ignoring failure');
      return;
    }
    stopPolling(tabId);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: status.error_message || 'Analysis failed'
    });
    notifyError(tabId, status.error_message || 'Analysis failed');
    await cleanupRequestStorage(tabId);
  }
  // For 'pending' or 'processing', just continue polling
}

/**
 * Handle completed request - fetch actions and execute
 */
async function handleCompletedRequest(requestId, tabId, mode) {
  try {
    console.log('[EasyForm Polling] ⭐ handleCompletedRequest called for requestId:', requestId, 'tabId:', tabId, 'mode:', mode);

    // Get config for API call
    const config = await chrome.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    // Construct actions endpoint
    const actionsUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/request/${requestId}/actions`
      : `${baseUrl}/api/form/request/${requestId}/actions`;

    // Prepare headers
    const headers = {};
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Fetch actions
    const response = await fetch(actionsUrl, { method: 'GET', headers });

    if (!response.ok) {
      throw new Error(`Failed to fetch actions: ${response.status}`);
    }

    const result = await response.json();
    console.log('[EasyForm Polling] 📋 Actions received:', result.actions.length);

    // Store result in chrome.storage
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.SUCCESS,
      [STORAGE_KEYS.ANALYSIS_RESULT]: result,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

    // Process based on mode
    if (result.actions && result.actions.length > 0) {
      console.log('[EasyForm Polling] 📋 Processing', result.actions.length, 'actions in mode:', mode);
      if (mode === 'automatic') {
        // Automatic mode: execute immediately
        console.log('[EasyForm Polling] 🤖 Auto-executing', result.actions.length, 'actions for tab:', tabId);
        const messageResponse = await chrome.tabs.sendMessage(tabId, {
          action: 'executeActions',
          actions: result.actions,
          autoExecute: true
        });
        console.log('[EasyForm Polling] ✅ Execution response:', messageResponse);
        notifyInfo(tabId, `Executed ${result.actions.length} action(s)`);
      } else {
        // Manual mode: show overlay
        console.log('[EasyForm Polling] 👁️ Showing overlay with', result.actions.length, 'actions');
        await chrome.tabs.sendMessage(tabId, {
          action: 'showOverlay',
          actions: result.actions
        });
      }
    } else {
      console.log('[EasyForm Polling] ⚠️ No actions to execute');
      notifyInfo(tabId, 'No actions to execute');
    }

    // Cleanup
    await cleanupRequestStorage(tabId);

  } catch (error) {
    console.error('[EasyForm Polling] ❌ Error handling completed request:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
    notifyError(tabId, error.message);
  }
}

/**
 * Cancel request (internal helper)
 */
async function cancelRequestInternal(tabId) {
  const requestId = await getStoredRequestId(tabId);

  if (!requestId) {
    console.log('[EasyForm Polling] No active request to cancel for tab:', tabId);
    return;
  }

  console.log('[EasyForm Polling] 🚫 Canceling request:', requestId);

  try {
    // Get config
    const config = await chrome.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    // Construct delete endpoint
    const deleteUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/request/${requestId}`
      : `${baseUrl}/api/form/request/${requestId}`;

    // Prepare headers
    const headers = {};
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Delete request
    const response = await fetch(deleteUrl, { method: 'DELETE', headers });

    if (response.ok || response.status === 404) {
      console.log('[EasyForm Polling] ✅ Request canceled');
    } else {
      console.warn('[EasyForm Polling] ⚠️ Failed to cancel request:', response.status);
    }

    // Cleanup storage regardless
    await cleanupRequestStorage(tabId);

    // Update state
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.IDLE,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

  } catch (error) {
    console.error('[EasyForm Polling] ❌ Error canceling request:', error);
    throw error;
  }
}

/**
 * Public cancel request function
 */
export async function cancelRequest(tabId) {
  stopPolling(tabId);
  await cancelRequestInternal(tabId);
}

/**
 * Cleanup tab when closed
 */
export function cleanupTab(tabId) {
  stopPolling(tabId);
  cleanupRequestStorage(tabId);
}
