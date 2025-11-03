// Background Service Worker for EasyForm
// Now uses async API with polling

const CONFIG = {
  backendUrl: 'https://easyform.markus28.de',
  mode: 'automatic' // 'automatic' or 'manual'
};

// Storage keys - now per-tab for request IDs
const STORAGE_KEYS = {
  getRequestId: (tabId) => `request_${tabId}`,
  getStartTime: (tabId) => `startTime_${tabId}`,
  ANALYSIS_STATE: 'analysisState',
  ANALYSIS_RESULT: 'analysisResult',
  ANALYSIS_ERROR: 'analysisError'
};

// Analysis states
const ANALYSIS_STATES = {
  IDLE: 'idle',
  RUNNING: 'running',
  SUCCESS: 'success',
  ERROR: 'error'
};

// Polling configuration
const POLL_INTERVAL_MS = 1000; // Poll every 1 second
const POLL_TIMEOUT_MS = 300000; // 5 minutes timeout

// Active polling intervals (tabId -> intervalId)
const activePolls = new Map();

// Initialize extension
chrome.runtime.onInstalled.addListener(() => {
  console.log('EasyForm installed');

  // Set default config
  chrome.storage.sync.get(['backendUrl', 'mode', 'executionMode', 'analysisMode'], (result) => {
    if (!result.backendUrl) {
      chrome.storage.sync.set({ backendUrl: CONFIG.backendUrl });
    }
    // Migrate old 'mode' to 'executionMode' if needed
    if (!result.executionMode) {
      chrome.storage.sync.set({ executionMode: result.mode || CONFIG.mode });
    }
    if (!result.analysisMode) {
      chrome.storage.sync.set({ analysisMode: 'basic' });
    }
  });

  // Create context menu
  chrome.contextMenus.create({
    id: 'analyze-page',
    title: 'Analyze page with EasyForm',
    contexts: ['page', 'selection']
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'analyze-page') {
    analyzePage(tab.id);
  }
});

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener((command) => {
  if (command === 'analyze-page') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        analyzePage(tabs[0].id);
      }
    });
  } else if (command === 'toggle-overlay') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'toggleOverlay' });
      }
    });
  }
});

