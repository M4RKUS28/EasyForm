// API communication with backend
import { CONFIG, STORAGE_KEYS, ANALYSIS_STATES } from '../utils/constants.js';
import { getConfig, storeRequestId, storeStartTime } from '../utils/storage.js';
import { startPolling } from './polling.js';
import { captureFullPageScreenshots } from './screenshots.js';
import { notifyError } from './notifications.js';

/**
 * Send page data to backend and start async processing
 */
export async function handlePageAnalysisAsync(pageData, tabId) {
  try {
    // Get config from storage
    const config = await getConfig();
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const executionMode = config.executionMode || CONFIG.mode;
    const analysisMode = config.analysisMode || 'basic';
    const apiToken = config.apiToken || '';

    console.log('[EasyForm API] 📝 Config:', {
      executionMode,
      analysisMode
    });

    // Capture screenshots if in extended mode
    let screenshots = null;
    if (analysisMode === 'extended') {
      console.log('[EasyForm API] 📸 Extended mode - capturing screenshots...');
      screenshots = await captureFullPageScreenshots(tabId);
      console.log(`[EasyForm API] ✅ Captured ${screenshots.length} screenshots`);
    }

    // Construct async analyze endpoint
    const backendUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/form/analyze/async`
      : `${baseUrl}/api/form/analyze/async`;

    console.log('[EasyForm API] 🌐 Sending to async backend:', backendUrl);

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

    console.log('[EasyForm API] 📦 Request body prepared:', {
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

    console.log('[EasyForm API] 📡 Backend response status:', response.status, response.statusText);

    if (response.status === 409) {
      // Conflict: User already has active request
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

    // Store request ID and start time for this tab
    const requestId = result.request_id;
    const startTime = Date.now();

    await storeRequestId(tabId, requestId);
    await storeStartTime(tabId, startTime);

    console.log('[EasyForm API] 💾 Request created:', requestId);
    console.log('[EasyForm API] ▶️ Starting polling...');

    // Start polling for status
    startPolling(requestId, tabId, startTime, executionMode);

  } catch (error) {
    console.error('[EasyForm API] ❌ Error handling page analysis:', error);
    await chrome.storage.local.set({
      [STORAGE_KEYS.ANALYSIS_STATE]: ANALYSIS_STATES.ERROR,
      [STORAGE_KEYS.ANALYSIS_ERROR]: error.message
    });
    notifyError(tabId, error.message);
    throw error;
  }
}

/**
 * Check backend health
 */
export async function checkHealth() {
  try {
    const config = await getConfig();
    const baseUrl = config.backendUrl || CONFIG.backendUrl;
    const apiToken = config.apiToken || '';

    const healthUrl = baseUrl.endsWith('/')
      ? `${baseUrl}api/health`
      : `${baseUrl}/api/health`;

    const headers = {};
    if (apiToken) {
      headers['Authorization'] = `Bearer ${apiToken}`;
    }

    const response = await fetch(healthUrl, { method: 'GET', headers, signal: AbortSignal.timeout(5000) });

    if (response.ok) {
      return { healthy: true };
    } else {
      return { healthy: false, error: `Backend returned ${response.status}` };
    }
  } catch (error) {
    return { healthy: false, error: error.message };
  }
}
