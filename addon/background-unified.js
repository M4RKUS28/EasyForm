// Unified Background Script for EasyForm
// Combines all background modules into one file for compatibility

// Note: browser-polyfill.js is loaded via manifest.json
// The global 'browser' object is provided by the polyfill

// ===== CONSTANTS =====
const CONFIG = {
  backendUrl: 'https://easyform-ai.com',
  mode: 'automatic'
};

const STORAGE_KEYS = {
  getRequestId: (tabId) => `request_${tabId}`,
  getStartTime: (tabId) => `startTime_${tabId}`,
  getTabState: (tabId) => `tabState_${tabId}`  // Unified state object
};

const ANALYSIS_STATES = {
  IDLE: 'idle',
  RUNNING: 'running',
  SUCCESS: 'success',
  ERROR: 'error'
};

// Helper functions for unified tab state
async function getTabState(tabId) {
  const data = await browser.storage.local.get(STORAGE_KEYS.getTabState(tabId));
  return data[STORAGE_KEYS.getTabState(tabId)] || {
    status: ANALYSIS_STATES.IDLE,
    progress: null,
    error: null,
    actions: null,
    mode: null,
    executed: false,
    timestamp: Date.now()
  };
}

async function updateTabState(tabId, updates) {
  const currentState = await getTabState(tabId);
  const newState = {
    ...currentState,
    ...updates,
    timestamp: Date.now()
  };
  await browser.storage.local.set({
    [STORAGE_KEYS.getTabState(tabId)]: newState
  });
  console.log('[EasyForm State] Updated tab', tabId, ':', newState);
  return newState;
}

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 1200000; // 20 minutes

// ===== STORAGE UTILITIES =====
async function getStoredRequestId(tabId) {
  const data = await browser.storage.local.get([STORAGE_KEYS.getRequestId(tabId)]);
  return data[STORAGE_KEYS.getRequestId(tabId)] || null;
}

async function storeRequestId(tabId, requestId) {
  await browser.storage.local.set({
    [STORAGE_KEYS.getRequestId(tabId)]: requestId
  });
}

async function storeStartTime(tabId, startTime) {
  await browser.storage.local.set({
    [STORAGE_KEYS.getStartTime(tabId)]: startTime
  });
}

async function cleanupRequestStorage(tabId) {
  await browser.storage.local.remove([
    STORAGE_KEYS.getRequestId(tabId),
    STORAGE_KEYS.getStartTime(tabId)
  ]);
  console.log('[EasyForm Storage] 🧹 Cleaned up storage for tab:', tabId);
}

async function getConfig() {
  const result = await browser.storage.sync.get(
    ['backendUrl', 'mode', 'executionMode', 'analysisMode', 'apiToken', 'quality', 'autoOpenPreview']
  );

  return {
    backendUrl: result.backendUrl,
    mode: result.mode,
    executionMode: result.executionMode || result.mode,
    analysisMode: result.analysisMode || 'basic',
    apiToken: result.apiToken || '',
    quality: result.quality || 'fast',
    autoOpenPreview: result.autoOpenPreview !== undefined ? result.autoOpenPreview : true
  };
}

async function setConfig(updates) {
  await browser.storage.sync.set(updates);
}

// ===== NOTIFICATIONS =====
function notifyError(tabId, message) {
  console.error('[EasyForm Notifications] ❌ Error:', message);
}

function notifyInfo(tabId, message) {
  console.log('[EasyForm Notifications] ℹ️ Info:', message);
}

