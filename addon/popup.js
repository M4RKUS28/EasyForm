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
    const response = await chrome.runtime.sendMessage({ action: 'healthCheck' });

    if (response.healthy) {
      // Backend is healthy - show green indicator
      setHealthStatus(true);
      clearError();
    } else {
      // Backend is not healthy
      showError(response.error || 'Backend health check failed');
    }
  } catch (error) {
    // Health check failed
    showError(error.message || 'Cannot connect to backend');
  }
}

async function loadConfig() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getConfig' });
    const mode = response.mode || 'automatic';
    updateModeButtons(mode);
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
  // Mode toggle buttons
  document.getElementById('autoBtn').addEventListener('click', () => {
    setMode('automatic');
  });

  document.getElementById('manualBtn').addEventListener('click', () => {
    setMode('manual');
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

function updateModeButtons(mode) {
  const autoBtn = document.getElementById('autoBtn');
  const manualBtn = document.getElementById('manualBtn');

  autoBtn.classList.toggle('active', mode === 'automatic');
  manualBtn.classList.toggle('active', mode === 'manual');
}

async function setMode(mode) {
  try {
    await chrome.runtime.sendMessage({
      action: 'setConfig',
      mode
    });
    updateModeButtons(mode);
  } catch (error) {
    console.error('Error setting mode:', error);
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

    if (!tab) {
      throw new Error('No active tab found');
    }

    // Clear previous state
    clearError();
    updateInfo('Starting analysis...');
    startBtn.disabled = true;
    startBtn.textContent = 'Running...';

    // Send message to background to START analysis (doesn't wait for completion)
    const response = await chrome.runtime.sendMessage({
      action: 'analyzePage',
      tabId: tab.id
    });

    if (response && response.started) {
      // Analysis started successfully - polling will update the UI
      updateInfo('Analyzing page...');
    } else {
      throw new Error('Failed to start analysis');
    }
  } catch (error) {
    console.error('Error starting analysis:', error);
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

    if (!response) return;

    const startBtn = document.getElementById('startBtn');
    const cancelBtn = document.getElementById('cancelBtn');

    switch (response.state) {
      case 'running':
        startBtn.disabled = true;
        startBtn.textContent = 'Running...';
        startBtn.style.display = 'none';
        cancelBtn.classList.add('show');
        updateInfo('Analyzing page...');
        clearError();
        break;

      case 'success':
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        cancelBtn.classList.remove('show');
        if (response.result && response.result.actions) {
          const count = response.result.actions.length;
          updateInfo(`${count} action${count !== 1 ? 's' : ''} found`);
        } else {
          updateInfo('Analysis complete');
        }
        clearError();
        break;

      case 'error':
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
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        cancelBtn.classList.remove('show');
        break;
    }
  } catch (error) {
    console.error('Error checking analysis state:', error);
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
