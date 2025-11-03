// Main background script - coordinates all modules
import { CONFIG, STORAGE_KEYS, ANALYSIS_STATES } from '../utils/constants.js';
import { getStoredRequestId, getConfig, setConfig } from '../utils/storage.js';
import { handlePageAnalysisAsync, checkHealth } from './api.js';
import { cancelRequest, cleanupTab } from './polling.js';

// Initialize extension
chrome.runtime.onInstalled.addListener(() => {
  console.log('[EasyForm] 🚀 Extension installed');

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
      console.error('[EasyForm] ❌ Analysis error:', error);
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
    getConfig().then(config => {
      sendResponse({
        backendUrl: config.backendUrl || CONFIG.backendUrl,
        mode: config.mode || CONFIG.mode, // Backward compat
        executionMode: config.executionMode || CONFIG.mode,
        analysisMode: config.analysisMode || 'basic',
        apiToken: config.apiToken || ''
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

    setConfig(updates).then(() => {
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

// Main function to analyze page
async function analyzePage(tabId) {
  try {
    console.log('[EasyForm] 🎯 Starting page analysis for tab:', tabId);

    // Check if there's already an active request for this tab
    const existingRequestId = await getStoredRequestId(tabId);
    if (existingRequestId) {
      console.log('[EasyForm] ⚠️ Tab already has active request:', existingRequestId);
      throw new Error('Analysis already running for this tab. Please cancel it first.');
    }

    // Set state to RUNNING
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.RUNNING,
      [STORAGE_KEYS.ANALYSIS_ERROR]: null
    });

    // Request page data from content script
    console.log('[EasyForm] 📨 Requesting page data from content script...');
    const response = await chrome.tabs.sendMessage(tabId, {
      action: 'getPageData'
    });

    if (response && response.data) {
      console.log('[EasyForm] ✅ Received page data:', {
        url: response.data.url,
        textLength: response.data.text?.length,
        htmlLength: response.data.html?.length,
        clipboardLength: response.data.clipboard?.length
      });
      await handlePageAnalysisAsync(response.data, tabId);
    } else {
      console.error('[EasyForm] ❌ No data received from content script');
      throw new Error('Failed to get page data');
    }
  } catch (error) {
    console.error('[EasyForm] ❌ Error analyzing page:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
  }
}

// Cleanup when tab is closed
chrome.tabs.onRemoved.addListener((tabId) => {
  console.log('[EasyForm] 🗑️ Tab closed:', tabId);
  cleanupTab(tabId);
});