// ===== SCREENSHOTS =====
async function captureFullPageScreenshots(tabId) {
  try {
    console.log('[EasyForm Screenshots] 📸 Starting full page capture...');

    const initialScrollInfo = await browser.tabs.sendMessage(tabId, {
      action: 'getScrollInfo'
    });
    const originalScrollX = initialScrollInfo.scrollX;
    const originalScrollY = initialScrollInfo.scrollY;

    await browser.tabs.sendMessage(tabId, { action: 'scrollToTop' });
    await new Promise(resolve => setTimeout(resolve, 500));

    const scrollInfo = await browser.tabs.sendMessage(tabId, {
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

    let currentY = 0;
    let screenshotCount = 0;
    const maxScreenshots = 20;

    while (currentY < scrollHeight && screenshotCount < maxScreenshots) {
      const screenshot = await browser.tabs.captureVisibleTab(null, {
        format: 'png',
        quality: 90
      });

      const base64Data = screenshot.replace(/^data:image\/png;base64,/, '');
      screenshots.push(base64Data);

      screenshotCount++;
      console.log(`[EasyForm Screenshots] 📷 Captured screenshot ${screenshotCount} at Y=${currentY}`);

      currentY += viewportHeight;

      if (currentY < scrollHeight) {
        await browser.tabs.sendMessage(tabId, {
          action: 'scrollToPosition',
          x: 0,
          y: currentY
        });
        await new Promise(resolve => setTimeout(resolve, 600));
      }
    }

    await browser.tabs.sendMessage(tabId, {
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

// ===== API =====
async function handlePageAnalysisAsync(pageData, tabId) {
  try {
    const config = await getConfig();
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const executionMode = config.executionMode || CONFIG.mode;
    const analysisMode = config.analysisMode || 'basic';
  const quality = config.quality || 'fast';
    const apiToken = config.apiToken || '';

    console.log('[EasyForm API] 📝 Config:', { executionMode, analysisMode, quality });

    let screenshots = null;
    if (analysisMode === 'extended') {
      console.log('[EasyForm API] 📸 Extended mode - capturing screenshots...');
      screenshots = await captureFullPageScreenshots(tabId);
      console.log(`[EasyForm API] ✅ Captured ${screenshots.length} screenshots`);
    }

    const backendUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/analyze/async`
      : `${baseUrl}/api/form/analyze/async`;

    console.log('[EasyForm API] 🌐 Sending to async backend:', backendUrl);

    const headers = { 'Content-Type': 'application/json' };
    if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

    // Load optional session instructions entered in the popup (fallback to legacy data if needed)
    let sessionInstructions = null;
    try {
      const storage = await browser.storage.local.get('sessionInstructions');
      if (typeof storage.sessionInstructions === 'string') {
        sessionInstructions = storage.sessionInstructions;
        if (sessionInstructions.length > 0) {
          console.log('[EasyForm API] � Using session instructions from popup');
        }
      }
    } catch (error) {
      console.warn('[EasyForm API] Could not load session instructions:', error);
    }

    if (sessionInstructions === null && typeof pageData?.sessionInstructions === 'string') {
      sessionInstructions = pageData.sessionInstructions;
    }

    if (sessionInstructions === null && typeof pageData?.clipboard === 'string') {
      sessionInstructions = pageData.clipboard;
    }

    const requestBody = {
      html: pageData.html,
      visible_text: pageData.text,
      clipboard_text: sessionInstructions,
      mode: analysisMode,
      quality: quality,
      screenshots: screenshots
    };

    console.log('[EasyForm API] 📦 Request body prepared:', {
      htmlLength: requestBody.html?.length,
      visibleTextLength: requestBody.visible_text?.length,
      sessionInstructionsLength: requestBody.clipboard_text?.length,
      mode: requestBody.mode,
      screenshotCount: screenshots?.length || 0
    });

    const response = await fetch(backendUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });

    console.log('[EasyForm API] 📡 Backend response status:', response.status, response.statusText);

    if (response.status === 409) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'You already have an active request');
    }

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[EasyForm API] ❌ Backend error response:', errorText);
      throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('[EasyForm API] ✅ Backend result:', result);

    const requestId = result.request_id;
    const startTime = Date.now();

    await storeRequestId(tabId, requestId);
    await storeStartTime(tabId, startTime);

    console.log('[EasyForm API] 💾 Request created:', requestId);
    console.log('[EasyForm API] ▶️ Starting polling...');

    startPolling(requestId, tabId, startTime, executionMode);

  } catch (error) {
    console.error('[EasyForm API] ❌ Error handling page analysis:', error);
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.ERROR,
      error: error.message,
      progress: null
    });
    notifyError(tabId, error.message);
    throw error;
  }
}

async function checkHealth() {
  try {
    const config = await getConfig();
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    const healthUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/health`
      : `${baseUrl}/api/health`;

    const headers = {};
    if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

    const response = await fetch(healthUrl, {
      method: 'GET',
      headers,
      signal: AbortSignal.timeout(5000)
    });

    if (response.ok) {
      return { healthy: true };
    } else {
      return { healthy: false, error: `Backend returned ${response.status}` };
    }
  } catch (error) {
    return { healthy: false, error: error.message };
  }
}

// ===== POLLING =====
const activePolls = new Map();

function startPolling(requestId, tabId, startTime, mode) {
  stopPolling(tabId);

  console.log('[EasyForm Polling] ▶️ Starting poll for tab:', tabId, 'request:', requestId, 'mode:', mode);

  const intervalId = setInterval(async () => {
    try {
      await pollRequestStatus(requestId, tabId, startTime, mode);
    } catch (error) {
      console.error('[EasyForm Polling] ❌ Polling error:', error);
      stopPolling(tabId);
      await updateTabState(tabId, {
        status: ANALYSIS_STATES.ERROR,
        error: error.message,
        progress: null
      });
    }
  }, POLL_INTERVAL_MS);

  activePolls.set(tabId, intervalId);
  console.log('[EasyForm Polling] 📊 Active polls after start:', activePolls.size, 'intervalId:', intervalId);
}

function stopPolling(tabId) {
  const intervalId = activePolls.get(tabId);
  if (intervalId) {
    clearInterval(intervalId);
    activePolls.delete(tabId);
    console.log('[EasyForm Polling] ⏹️ Stopped polling for tab:', tabId, 'intervalId:', intervalId, 'activePolls size:', activePolls.size);
  } else {
    console.log('[EasyForm Polling] ⚠️ stopPolling called but no active poll for tab:', tabId, 'activePolls size:', activePolls.size);
  }
}

async function pollRequestStatus(requestId, tabId, startTime, mode) {
  const elapsed = Date.now() - startTime;

  if (elapsed > POLL_TIMEOUT_MS) {
    console.error('[EasyForm Polling] ⏱️ Polling timeout');
    stopPolling(tabId);
    await cancelRequestInternal(tabId);
    const timeoutMinutes = Math.round(POLL_TIMEOUT_MS / 60000);
    const timeoutMessage = `Analysis timeout (${timeoutMinutes} minutes)`;
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.ERROR,
      error: timeoutMessage,
      progress: null
    });
    notifyError(tabId, timeoutMessage);
    return;
  }

  const config = await browser.storage.sync.get(['backendUrl', 'apiToken']);
  const baseUrl = config.backendUrl || CONFIG.backendUrl;
  const apiToken = config.apiToken || '';

  const statusUrl = baseUrl.endsWith('/')
    ? `${baseUrl}api/form/request/${requestId}/status`
    : `${baseUrl}/api/form/request/${requestId}/status`;

  const headers = {};
  if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

  const response = await fetch(statusUrl, { method: 'GET', headers });

  if (!response.ok) {
    throw new Error(`Status check failed: ${response.status}`);
  }

  const status = await response.json();
  console.log('[EasyForm Polling] 📡 Poll status:', status.status, `(${Math.round(elapsed / 1000)}s)`);

  // Extract latest progress message from backend
  let progressMessage = null;
  if (status.progress && Array.isArray(status.progress) && status.progress.length > 0) {
    const latestProgress = status.progress[status.progress.length - 1];
    progressMessage = latestProgress.message || null;

    // Update progress in state
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.RUNNING,
      progress: progressMessage
    });
  }

  if (status.status === 'completed') {
    console.log('[EasyForm Polling] 🏁 Status completed - checking if polling is still active');
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
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.ERROR,
      error: status.error_message || 'Analysis failed',
      progress: null
    });
    notifyError(tabId, status.error_message || 'Analysis failed');
    await cleanupRequestStorage(tabId);
  }
}

