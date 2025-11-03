// Popup Script for EasyForm

document.addEventListener('DOMContentLoaded', async () => {
  // Load current configuration
  await loadConfig();

  // Load last analysis result
  await loadLastResult();

  // Setup event listeners
  setupEventListeners();
});

/**
 * Load configuration from storage
 */
async function loadConfig() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getConfig' });

    // Set backend URL
    document.getElementById('backendUrl').value = response.backendUrl || '';

    // Set mode buttons
    document.querySelectorAll('.mode-button').forEach(button => {
      if (button.dataset.mode === response.mode) {
        button.classList.add('active');
      } else {
        button.classList.remove('active');
      }
    });

    updateStatus('Ready');
  } catch (error) {
    console.error('Error loading config:', error);
    showError('Failed to load configuration');
  }
}

/**
 * Load last analysis result
 */
async function loadLastResult() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getLastResult' });

    if (response.error) {
      showError(response.error);
    } else if (response.result && response.result.actions) {
      displayActions(response.result.actions);
    } else {
      displayEmptyState();
    }
  } catch (error) {
    console.error('Error loading last result:', error);
    displayEmptyState();
  }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
  // Mode toggle buttons
  document.querySelectorAll('.mode-button').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.mode-button').forEach(b => b.classList.remove('active'));
      button.classList.add('active');
    });
  });

  // Save button
  document.getElementById('saveButton').addEventListener('click', saveConfig);

  // Enter key to save
  document.getElementById('backendUrl').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      saveConfig();
    }
  });
}

/**
 * Save configuration
 */
async function saveConfig() {
  try {
    const backendUrl = document.getElementById('backendUrl').value.trim();
    const mode = document.querySelector('.mode-button.active').dataset.mode;

    if (!backendUrl) {
      showError('Please enter a backend URL');
      return;
    }

    // Validate URL
    try {
      new URL(backendUrl);
    } catch {
      showError('Invalid URL format');
      return;
    }

    const response = await chrome.runtime.sendMessage({
      action: 'setConfig',
      backendUrl,
      mode
    });

    if (response.success) {
      showSuccess('Settings saved successfully');
      updateStatus('Ready');
    } else {
      showError('Failed to save settings');
    }
  } catch (error) {
    console.error('Error saving config:', error);
    showError('Failed to save settings');
  }
}

/**
 * Display actions list
 */
function displayActions(actions) {
  const container = document.getElementById('actionsList');

  if (!actions || actions.length === 0) {
    displayEmptyState();
    return;
  }

  const listHtml = actions.map((action, index) => {
    const question = action.question || `Field ${index + 1}`;
    const number = action.number || index + 1;
    const value = action.value || '-';

    return `
      <div class="action-item">
        <div>
          <span class="action-number">${number}.</span>
          <span class="action-question">${escapeHtml(question)}</span>
        </div>
        <div class="action-answer">${escapeHtml(String(value))}</div>
      </div>
    `;
  }).join('');

  container.innerHTML = `<div class="actions-list">${listHtml}</div>`;
}

/**
 * Display empty state
 */
function displayEmptyState() {
  const container = document.getElementById('actionsList');
  container.innerHTML = '<div class="empty-state">No analysis results yet.<br>Use Ctrl+Shift+E to analyze a page.</div>';
}

/**
 * Update status text
 */
function updateStatus(text) {
  document.getElementById('statusText').textContent = text;
}

/**
 * Show error message
 */
function showError(message) {
  const errorDiv = document.getElementById('errorMessage');
  errorDiv.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
  setTimeout(() => {
    errorDiv.innerHTML = '';
  }, 5000);
}

/**
 * Show success message
 */
function showSuccess(message) {
  const messageDiv = document.getElementById('saveMessage');
  messageDiv.innerHTML = `<div class="success">${escapeHtml(message)}</div>`;
  setTimeout(() => {
    messageDiv.innerHTML = '';
  }, 3000);
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