// Handle messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Handle analyzePage from popup (has tabId parameter)
  if (request.action === 'analyzePage' && request.tabId) {
    analyzePage(request.tabId).catch(error => {
      console.error('[EasyForm] Analysis error:', error);
    });
    sendResponse({ success: true, started: true });
    return false;
  }

  // Handle analyzePage from content script (has data parameter)
  if (request.action === 'analyzePage' && request.data) {
    handlePageAnalysis(request.data, sender.tab.id)
      .then(sendResponse)
      .catch(error => {
        sendResponse({ error: error.message });
      });
    return true;
  }

  if (request.action === 'getConfig') {
    chrome.storage.sync.get(['backendUrl', 'mode', 'executionMode', 'analysisMode', 'apiToken'], (result) => {
      sendResponse({
        backendUrl: result.backendUrl || CONFIG.backendUrl,
        mode: result.mode || CONFIG.mode, // Backward compat
        executionMode: result.executionMode || result.mode || CONFIG.mode,
        analysisMode: result.analysisMode || 'basic',
        apiToken: result.apiToken || ''
      });
    });
    return true;
  }

  if (request.action === 'setConfig') {
    const updates = {};
    if (request.backendUrl !== undefined) updates.backendUrl = request.backendUrl;
    if (request.mode !== undefined) updates.mode = request.mode; // Backward compat
    if (request.executionMode !== undefined) updates.executionMode = request.executionMode;
    if (request.analysisMode !== undefined) updates.analysisMode = request.analysisMode;
    if (request.apiToken !== undefined) updates.apiToken = request.apiToken;

    chrome.storage.sync.set(updates, () => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (request.action === 'getAnalysisState') {
    chrome.storage.local.get([
      STORAGE_KEYS.ANALYSIS_STATE,
      STORAGE_KEYS.ANALYSIS_RESULT,
      STORAGE_KEYS.ANALYSIS_ERROR
    ], (data) => {
      sendResponse({
        state: data[STORAGE_KEYS.ANALYSIS_STATE] || ANALYSIS_STATES.IDLE,
        result: data[STORAGE_KEYS.ANALYSIS_RESULT],
        error: data[STORAGE_KEYS.ANALYSIS_ERROR]
      });
    });
    return true;
  }

  if (request.action === 'cancelRequest' && request.tabId) {
    cancelRequest(request.tabId)
      .then(() => sendResponse({ success: true }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (request.action === 'healthCheck') {
    checkHealth()
      .then(sendResponse)
      .catch(error => {
        sendResponse({ healthy: false, error: error.message });
      });
    return true;
  }
});

/**
 * Capture full-page screenshots with scrolling
 */
async function captureFullPageScreenshots(tabId) {
  try {
    console.log('[EasyForm] Capturing full page screenshots...');

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

    console.log('[EasyForm] Page dimensions:', {
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
      console.log(`[EasyForm] Captured screenshot ${screenshotCount} at Y=${currentY}`);

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

    console.log(`[EasyForm] Captured ${screenshots.length} screenshots`);
    return screenshots;

  } catch (error) {
    console.error('[EasyForm] Error capturing screenshots:', error);
    throw error;
  }
}

// Main function to analyze page
async function analyzePage(tabId) {
  try {
    console.log('[EasyForm] Starting page analysis for tab:', tabId);

    // Check if there's already an active request for this tab
    const existingRequestId = await getStoredRequestId(tabId);
    if (existingRequestId) {
      console.log('[EasyForm] Tab already has active request:', existingRequestId);
      throw new Error('Analysis already running for this tab. Please cancel it first.');
    }

    // Set state to RUNNING
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.RUNNING,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

    // Request page data from content script
    console.log('[EasyForm] Requesting page data from content script...');
    const response = await chrome.tabs.sendMessage(tabId, {
      action: 'getPageData'
    });

    if (response && response.data) {
      console.log('[EasyForm] Received page data:', {
        url: response.data.url,
        textLength: response.data.text?.length,
        htmlLength: response.data.html?.length,
        clipboardLength: response.data.clipboard?.length
      });
      await handlePageAnalysisAsync(response.data, tabId);
    } else {
      console.error('[EasyForm] No data received from content script');
      throw new Error('Failed to get page data');
    }
  } catch (error) {
    console.error('[EasyForm] Error analyzing page:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
    notifyError(tabId, error.message);
  }
}

// Send page data to backend and start async processing
async function handlePageAnalysisAsync(pageData, tabId) {
  try {
    // Get config from storage
    const config = await chrome.storage.sync.get(['backendUrl', 'mode', 'executionMode', 'analysisMode', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const executionMode = config.executionMode || config.mode || CONFIG.mode;
    const analysisMode = config.analysisMode || 'basic';
    const apiToken = config.apiToken || '';

    console.log('[EasyForm] Config:', {
      executionMode,
      analysisMode
    });

    // Capture screenshots if in extended mode
    let screenshots = null;
    if (analysisMode === 'extended') {
      console.log('[EasyForm] Extended mode - capturing screenshots...');
      screenshots = await captureFullPageScreenshots(tabId);
      console.log(`[EasyForm] Captured ${screenshots.length} screenshots`);
    }

    // Construct async analyze endpoint
    const backendUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/analyze/async`
      : `${baseUrl}/api/form/analyze/async`;

    console.log('[EasyForm] Sending to async backend:', backendUrl);

    // Prepare headers
    const headers = {
      'Content-Type': 'application/json',
    };

    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Transform pageData to match backend schema
    const requestBody = {
      html: pageData.html,
      visible_text: pageData.text,
      clipboard_text: pageData.clipboard,
      mode: analysisMode,
      screenshots: screenshots
    };

    console.log('[EasyForm] Request body prepared:', {
      htmlLength: requestBody.html?.length,
      visibleTextLength: requestBody.visible_text?.length,
      clipboardLength: requestBody.clipboard_text?.length,
      mode: requestBody.mode,
      screenshotCount: screenshots?.length || 0
    });

    // Send data to backend (async endpoint)
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });

    console.log('[EasyForm] Backend response status:', response.status, response.statusText);

    if (response.status === 409) {
      // Conflict: User already has active request
      const errorData = await response.json();
      throw new Error(errorData.detail || 'You already have an active request');
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[EasyForm] Backend error response:', errorText);
      throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('[EasyForm] Backend result:', result);

    // Store request ID and start time for this tab
    const requestId = result.request_id;
    const startTime = Date.now();

    await chrome.storage.local.set({
      [STORAGE_KEYS.getRequestId(tabId)]: requestId,
      [STORAGE_KEYS.getStartTime(tabId)]: startTime
    });

    console.log('[EasyForm] Request created:', requestId);
    console.log('[EasyForm] Starting polling...');

    // Start polling for status
    startPolling(requestId, tabId, startTime, executionMode);

  } catch (error) {
    console.error('[EasyForm] Error handling page analysis:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
    notifyError(tabId, error.message);
    throw error;
  }
}

// Start polling for request status
function startPolling(requestId, tabId, startTime, mode) {
  // Clear any existing poll for this tab
  stopPolling(tabId);

  console.log('[EasyForm] ▶️ Starting poll for tab:', tabId, 'request:', requestId, 'mode:', mode);

  const intervalId = setInterval(async () => {
    try {
      await pollRequestStatus(requestId, tabId, startTime, mode);
    } catch (error) {
      console.error('[EasyForm] ❌ Polling error:', error);
      stopPolling(tabId);
      await chrome.storage.local.set({
        [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
        [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
      });
    }
  }, POLL_INTERVAL_MS);

  activePolls.set(tabId, intervalId);
  console.log('[EasyForm] 📊 Active polls after start:', activePolls.size, 'intervalId:', intervalId);
}

// Poll request status
async function pollRequestStatus(requestId, tabId, startTime, mode) {
  const elapsed = Date.now() - startTime;

  // Check timeout
  if (elapsed > POLL_TIMEOUT_MS) {
    console.error('[EasyForm] Polling timeout');
    stopPolling(tabId);
    await cancelRequest(tabId);
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
  console.log('[EasyForm] Poll status:', status.status, `(${Math.round(elapsed / 1000)}s)`);

  // Handle different statuses
  if (status.status === 'completed') {
    console.log('[EasyForm] 🏁 Status completed - checking if polling is still active');
    // Check if polling is still active - this prevents race condition where multiple polls
    // see the 'completed' status before the interval is cleared
    if (!activePolls.has(tabId)) {
      console.log('[EasyForm] ⚠️ Polling already stopped for tab:', tabId, '- ignoring completion');
      return;
    }
    console.log('[EasyForm] ✓ Polling is active, proceeding with completion');
    stopPolling(tabId);
    await handleCompletedRequest(requestId, tabId, mode);
  } else if (status.status === 'failed') {
    console.log('[EasyForm] ❌ Status failed - checking if polling is still active');
    if (!activePolls.has(tabId)) {
      console.log('[EasyForm] ⚠️ Polling already stopped for tab:', tabId, '- ignoring failure');
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

// Handle completed request - fetch actions and execute
async function handleCompletedRequest(requestId, tabId, mode) {
  try {
    console.log('[EasyForm] ⭐ handleCompletedRequest called for requestId:', requestId, 'tabId:', tabId, 'mode:', mode);

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
    console.log('[EasyForm] Actions received:', result.actions.length);

    // Store result in chrome.storage
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.SUCCESS,
      [STORAGE_KEYS.ANALYSIS_RESULT]: result,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

    // Process based on mode
    if (result.actions && result.actions.length > 0) {
      console.log('[EasyForm] 📋 Processing', result.actions.length, 'actions in mode:', mode);
      if (mode === 'automatic') {
        // Automatic mode: execute immediately
        console.log('[EasyForm] 🤖 Auto-executing', result.actions.length, 'actions for tab:', tabId);
        const messageResponse = await chrome.tabs.sendMessage(tabId, {
          action: 'executeActions',
          actions: result.actions,
          autoExecute: true
        });
        console.log('[EasyForm] ✅ Execution response:', messageResponse);
        notifyInfo(tabId, `Executed ${result.actions.length} action(s)`);
      } else {
        // Manual mode: show overlay
        console.log('[EasyForm] 👁️ Showing overlay with', result.actions.length, 'actions');
        await chrome.tabs.sendMessage(tabId, {
          action: 'showOverlay',
          actions: result.actions
        });
      }
    } else {
      console.log('[EasyForm] ⚠️ No actions to execute');
      notifyInfo(tabId, 'No actions to execute');
    }

    // Cleanup
    await cleanupRequestStorage(tabId);

  } catch (error) {
    console.error('[EasyForm] Error handling completed request:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
    notifyError(tabId, error.message);
  }
}

// Cancel request
async function cancelRequest(tabId) {
  const requestId = await getStoredRequestId(tabId);

  if (!requestId) {
    console.log('[EasyForm] No active request to cancel for tab:', tabId);
    return;
  }

  console.log('[EasyForm] Canceling request:', requestId);

  try {
    // Get config for API call
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

    if (response.status === 204 || response.status === 404) {
      console.log('[EasyForm] Request canceled successfully');
    } else {
      console.warn('[EasyForm] Unexpected status when canceling:', response.status);
    }
  } catch (error) {
    console.error('[EasyForm] Error canceling request:', error);
  } finally {
    // Always stop polling and cleanup storage
    stopPolling(tabId);
    await cleanupRequestStorage(tabId);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.IDLE,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });
  }
}

// Stop polling for a tab
function stopPolling(tabId) {
  const intervalId = activePolls.get(tabId);
  if (intervalId) {
    clearInterval(intervalId);
    activePolls.delete(tabId);
    console.log('[EasyForm] ⏹️ Stopped polling for tab:', tabId, 'intervalId:', intervalId, 'activePolls size:', activePolls.size);
  } else {
    console.log('[EasyForm] ⚠️ stopPolling called but no active poll for tab:', tabId, 'activePolls size:', activePolls.size);
  }
}

// Get stored request ID for a tab
async function getStoredRequestId(tabId) {
  const data = await chrome.storage.local.get([STORAGE_KEYS.getRequestId(tabId)]);
  return data[STORAGE_KEYS.getRequestId(tabId)] || null;
}

// Cleanup request storage for a tab
async function cleanupRequestStorage(tabId) {
  await chrome.storage.local.remove([
    STORAGE_KEYS.getRequestId(tabId),
    STORAGE_KEYS.getStartTime(tabId)
  ]);
}

// Health check function
async function checkHealth() {
  try {
    const config = await chrome.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    const healthUrl = baseUrl.endsWith('/') ? `${baseUrl}api/health` : `${baseUrl}/api/health`;

    console.log('Checking health:', healthUrl);

    const headers = {};
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    const response = await fetch(healthUrl, { method: 'GET', headers });

    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();
    return { healthy: true, data: result };
  } catch (error) {
    console.error('Health check error:', error);
    throw error;
  }
}

// Notification helpers
function notifyError(tabId, message) {
  chrome.tabs.sendMessage(tabId, {
    action: 'showNotification',
    type: 'error',
    message: message
  }).catch(() => {
    console.error('Notification error:', message);
  });
}

function notifyInfo(tabId, message) {
  chrome.tabs.sendMessage(tabId, {
    action: 'showNotification',
    type: 'info',
    message: message
  }).catch(() => {
    console.log('Notification:', message);
  });
}

// Cleanup when tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  console.log('[EasyForm] Tab closed:', tabId);
  stopPolling(tabId);
  cleanupRequestStorage(tabId);
});

// Resume polling on extension reload if request is still active
chrome.runtime.onStartup.addListener(async () => {
  console.log('[EasyForm] Extension started, checking for active requests...');
  // Note: This won't work perfectly because we lose the activePolls Map on reload
  // But the storage-based state will persist
});
