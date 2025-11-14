// Options Page Script for EasyForm

document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  setupEventListeners();
});

async function loadSettings() {
  try {
    const response = await browser.runtime.sendMessage({ action: 'getConfig' });

    // Set backend URL
    document.getElementById('backendUrl').value = response.backendUrl || '';

    // Set API token
    document.getElementById('apiToken').value = response.apiToken || '';

    // Set quality dropdown
    const quality = response.quality || 'fast';
    document.getElementById('quality').value = quality;

    // Set auto-open preview checkbox (default true)
    const autoOpenPreview = response.autoOpenPreview !== undefined ? response.autoOpenPreview : true;
    document.getElementById('autoOpenPreview').checked = autoOpenPreview;
  } catch (error) {
    console.error('Error loading settings:', error);
  }
}

function setupEventListeners() {
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

async function saveSettings() {
  try {
    const backendUrl = document.getElementById('backendUrl').value.trim();
    const apiToken = document.getElementById('apiToken').value.trim();
    const quality = document.getElementById('quality').value;
    const autoOpenPreview = document.getElementById('autoOpenPreview').checked;

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

    const response = await browser.runtime.sendMessage({
      action: 'setConfig',
      backendUrl,
      apiToken,
      quality,
      autoOpenPreview
    });

    if (response && response.success) {
      showSuccessMessage();
    } else {
      const errorMsg = response && response.error ? response.error : 'Failed to save settings';
      alert(errorMsg);
    }
  } catch (error) {
    console.error('Error saving settings:', error);
    alert(`Failed to save settings: ${error.message}`);
  }
}

function showSuccessMessage() {
  const message = document.getElementById('successMessage');
  message.classList.add('show');

  setTimeout(() => {
    message.classList.remove('show');
  }, 3000);
}
