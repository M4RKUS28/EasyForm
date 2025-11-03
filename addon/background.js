// Background Service Worker for EasyForm

const CONFIG = {
  backendUrl: 'https://easyform.markus28.de',
  mode: 'automatic' // 'automatic' or 'manual'
};

// Store last analysis result (kept for backward compatibility)
let lastAnalysisResult = null;
let lastError = null;

// Analysis state keys for chrome.storage.local
const STORAGE_KEYS = {
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

// Initialize extension
chrome.runtime.onInstalled.addListener(() => {
  console.log('EasyForm installed');

  // Set default config
  chrome.storage.sync.get(['backendUrl', 'mode'], (result) => {
    if (!result.backendUrl) {
      chrome.storage.sync.set({ backendUrl: CONFIG.backendUrl });
    }
    if (!result.mode) {
      chrome.storage.sync.set({ mode: CONFIG.mode });
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
    // Start analysis asynchronously - don't wait for completion
    // This prevents timeout issues with long-running operations
    analyzePage(request.tabId).catch(error => {
      console.error('[EasyForm] Analysis error:', error);
    });

    // Respond immediately to acknowledge the request
    sendResponse({ success: true, started: true });
    return false; // Don't keep the message channel open
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
    chrome.storage.sync.get(['backendUrl', 'mode', 'apiToken'], (result) => {
      sendResponse({
        backendUrl: result.backendUrl || CONFIG.backendUrl,
        mode: result.mode || CONFIG.mode,
        apiToken: result.apiToken || ''
      });
    });
    return true;
  }

  if (request.action === 'setConfig') {
    const updates = {};
    if (request.backendUrl !== undefined) updates.backendUrl = request.backendUrl;
    if (request.mode !== undefined) updates.mode = request.mode;
    if (request.apiToken !== undefined) updates.apiToken = request.apiToken;

    chrome.storage.sync.set(updates, () => {
      sendResponse({ success: true });
    });
    return true;
  }

  if (request.action === 'getLastResult') {
    sendResponse({
      result: lastAnalysisResult,
      error: lastError
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

  if (request.action === 'executeStoredActions') {
    if (lastAnalysisResult && lastAnalysisResult.actions) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, {
            action: 'executeActions',
            actions: lastAnalysisResult.actions,
            autoExecute: true
          });
        }
      });
      sendResponse({ success: true });
    } else {
      sendResponse({ error: 'No actions to execute' });
    }
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

// Main function to analyze page
async function analyzePage(tabId) {
  try {
    console.log('[EasyForm] Starting page analysis for tab:', tabId);
    lastError = null;

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
      await handlePageAnalysis(response.data, tabId);
    } else {
      console.error('[EasyForm] No data received from content script');
    }
  } catch (error) {
    console.error('[EasyForm] Error analyzing page:', error);
    lastError = error.message;

    // Set error state in storage
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });

    notifyError(tabId, error.message);
  }
}

// Send page data to backend and process response
async function handlePageAnalysis(pageData, tabId) {
  try {
    // Get config from storage
    const config = await chrome.storage.sync.get(['backendUrl', 'mode', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const mode = config.mode || CONFIG.mode;
    const apiToken = config.apiToken || '';

    // Construct full API endpoint
    const backendUrl = baseUrl.endsWith('/') ? `${baseUrl}api/form/analyze` : `${baseUrl}/api/form/analyze`;

    console.log('[EasyForm] Sending to backend:', backendUrl);
    console.log('[EasyForm] Mode:', mode);
    console.log('[EasyForm] Has API token:', !!apiToken);

    // Prepare headers
    const headers = {
      'Content-Type': 'application/json',
    };

    // Add authorization header if token is present
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Transform pageData to match backend schema
    const requestBody = {
      html: pageData.html,
      visible_text: pageData.text,  // Backend expects 'visible_text' not 'text'
      clipboard_text: pageData.clipboard,
      mode: 'basic'
    };

    console.log('[EasyForm] Request body prepared:', {
      htmlLength: requestBody.html?.length,
      visibleTextLength: requestBody.visible_text?.length,
      clipboardLength: requestBody.clipboard_text?.length,
      mode: requestBody.mode
    });

    // Send data to backend
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody)
    });

    console.log('[EasyForm] Backend response status:', response.status, response.statusText);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('[EasyForm] Backend error response:', errorText);
      throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    console.log('[EasyForm] Backend result:', {
      status: result.status,
      actionsCount: result.actions?.length,
      fieldsDetected: result.fields_detected
    });

    lastAnalysisResult = result;
    lastError = null;

    // Store result in chrome.storage
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.SUCCESS,
      [STORAGE_KEYS.ANALYSIS_RESULT]: result,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

    // Process based on mode
    if (result.actions && result.actions.length > 0) {
      console.log('[EasyForm] Processing actions in mode:', mode);
      if (mode === 'automatic') {
        // Automatic mode: execute immediately
        console.log('[EasyForm] Auto-executing', result.actions.length, 'actions');
        await chrome.tabs.sendMessage(tabId, {
          action: 'executeActions',
          actions: result.actions,
          autoExecute: true
        });
        notifyInfo(tabId, `Executed ${result.actions.length} action(s)`);
      } else {
        // Manual mode: show overlay
        console.log('[EasyForm] Showing overlay with', result.actions.length, 'actions');
        await chrome.tabs.sendMessage(tabId, {
          action: 'showOverlay',
          actions: result.actions
        });
      }

      return { success: true, actionsCount: result.actions.length, mode };
    } else {
      console.log('[EasyForm] No actions to execute');
      notifyInfo(tabId, 'No actions to execute');
      return { success: true, actionsCount: 0 };
    }
  } catch (error) {
    console.error('[EasyForm] Error handling page analysis:', error);
    lastError = error.message;

    // Set error state in storage
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });

    notifyError(tabId, error.message);
    throw error;
  }
}

// Health check function
async function checkHealth() {
  try {
    // Get config from storage
    const config = await chrome.storage.sync.get(['backendUrl', 'apiToken']);
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    // Construct health endpoint
    const healthUrl = baseUrl.endsWith('/') ? `${baseUrl}api/health` : `${baseUrl}/api/health`;

    console.log('Checking health:', healthUrl);

    // Prepare headers
    const headers = {};
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Call health endpoint
    const response = await fetch(healthUrl, {
      method: 'GET',
      headers
    });

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
