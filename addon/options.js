// Options Page Script for EasyForm

const modeDescriptions = {
  automatic: 'Actions are executed immediately after analysis. Best for trusted forms.',
  manual: 'Actions are displayed in an overlay for review. Click "Execute" to apply changes.'
};

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  setupEventListeners();
});

async function loadSettings() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getConfig' });

    // Set backend URL
    document.getElementById('backendUrl').value = response.backendUrl || '';

    // Set API token
    document.getElementById('apiToken').value = response.apiToken || '';

    // Set mode buttons
    const mode = response.mode || 'automatic';
    updateModeButtons(mode);
    updateModeDescription(mode);
  } catch (error) {
    console.error('Error loading settings:', error);
  }
}

function setupEventListeners() {
  // Mode toggle buttons
  document.getElementById('autoModeBtn').addEventListener('click', () => {
    updateModeButtons('automatic');
    updateModeDescription('automatic');
  });

  document.getElementById('manualModeBtn').addEventListener('click', () => {
    updateModeButtons('manual');
    updateModeDescription('manual');
  });

  // Save button
  document.getElementById('saveButton').addEventListener('click', saveSettings);

  // Enter key to save
  document.getElementById('backendUrl').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveSettings();
    }
  });

  document.getElementById('apiToken').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveSettings();
    }
  });
}

function updateModeButtons(mode) {
  const autoBtn = document.getElementById('autoModeBtn');
  const manualBtn = document.getElementById('manualModeBtn');

  autoBtn.classList.toggle('active', mode === 'automatic');
  manualBtn.classList.toggle('active', mode === 'manual');
}

function updateModeDescription(mode) {
  const description = document.getElementById('modeDescription');
  description.textContent = modeDescriptions[mode];
}

async function saveSettings() {
  try {
    const backendUrl = document.getElementById('backendUrl').value.trim();
    const apiToken = document.getElementById('apiToken').value.trim();
    const mode = document.querySelector('.mode-button.active').dataset.mode;

    if (!backendUrl) {
      alert('Please enter a backend URL');
      return;
    }

    // Validate URL
    try {
      new URL(backendUrl);
    } catch {
      alert('Invalid URL format');
      return;
    }

    const response = await chrome.runtime.sendMessage({
      action: 'setConfig',
      backendUrl,
      apiToken,
      mode
    });

    if (response.success) {
      showSuccessMessage();
    } else {
      alert('Failed to save settings');
    }
  } catch (error) {
    console.error('Error saving settings:', error);
    alert('Failed to save settings');
  }
}

function showSuccessMessage() {
  const message = document.getElementById('successMessage');
  message.classList.add('show');

  setTimeout(() => {
    message.classList.remove('show');
  }, 3000);
}
