// Minimal Popup Script for EasyForm

const DEFAULT_BACKEND_URL = 'https://easyform-ai.com';

let statusCheckInterval = null;
let isCanceling = false;
let lastAnalysisState = null;
let lastAnalysisError = null;
let lastAnalysisProgress = null;
let cachedBackendUrl = DEFAULT_BACKEND_URL;
let infoResetTimeout = null;
let lastInfoMessage = 'Ready';
let lastPersistentInfoMessage = 'Ready';

document.addEventListener('DOMContentLoaded', async () => {
  setHealthStatus('pending'); // Set to orange initially
  await checkBackendHealth();
  await loadConfig();
  await loadStatus();
  await loadSessionInstructions();
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

browser.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === 'sync' && changes.backendUrl) {
    cachedBackendUrl = normalizeBackendUrl(changes.backendUrl.newValue) || DEFAULT_BACKEND_URL;
  }
});

async function checkBackendHealth() {
  try {
    console.log('[EasyForm Popup] 🏥 Checking backend health...');
    const response = await browser.runtime.sendMessage({ action: 'healthCheck' });
    console.log('[EasyForm Popup] Health check response:', response);

    if (response.healthy) {
      // Backend is healthy - show green indicator
      console.log('[EasyForm Popup] ✅ Backend is healthy');
    setHealthStatus('healthy');
    clearError();
    } else {
      // Backend is not healthy
      console.warn('[EasyForm Popup] ⚠️ Backend is not healthy:', response.error);
      setHealthStatus('unhealthy');
      showError(response.error || 'Backend health check failed');
    }
  } catch (error) {
    // Health check failed
    console.error('[EasyForm Popup] ❌ Health check failed:', error);
    setHealthStatus('unhealthy');
    showError(error.message || 'Cannot connect to backend');
  }
}

// Prevent multiple polling intervals from being created
let pollingStarted = false;

async function loadConfig() {
  try {
    const response = await browser.runtime.sendMessage({ action: 'getConfig' });
    const executionMode = response.executionMode || response.mode || 'automatic'; // Backward compat
    const analysisMode = response.analysisMode || 'basic';

    cachedBackendUrl = normalizeBackendUrl(response.backendUrl) || DEFAULT_BACKEND_URL;

    // Set toggle states (checked = automatic/extended, unchecked = manual/basic)
    document.getElementById('executionModeToggle').checked = (executionMode === 'automatic');
    document.getElementById('analysisModeToggle').checked = (analysisMode === 'extended');
  } catch (error) {
    console.error('Error loading config:', error);
  }
}

