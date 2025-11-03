// Minimal Popup Script for EasyForm

let statusCheckInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
  await checkBackendHealth();
  await loadConfig();
  await loadStatus();
  setupEventListeners();

  // Check analysis state on popup open
  await checkAnalysisState();

  // Start polling for analysis state changes
  startStatusPolling();
});

// Stop polling when popup is closed/unloaded
window.addEventListener('beforeunload', () => {
  stopStatusPolling();
});

async function checkBackendHealth() {
  try {
    console.log('[EasyForm Popup] 🏥 Checking backend health...');
    const response = await chrome.runtime.sendMessage({ action: 'healthCheck' });
    console.log('[EasyForm Popup] Health check response:', response);

    if (response.healthy) {
      // Backend is healthy - show green indicator
      console.log('[EasyForm Popup] ✅ Backend is healthy');
      setHealthStatus(true);
      clearError();
    } else {
      // Backend is not healthy
      console.warn('[EasyForm Popup] ⚠️ Backend is not healthy:', response.error);
      showError(response.error || 'Backend health check failed');
    }
  } catch (error) {
    // Health check failed
    console.error('[EasyForm Popup] ❌ Health check failed:', error);
    showError(error.message || 'Cannot connect to backend');
  }
}

async function loadConfig() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getConfig' });
    const executionMode = response.executionMode || response.mode || 'automatic'; // Backward compat
    const analysisMode = response.analysisMode || 'basic';

    // Set dropdown values
    document.getElementById('executionMode').value = executionMode;
    document.getElementById('analysisMode').value = analysisMode;
  } catch (error) {
    console.error('Error loading config:', error);
  }
}

async function loadStatus() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getLastResult' });

    if (response.error) {
      showError(response.error);
    } else if (response.result && response.result.actions) {
      const count = response.result.actions.length;
      updateInfo(`${count} action${count !== 1 ? 's' : ''} found`);
    }
  } catch (error) {
    // Ignore - no last result available
  }
}

function setupEventListeners() {
  // Execution mode dropdown
  document.getElementById('executionMode').addEventListener('change', async (e) => {
    await setConfig({ executionMode: e.target.value, mode: e.target.value }); // mode for backward compat
  });

  // Analysis mode dropdown
  document.getElementById('analysisMode').addEventListener('change', async (e) => {
    await setConfig({ analysisMode: e.target.value });
  });

  // Start button
  document.getElementById('startBtn').addEventListener('click', async () => {
    await handleStartClick();
  });

  // Cancel button
  document.getElementById('cancelBtn').addEventListener('click', async () => {
    await handleCancelClick();
  });
}

async function setConfig(config) {
  try {
    await chrome.runtime.sendMessage({
      action: 'setConfig',
      ...config
    });
  } catch (error) {
    console.error('Error setting config:', error);
  }
}

function updateInfo(text) {
  document.getElementById('infoText').textContent = text;
}

function setHealthStatus(isHealthy) {
  const statusDot = document.getElementById('statusDot');
  if (isHealthy) {
    statusDot.classList.remove('error');
  } else {
    statusDot.classList.add('error');
  }
}

function showError(message) {
  const statusDot = document.getElementById('statusDot');
  const errorDiv = document.getElementById('errorMessage');

  statusDot.classList.add('error');
  errorDiv.textContent = message;
  errorDiv.classList.add('show');
}

function clearError() {
  const statusDot = document.getElementById('statusDot');
  const errorDiv = document.getElementById('errorMessage');

  statusDot.classList.remove('error');
  errorDiv.textContent = '';
  errorDiv.classList.remove('show');
}

async function handleStartClick() {
  const startBtn = document.getElementById('startBtn');

  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    console.log('[EasyForm Popup] 🎯 Start clicked for tab:', tab?.id);

    if (!tab) {
      throw new Error('No active tab found');
    }

    // Clear previous state
    clearError();
    updateInfo('Starting analysis...');
    startBtn.disabled = true;
    startBtn.textContent = 'Running...';

    console.log('[EasyForm Popup] 📤 Sending analyzePage message to background...');
    // Send message to background to START analysis (doesn't wait for completion)
    const response = await chrome.runtime.sendMessage({
      action: 'analyzePage',
      tabId: tab.id
    });
    console.log('[EasyForm Popup] 📥 Received response:', response);

    if (response && response.started) {
      // Analysis started successfully - polling will update the UI
      console.log('[EasyForm Popup] ✅ Analysis started successfully');
      updateInfo('Analyzing page...');
    } else {
      throw new Error('Failed to start analysis');
    }
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error starting analysis:', error);
    showError(error.message);
    updateInfo('Error');
    const startBtn = document.getElementById('startBtn');
    startBtn.disabled = false;
    startBtn.textContent = 'Start';
  }
}

// Check current analysis state
async function checkAnalysisState() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getAnalysisState' });
    console.log('[EasyForm Popup] 📊 Analysis state:', response?.state);

    if (!response) return;

    const startBtn = document.getElementById('startBtn');
    const cancelBtn = document.getElementById('cancelBtn');

    switch (response.state) {
      case 'running':
        console.log('[EasyForm Popup] 🔄 State: running');
        startBtn.disabled = true;
        startBtn.textContent = 'Running...';
        startBtn.style.display = 'none';
        cancelBtn.classList.add('show');
        updateInfo('Analyzing page...');
        clearError();
        break;

      case 'success':
        console.log('[EasyForm Popup] ✅ State: success');
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        cancelBtn.classList.remove('show');
        if (response.result && response.result.actions) {
          const count = response.result.actions.length;
          console.log('[EasyForm Popup] 📋 Actions found:', count);
          updateInfo(`${count} action${count !== 1 ? 's' : ''} found`);
        } else {
          updateInfo('Analysis complete');
        }
        clearError();
        break;

      case 'error':
        console.log('[EasyForm Popup] ❌ State: error -', response.error);
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        cancelBtn.classList.remove('show');
        if (response.error) {
          showError(response.error);
          updateInfo('Analysis failed');
        }
        break;

      case 'idle':
      default:
        console.log('[EasyForm Popup] ⏸️ State: idle');
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        cancelBtn.classList.remove('show');
        break;
    }
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error checking analysis state:', error);
  }
}

// Handle cancel button click
async function handleCancelClick() {
  try {
    // Get current tab
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

    if (!tab) {
      throw new Error('No active tab found');
    }

    console.log('Canceling analysis for tab:', tab.id);

    // Send cancel request to background
    const response = await chrome.runtime.sendMessage({
      action: 'cancelRequest',
      tabId: tab.id
    });

    if (response && response.success) {
      updateInfo('Analysis canceled');
      clearError();
    } else {
      throw new Error(response.error || 'Failed to cancel');
    }
  } catch (error) {
    console.error('Error canceling analysis:', error);
    showError(error.message);
  }
}

// Start polling for status updates
function startStatusPolling() {
  // Clear any existing interval
  stopStatusPolling();

  // Poll every 500ms for status updates
  statusCheckInterval = setInterval(async () => {
    await checkAnalysisState();
  }, 500);
}

// Stop polling
function stopStatusPolling() {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
    statusCheckInterval = null;
  }
}