async function handleCompletedRequest(requestId, tabId, mode) {
  try {
    console.log('[EasyForm Polling] ⭐ handleCompletedRequest called for requestId:', requestId, 'tabId:', tabId, 'mode:', mode);

    const config = await browser.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    const actionsUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/request/${requestId}/actions`
      : `${baseUrl}/api/form/request/${requestId}/actions`;

    const headers = {};
    if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

    const response = await fetch(actionsUrl, { method: 'GET', headers });

    if (!response.ok) {
      throw new Error(`Failed to fetch actions: ${response.status}`);
    }

    const result = await response.json();
    console.log('[EasyForm Polling] 📋 Actions received:', result.actions.length);

    // UNIFIED LOGIC: Always store actions with mode
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.SUCCESS,
      progress: null,
      error: null,
      actions: result.actions,
      mode: mode,
      executed: false  // Initially not executed
    });

    if (result.actions && result.actions.length > 0) {
      console.log('[EasyForm Polling] 📋 Processing', result.actions.length, 'actions in mode:', mode);

      if (mode === 'automatic') {
        // AUTOMATIC MODE: Execute immediately without showing overlay
        console.log('[EasyForm Polling] 🤖 Auto-mode: executing silently');

        const messageResponse = await browser.tabs.sendMessage(tabId, {
          action: 'executeActions',
          actions: result.actions,
          autoExecute: true
        });
        console.log('[EasyForm Polling] ✅ Execution response:', messageResponse);

        // Mark as executed
        await updateTabState(tabId, {
          executed: true
        });

        notifyInfo(tabId, `Executed ${result.actions.length} action(s)`);
      } else {
        // MANUAL MODE: Check if auto-open preview is enabled
        const config = await getConfig();
        const autoOpenPreview = config.autoOpenPreview !== undefined ? config.autoOpenPreview : true;

        if (autoOpenPreview) {
          console.log('[EasyForm Polling] 👁️ Manual mode: showing overlay for user review (auto-open enabled)');
          await browser.tabs.sendMessage(tabId, {
            action: 'showOverlay',
            actions: result.actions
          });
        } else {
          console.log('[EasyForm Polling] 📋 Manual mode: preview saved but not auto-opened (user disabled auto-open)');
          notifyInfo(tabId, `${result.actions.length} action(s) ready - click preview to review`);
        }
      }
    } else {
      console.log('[EasyForm Polling] ⚠️ No actions to execute');
      notifyInfo(tabId, 'No actions to execute');
    }

    await cleanupRequestStorage(tabId);

  } catch (error) {
    console.error('[EasyForm Polling] ❌ Error handling completed request:', error);
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.ERROR,
      error: error.message,
      progress: null
    });
    notifyError(tabId, error.message);
  }
}

async function cancelRequestInternal(tabId) {
  const requestId = await getStoredRequestId(tabId);

  if (!requestId) {
    console.log('[EasyForm Polling] No active request to cancel for tab:', tabId);
    return;
  }

  console.log('[EasyForm Polling] 🚫 Canceling request:', requestId);

  try {
    const config = await browser.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    const deleteUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/request/${requestId}`
      : `${baseUrl}/api/form/request/${requestId}`;

    const headers = {};
    if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;

    const response = await fetch(deleteUrl, { method: 'DELETE', headers });

    if (response.ok || response.status === 404) {
      console.log('[EasyForm Polling] ✅ Request canceled');
    } else {
      console.warn('[EasyForm Polling] ⚠️ Failed to cancel request:', response.status);
    }

    await cleanupRequestStorage(tabId);

    await updateTabState(tabId, {
      status: ANALYSIS_STATES.IDLE,
      progress: null,
      error: null
    });

  } catch (error) {
    console.error('[EasyForm Polling] ❌ Error canceling request:', error);
    throw error;
  }
}