async function loadStatus() {
  try {
    const response = await browser.runtime.sendMessage({ action: 'getLastResult' });

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

async function loadSessionInstructions() {
  const instructionsInput = document.getElementById('sessionInstructionsInput');

  try {
    const storage = await browser.storage.local.get('sessionInstructions');
    const savedInstructions = storage.sessionInstructions;
    if (typeof savedInstructions === 'string' && savedInstructions.length > 0) {
      instructionsInput.value = savedInstructions;
      console.log('[EasyForm Popup] � Loaded saved session instructions:', savedInstructions.substring(0, 50) + '...');
    }
  } catch (error) {
    console.warn('[EasyForm Popup] ⚠️ Could not load session instructions:', error);
  }
}

function setupEventListeners() {
  // Execution mode toggle (checked = automatic, unchecked = manual)
  document.getElementById('executionModeToggle').addEventListener('change', async (e) => {
    const mode = e.target.checked ? 'automatic' : 'manual';
    await setConfig({ executionMode: mode, mode: mode }); // mode for backward compat
  });

  // Analysis mode toggle (checked = extended, unchecked = basic)
  document.getElementById('analysisModeToggle').addEventListener('change', async (e) => {
    const mode = e.target.checked ? 'extended' : 'basic';
    await setConfig({ analysisMode: mode });
  });

  // Start button
  document.getElementById('startBtn').addEventListener('click', async () => {
    await handleStartClick();
  });

  // Cancel button
  document.getElementById('cancelBtn').addEventListener('click', async () => {
    await handleCancelClick();
  });

  // Reset button
  document.getElementById('resetBtn').addEventListener('click', async () => {
    await handleResetClick();
  });

  document.getElementById('toggleOverlayBtn').addEventListener('click', async () => {
    await handleToggleOverlayClick();
  });

  document.getElementById('openSettingsBtn').addEventListener('click', () => {
    handleOpenSettingsClick();
  });

  document.getElementById('openBackendBtn').addEventListener('click', async () => {
    await handleOpenBackendClick();
  });

  // Instructions toggle button
  document.getElementById('instructionsToggle').addEventListener('click', () => {
    const toggle = document.getElementById('instructionsToggle');
    const content = document.getElementById('instructionsContent');
    const isExpanded = content.classList.contains('expanded');

    if (isExpanded) {
      content.classList.remove('expanded');
      toggle.classList.remove('active');
    } else {
      content.classList.add('expanded');
      toggle.classList.add('active');
    }
  });

  // Session instructions input - save to storage when edited
  const instructionsInput = document.getElementById('sessionInstructionsInput');
  let instructionsUpdateTimeout;
  
  instructionsInput.addEventListener('input', () => {
    // Debounce the update
    clearTimeout(instructionsUpdateTimeout);
    instructionsUpdateTimeout = setTimeout(async () => {
      const newValue = instructionsInput.value;
      console.log('[EasyForm Popup] 📝 Session instructions updated:', newValue.substring(0, 50) + '...');
      
      // Store the updated session instructions value
      try {
        await browser.storage.local.set({ sessionInstructions: newValue });
      } catch (error) {
        console.error('[EasyForm Popup] Error saving session instructions:', error);
      }
    }, 500);
  });

  // Listen for paste events (when user pastes text)
  instructionsInput.addEventListener('paste', () => {
    setTimeout(() => {
      console.log('[EasyForm Popup] 📋 Pasted into session instructions input');
    }, 10);
  });
}

async function setConfig(config) {
  try {
    if (config.backendUrl !== undefined) {
      cachedBackendUrl = normalizeBackendUrl(config.backendUrl) || DEFAULT_BACKEND_URL;
    }
    await browser.runtime.sendMessage({
      action: 'setConfig',
      ...config
    });
  } catch (error) {
    console.error('Error setting config:', error);
  }
}

function updateInfo(text, options = {}) {
  const { persistent = true } = options;
  if (persistent) {
    lastPersistentInfoMessage = text;
  }
  lastInfoMessage = text;
  document.getElementById('infoText').textContent = text;
}

function setTemporaryInfo(text, duration = 2000) {
  const fallbackMessage = lastPersistentInfoMessage;
  updateInfo(text, { persistent: false });
  clearTimeout(infoResetTimeout);
  infoResetTimeout = setTimeout(() => {
    if (lastInfoMessage === text) {
      updateInfo(fallbackMessage, { persistent: false });
    }
  }, duration);
}

function setHealthStatus(status) { // status can be 'healthy', 'unhealthy', 'pending'
  const statusDot = document.getElementById('statusDot');
  statusDot.classList.remove('error', 'warning');

  if (status === 'healthy') {
    // Green
  } else if (status === 'unhealthy') {
    statusDot.classList.add('error'); // Red
  } else {
    statusDot.classList.add('warning'); // Orange
  }
}

function showError(message, options = {}) {
  const { affectHealth = true } = options;
  const errorDiv = document.getElementById('errorMessage');

  if (affectHealth) {
    setHealthStatus('unhealthy');
  }
  errorDiv.textContent = message;
  errorDiv.classList.add('show');
}

function clearError(nextStatus = null) {
  if (nextStatus) {
    setHealthStatus(nextStatus);
  } else {
    const statusDot = document.getElementById('statusDot');
    statusDot.classList.remove('error');
  }

  const errorDiv = document.getElementById('errorMessage');
  errorDiv.textContent = '';
  errorDiv.classList.remove('show');
}

// Handle start button click
async function handleStartClick() {
  const startBtn = document.getElementById('startBtn');

  try {
    // Get current tab
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    console.log('[EasyForm Popup] 🎯 Start clicked for tab:', tab?.id);

    if (!tab) {
      throw new Error('No active tab found');
    }

  // Clear previous state
  setHealthStatus('pending');
  clearError();
    updateInfo('Starting analysis...');
    startBtn.disabled = true;
    startBtn.textContent = 'Running...';

    console.log('[EasyForm Popup] 📤 Sending analyzePage message to background...');
    // Send message to background to START analysis (doesn't wait for completion)
    const response = await browser.runtime.sendMessage({
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
    // Get current tab ID
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.id) {
      console.warn('[EasyForm Popup] ⚠️ No active tab found for state check');
      return;
    }

    const response = await browser.runtime.sendMessage({
      action: 'getAnalysisState',
      tabId: tab.id
    });
    if (!response) return;

    const currentStatus = response.status || 'idle';
    const currentProgress = response.progress || null;
    const currentError = response.error || null;
    const actions = response.actions || null;
    const executed = response.executed || false;

    // Check if state actually changed
    const stateChanged = (
      currentStatus !== lastAnalysisState ||
      currentError !== lastAnalysisError ||
      currentProgress !== lastAnalysisProgress
    );

    if (!stateChanged) {
      return;
    }

    lastAnalysisState = currentStatus;
    lastAnalysisError = currentError;
    lastAnalysisProgress = currentProgress;

    console.log('[EasyForm Popup] 📊 State changed:', { currentStatus, currentProgress, executed, actionsCount: actions?.length });

    const startBtn = document.getElementById('startBtn');
    const cancelBtn = document.getElementById('cancelBtn');
    const resetBtn = document.getElementById('resetBtn');

    resetBtn.style.display = 'none';
    resetBtn.disabled = false;
    resetBtn.textContent = 'Reset';
    cancelBtn.classList.remove('show');

    switch (currentStatus) {
      case 'running':
        setHealthStatus('pending');
        startBtn.disabled = true;
        startBtn.textContent = 'Running...';
        startBtn.style.display = 'none';
        cancelBtn.classList.add('show');
        // Show detailed progress message
        updateInfo(currentProgress || 'Analyzing page...');
        clearError();
        break;

      case 'success':
        setHealthStatus('healthy');
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        if (actions && actions.length > 0) {
          const count = actions.length;
          // Option B: Show executed status
          const statusText = executed ? ' ✓ executed' : '';
          console.log('[EasyForm Popup] 📋 Actions:', count, 'Executed:', executed);
          updateInfo(`${count} action${count !== 1 ? 's' : ''}${statusText}`);
        } else {
          updateInfo('Analysis complete');
        }
        clearError();
        break;

      case 'error':
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        resetBtn.style.display = 'block';
        if (currentError) {
          showError(currentError);
          updateInfo('Analysis failed');
        }
        break;

      case 'idle':
      default:
        startBtn.disabled = false;
        startBtn.textContent = 'Start';
        startBtn.style.display = 'block';
        updateInfo('Ready');
        clearError();
        break;
    }
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error checking analysis state:', error);
  }
}

// Handle cancel button click
async function handleCancelClick() {
  if (isCanceling) {
    console.log('[EasyForm Popup] ⏳ Cancel already in progress, ignoring extra click');
    return;
  }

  try {
    // Get current tab
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

    if (!tab) {
      throw new Error('No active tab found');
    }

    console.log('Canceling analysis for tab:', tab.id);

    const cancelBtn = document.getElementById('cancelBtn');
    cancelBtn.disabled = true;
    cancelBtn.textContent = 'Canceling...';
    isCanceling = true;

    // Send cancel request to background
    const response = await browser.runtime.sendMessage({
      action: 'cancelRequest',
      tabId: tab.id
    });

    if (response && response.success) {
      updateInfo('Analysis canceled');
      clearError();
      const startBtn = document.getElementById('startBtn');
      startBtn.disabled = false;
      startBtn.textContent = 'Start';
      startBtn.style.display = 'block';
      cancelBtn.classList.remove('show');
      cancelBtn.disabled = false;
      cancelBtn.textContent = 'Cancel';
    } else {
      throw new Error(response.error || 'Failed to cancel');
    }
  } catch (error) {
    console.error('Error canceling analysis:', error);
    showError(error.message);
    const cancelBtn = document.getElementById('cancelBtn');
    cancelBtn.disabled = false;
    cancelBtn.textContent = 'Cancel';
  } finally {
    isCanceling = false;
  }
}

// Handle reset button click
async function handleResetClick() {
  console.log('[EasyForm Popup] 🔄 Resetting state...');
  const resetBtn = document.getElementById('resetBtn');
  try {
    resetBtn.disabled = true;
    resetBtn.textContent = 'Resetting...';

    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });
    const tabId = tab?.id;

    const response = await browser.runtime.sendMessage({ action: 'resetState', tabId });
    if (response && response.success === false) {
      throw new Error(response.error || 'Could not reset state');
    }

    lastAnalysisState = null;
    lastAnalysisError = null;
    lastAnalysisProgress = null;

    setHealthStatus('pending');
    clearError();
    updateInfo('Ready');

    const startBtn = document.getElementById('startBtn');
    startBtn.disabled = false;
    startBtn.textContent = 'Start';
    startBtn.style.display = 'block';

  const cancelBtn = document.getElementById('cancelBtn');
  cancelBtn.classList.remove('show');

  const instructionsInput = document.getElementById('sessionInstructionsInput');
  instructionsInput.value = '';
  await browser.storage.local.remove('sessionInstructions');

    await checkBackendHealth();
    await checkAnalysisState();

  resetBtn.style.display = 'none';

    console.log('[EasyForm Popup] ✅ State reset successfully');
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error resetting state:', error);
    showError('Failed to reset state. Please close and reopen the popup.');
  } finally {
    resetBtn.disabled = false;
    resetBtn.textContent = 'Reset';
  }
}

async function handleToggleOverlayClick() {
  const errorMessage = 'Unable to toggle content window';
  try {
    const [tab] = await browser.tabs.query({ active: true, currentWindow: true });

    if (!tab?.id) {
      setTemporaryInfo('No active tab');
      return;
    }

    await browser.tabs.sendMessage(tab.id, { action: 'toggleOverlay' });
    setTemporaryInfo('Content window toggled');
    clearErrorIfMatches(errorMessage);
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error toggling overlay:', error);
    setTemporaryInfo('Toggle failed');
    showError(errorMessage, { affectHealth: false });
    setTimeout(() => {
      clearErrorIfMatches(errorMessage);
    }, 4000);
  }
}

function handleOpenSettingsClick() {
  const errorMessage = 'Unable to open settings';

  const handleFailure = (error) => {
    console.error('[EasyForm Popup] ❌ Error opening settings:', error);
    setTemporaryInfo('Settings unavailable');
    showError(errorMessage, { affectHealth: false });
    setTimeout(() => {
      clearErrorIfMatches(errorMessage);
    }, 4000);
  };

  try {
    const maybePromise = browser.runtime.openOptionsPage();
    if (maybePromise && typeof maybePromise.then === 'function') {
      setTemporaryInfo('Opening settings...');
      maybePromise
        .then(() => {
          clearErrorIfMatches(errorMessage);
          setTemporaryInfo('Settings opened');
        })
        .catch(handleFailure);
    } else {
      setTemporaryInfo('Settings opened');
      clearErrorIfMatches(errorMessage);
    }
  } catch (error) {
    handleFailure(error);
  }
}

async function handleOpenBackendClick() {
  const errorMessage = 'Unable to open backend';
  try {
    const targetUrl = normalizeBackendUrl(cachedBackendUrl) || DEFAULT_BACKEND_URL;
    await createTab(targetUrl);
    setTemporaryInfo('Backend opened');
    clearErrorIfMatches(errorMessage);
  } catch (error) {
    console.error('[EasyForm Popup] ❌ Error opening backend:', error);
    setTemporaryInfo('Open failed');
    showError(errorMessage, { affectHealth: false });
    setTimeout(() => {
      clearErrorIfMatches(errorMessage);
    }, 4000);
  }
}

function normalizeBackendUrl(url) {
  if (!url) return null;
  const trimmed = url.trim();
  if (!trimmed) return null;
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

async function createTab(url) {
  return await browser.tabs.create({ url });
}

function clearErrorIfMatches(message) {
  const errorDiv = document.getElementById('errorMessage');
  if (errorDiv.textContent === message) {
    clearError();
  }
}

// Start polling for status updates
function startStatusPolling() {
  // Clear any existing interval
  if (pollingStarted) return;
  pollingStarted = true;
  // Clear any existing interval (safety)
  stopStatusPolling();

  // Poll every 1000ms for status updates
  statusCheckInterval = setInterval(async () => {
    await checkAnalysisState();
  }, 1000);
}

// Stop polling
function stopStatusPolling() {
  if (statusCheckInterval) {
    clearInterval(statusCheckInterval);
    statusCheckInterval = null;
    pollingStarted = false;
  }
}

