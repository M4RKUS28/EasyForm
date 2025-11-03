// Background Service Worker for EasyForm

const CONFIG = {
  backendUrl: 'https://easyform.markus28.de',
  mode: 'automatic' // 'automatic' or 'manual'
};

// Store last analysis result
let lastAnalysisResult = null;
let lastError = null;

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
    analyzePage(request.tabId)
      .then(() => {
        sendResponse({
          success: true,
          actionsCount: lastAnalysisResult?.actions?.length || 0
        });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
    return true;
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
    lastError = null;

    // Request page data from content script
    const response = await chrome.tabs.sendMessage(tabId, {
      action: 'getPageData'
    });

    if (response && response.data) {
      await handlePageAnalysis(response.data, tabId);
    }
  } catch (error) {
    console.error('Error analyzing page:', error);
    lastError = error.message;
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

    console.log('Sending to backend:', backendUrl);

    // Prepare headers
    const headers = {
      'Content-Type': 'application/json',
    };

    // Add authorization header if token is present
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    // Send data to backend
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(pageData)
    });

    if (!response.ok) {
      throw new Error(`Backend returned ${response.status}: ${response.statusText}`);
    }

    const result = await response.json();
    lastAnalysisResult = result;
    lastError = null;

    // Process based on mode
    if (result.actions && result.actions.length > 0) {
      if (mode === 'automatic') {
        // Automatic mode: execute immediately
        await chrome.tabs.sendMessage(tabId, {
          action: 'executeActions',
          actions: result.actions,
          autoExecute: true
        });
        notifyInfo(tabId, `Executed ${result.actions.length} action(s)`);
      } else {
        // Manual mode: show overlay
        await chrome.tabs.sendMessage(tabId, {
          action: 'showOverlay',
          actions: result.actions
        });
      }

      return { success: true, actionsCount: result.actions.length, mode };
    } else {
      notifyInfo(tabId, 'No actions to execute');
      return { success: true, actionsCount: 0 };
    }
  } catch (error) {
    console.error('Error handling page analysis:', error);
    lastError = error.message;
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