async function cancelRequest(tabId) {
  stopPolling(tabId);
  await cancelRequestInternal(tabId);
}

async function cleanupTab(tabId) {
  stopPolling(tabId);
  await cleanupRequestStorage(tabId);

  // Clean up unified tab state
  await browser.storage.local.remove([
    STORAGE_KEYS.getTabState(tabId)
  ]);

  console.log('[EasyForm Storage] 🧹 Cleaned up tab state for tab:', tabId);
}

// ===== MAIN =====
browser.runtime.onInstalled.addListener(async () => {
  console.log('[EasyForm] 🚀 Extension installed');

  const result = await browser.storage.sync.get(['backendUrl', 'mode', 'executionMode', 'analysisMode', 'quality']);

  if (!result.backendUrl) {
    await browser.storage.sync.set({ backendUrl: CONFIG.backendUrl });
  }
  if (!result.executionMode) {
    await browser.storage.sync.set({ executionMode: result.mode || CONFIG.mode });
  }
  if (!result.analysisMode) {
    await browser.storage.sync.set({ analysisMode: 'basic' });
  }
  if (!result.quality) {
    await browser.storage.sync.set({ quality: 'fast' });
  }

  browser.contextMenus.create({
    id: 'analyze-page',
    title: 'Analyze page with EasyForm',
    contexts: ['page', 'selection']
  });
});

