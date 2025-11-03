// Minimal Popup Script for EasyForm

document.addEventListener('DOMContentLoaded', async () => {
  await loadConfig();
  await loadStatus();
  setupEventListeners();
});

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
      updateSummary(`Last: ${count} action${count !== 1 ? 's' : ''} found`);
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

  // Settings link - opens options page
  document.getElementById('settingsLink').addEventListener('click', () => {
    chrome.runtime.openOptionsPage();
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

function updateSummary(text) {
  document.getElementById('actionsSummary').textContent = text;
}

function showError(message) {
  const statusDot = document.getElementById('statusDot');
  const errorDiv = document.getElementById('errorMessage');

  statusDot.classList.add('error');
  errorDiv.textContent = message;
  errorDiv.classList.add('show');
}