browser.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'analyze-page') {
    analyzePage(tab.id);
  }
});

browser.commands.onCommand.addListener(async (command) => {
  if (command === 'analyze-page') {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]) analyzePage(tabs[0].id);
  } else if (command === 'toggle-overlay') {
    const tabs = await browser.tabs.query({ active: true, currentWindow: true });
    if (tabs[0]) {
      browser.tabs.sendMessage(tabs[0].id, { action: 'toggleOverlay' });
    }
  }
});

browser.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'analyzePage' && request.tabId) {
    analyzePage(request.tabId).catch(error => {
      console.error('[EasyForm] ❌ Analysis error:', error);
    });
    sendResponse({ success: true, started: true });
    return false;
  }

  if (request.action === 'analyzePage' && request.data) {
    handlePageAnalysis(request.data, sender.tab.id)
      .then(sendResponse)
      .catch(error => {
        sendResponse({ error: error.message });
      });
    return true;
  }

  if (request.action === 'getConfig') {
    getConfig().then(config => {
      sendResponse({
        backendUrl: config.backendUrl || CONFIG.backendUrl,
        mode: config.mode || CONFIG.mode,
        executionMode: config.executionMode || CONFIG.mode,
        analysisMode: config.analysisMode || 'basic',
        apiToken: config.apiToken || '',
        quality: config.quality || 'fast',
        autoOpenPreview: config.autoOpenPreview !== undefined ? config.autoOpenPreview : true
      });
    });
    return true;
  }

  if (request.action === 'setConfig') {
    const updates = {};
    if (request.backendUrl !== undefined) updates.backendUrl = request.backendUrl;
    if (request.mode !== undefined) updates.mode = request.mode;
    if (request.executionMode !== undefined) updates.executionMode = request.executionMode;
    if (request.analysisMode !== undefined) updates.analysisMode = request.analysisMode;
    if (request.apiToken !== undefined) updates.apiToken = request.apiToken;
    if (request.quality !== undefined) updates.quality = request.quality;
    if (request.autoOpenPreview !== undefined) updates.autoOpenPreview = request.autoOpenPreview;

    setConfig(updates)
      .then(() => {
        sendResponse({ success: true });
      })
      .catch((error) => {
        console.error('[EasyForm] Error saving config:', error);
        sendResponse({ success: false, error: error.message });
      });
    return true;
  }

  if (request.action === 'getAnalysisState') {
    (async () => {
      // Use tabId from request, or fallback to sender's tab (for content scripts)
      const tabId = request.tabId || sender.tab?.id;
      if (!tabId) {
        sendResponse({
          status: ANALYSIS_STATES.IDLE,
          progress: null,
          error: null,
          actions: null,
          mode: null,
          executed: false
        });
        return;
      }
      const tabState = await getTabState(tabId);
      sendResponse(tabState);
    })();
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

  if (request.action === 'resetState') {
    (async () => {
      try {
        const tabId = request.tabId;

        if (tabId) {
          stopPolling(tabId);
          await cleanupRequestStorage(tabId);

          // Reset to idle state (clears everything)
          await updateTabState(tabId, {
            status: ANALYSIS_STATES.IDLE,
            progress: null,
            error: null,
            actions: null,
            mode: null,
            executed: false
          });
        } else {
          // Fallback: stop all polls if no tab specified
          for (const activeTabId of Array.from(activePolls.keys())) {
            stopPolling(activeTabId);
            await cleanupRequestStorage(activeTabId);

            await updateTabState(activeTabId, {
              status: ANALYSIS_STATES.IDLE,
              progress: null,
              error: null,
              actions: null,
              mode: null,
              executed: false
            });
          }
        }

        sendResponse({ success: true });
      } catch (error) {
        console.error('[EasyForm] ❌ Error resetting state:', error);
        sendResponse({ success: false, error: error.message });
      }
    })();
    return true;
  }

  if (request.action === 'clearActions') {
    (async () => {
      try {
        // Use tabId from request, or fallback to sender's tab (for content scripts)
        const tabId = request.tabId || sender.tab?.id;
        if (!tabId) {
          sendResponse({ success: false, error: 'No tab ID provided' });
          return;
        }

        // Clear actions and reset to idle (Option A from user requirements)
        await updateTabState(tabId, {
          status: ANALYSIS_STATES.IDLE,
          progress: null,
          error: null,
          actions: null,
          mode: null,
          executed: false
        });

        sendResponse({ success: true });
      } catch (error) {
        console.error('[EasyForm] ❌ Error clearing actions:', error);
        sendResponse({ success: false, error: error.message });
      }
    })();
    return true;
  }

  if (request.action === 'markExecuted') {
    (async () => {
      try {
        // Use tabId from request, or fallback to sender's tab (for content scripts)
        const tabId = request.tabId || sender.tab?.id;
        if (!tabId) {
          sendResponse({ success: false, error: 'No tab ID provided' });
          return;
        }

        // Mark actions as executed
        await updateTabState(tabId, {
          executed: true
        });

        sendResponse({ success: true });
      } catch (error) {
        console.error('[EasyForm] ❌ Error marking executed:', error);
        sendResponse({ success: false, error: error.message });
      }
    })();
    return true;
  }

  return false;
});

async function analyzePage(tabId) {
  try {
    console.log('[EasyForm] 🎯 Starting page analysis for tab:', tabId);

    const existingRequestId = await getStoredRequestId(tabId);
    if (existingRequestId) {
      console.log('[EasyForm] ⚠️ Tab already has active request:', existingRequestId);
      throw new Error('Analysis already running for this tab. Please cancel it first.');
    }

    // Get current config to store mode in state
    const config = await getConfig();
    const executionMode = config.executionMode || CONFIG.mode;

    await updateTabState(tabId, {
      status: ANALYSIS_STATES.RUNNING,
      progress: 'Starting analysis...',
      error: null,
      mode: executionMode
    });

    console.log('[EasyForm] 📨 Requesting page data from content script...');
    const response = await browser.tabs.sendMessage(tabId, {
      action: 'getPageData'
    });

    if (response && response.data) {
  let sessionInstructionsLength = 0;
      try {
        const storage = await browser.storage.local.get('sessionInstructions');
        if (typeof storage.sessionInstructions === 'string') {
          sessionInstructionsLength = storage.sessionInstructions.length;
        }
      } catch (error) {
        console.warn('[EasyForm] ⚠️ Could not read session instructions length:', error);
      }

      console.log('[EasyForm] ✅ Received page data:', {
        url: response.data.url,
        textLength: response.data.text?.length,
        htmlLength: response.data.html?.length,
        sessionInstructionsLength
      });
      await handlePageAnalysisAsync(response.data, tabId);
    } else {
      console.error('[EasyForm] ❌ No data received from content script');
      throw new Error('Failed to get page data');
    }
  } catch (error) {
    console.error('[EasyForm] ❌ Error analyzing page:', error);
    await updateTabState(tabId, {
      status: ANALYSIS_STATES.ERROR,
      error: error.message,
      progress: null
    });
  }
}

browser.tabs.onRemoved.addListener((tabId) => {
  console.log('[EasyForm] 🗑️ Tab closed:', tabId);
  cleanupTab(tabId);
});
