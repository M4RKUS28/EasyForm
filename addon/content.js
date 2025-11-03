// Content Script for EasyForm
// Handles page interaction, overlay, and action execution

(function() {
  'use strict';

  let overlayVisible = false;
  let currentActions = [];

  // Listen for messages from background script
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch (request.action) {
      case 'getPageData':
        (async () => {
          try {
            const data = await getPageData();
            sendResponse({ data });
          } catch (error) {
            console.error('[EasyForm Content] Failed to collect page data:', error);
            sendResponse({ error: error.message });
          }
        })();
        return true;

      case 'getScrollInfo':
        const scrollInfo = getScrollInfo();
        sendResponse(scrollInfo);
        break;

      case 'scrollToPosition':
        scrollToPosition(request.x, request.y);
        sendResponse({ success: true });
        break;

      case 'scrollToTop':
        scrollToTop();
        sendResponse({ success: true });
        break;

      case 'restoreScroll':
        restoreScroll(request.x, request.y);
        sendResponse({ success: true });
        break;

      case 'executeActions':
        executeActions(request.actions, request.autoExecute)
          .then(result => sendResponse(result))
          .catch(error => sendResponse({ error: error.message }));
        return true;

      case 'showOverlay':
        currentActions = request.actions;
        showOverlay(request.actions);
        sendResponse({ success: true });
        break;

      case 'toggleOverlay':
        toggleOverlay();
        sendResponse({ success: true });
        break;

      case 'showNotification':
        showNotification(request.type, request.message);
        sendResponse({ success: true });
        break;
    }
  });

  /**
   * Extract page data (text and HTML)
   */
  async function getPageData() {
    const clipboard = await readClipboard();

    const data = {
      url: window.location.href,
      title: document.title,
      text: document.body.innerText,
      html: document.documentElement.outerHTML,
      clipboard,
      timestamp: new Date().toISOString()
    };
    console.log('[EasyForm Content] Page data extracted:', {
      url: data.url,
      title: data.title,
      textLength: data.text?.length,
      htmlLength: data.html?.length,
      clipboardLength: data.clipboard?.length
    });
    return data;
  }

  async function readClipboard() {
    try {
      if (navigator.clipboard?.readText) {
        const text = await navigator.clipboard.readText();
        return text || null;
      }
    } catch (error) {
      console.warn('[EasyForm Content] Clipboard read failed:', error);
    }
    return null;
  }

  /**
   * Get scroll information for screenshot capture
   */
  function getScrollInfo() {
    return {
      scrollX: window.scrollX || window.pageXOffset,
      scrollY: window.scrollY || window.pageYOffset,
      scrollWidth: document.documentElement.scrollWidth,
      scrollHeight: document.documentElement.scrollHeight,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      documentWidth: document.documentElement.clientWidth,
      documentHeight: document.documentElement.clientHeight
    };
  }

  /**
   * Scroll to specific position
   */
  function scrollToPosition(x, y) {
    window.scrollTo({
      left: x,
      top: y,
      behavior: 'instant'
    });
  }

  /**
   * Scroll to top of page
   */
  function scrollToTop() {
    window.scrollTo({
      left: 0,
      top: 0,
      behavior: 'instant'
    });
  }

  /**
   * Restore scroll position
   */
  function restoreScroll(x, y) {
    window.scrollTo({
      left: x,
      top: y,
      behavior: 'instant'
    });
  }

  /**
   * Execute actions using ActionExecutor
   */
  async function executeActions(actions, autoExecute = true) {
    if (window.ActionExecutor) {
      return await window.ActionExecutor.executeActions(actions, autoExecute);
    } else {
      throw new Error('ActionExecutor not loaded');
    }
  }

  /**
   * Show overlay with actions
   */
  function showOverlay(actions) {
    // Remove existing overlay if any
    removeOverlay();

    // Create overlay
    const overlay = createOverlay(actions);
    document.body.appendChild(overlay);
    overlayVisible = true;
  }

  /**
   * Toggle overlay visibility
   */
  function toggleOverlay() {
    if (overlayVisible) {
      removeOverlay();
    } else if (currentActions.length > 0) {
      showOverlay(currentActions);
    }
  }

  /**
   * Remove overlay
   */
  function removeOverlay() {
    const overlay = document.getElementById('easyform-overlay');
    if (overlay) {
      overlay.remove();
      overlayVisible = false;
    }
  }

  /**
   * Create overlay element
   */
  function createOverlay(actions) {
    const overlay = document.createElement('div');
    overlay.id = 'easyform-overlay';
    overlay.className = 'easyform-overlay';

    // Header
    const header = document.createElement('div');
    header.className = 'easyform-header';
    header.innerHTML = `
      <span class="easyform-title">EasyForm - Form Analysis</span>
      <button class="easyform-close" id="easyform-close">×</button>
    `;

    // Content
    const content = document.createElement('div');
    content.className = 'easyform-content';

    // Actions list
    const list = document.createElement('div');
    list.className = 'easyform-list';

    actions.forEach((action, index) => {
      const item = document.createElement('div');
      item.className = 'easyform-item';

      const question = action.question || `Field ${index + 1}`;
      const number = action.number || index + 1;
      const value = action.value || '-';

      item.innerHTML = `
        <div class="easyform-item-header">
          <span class="easyform-number">${number}.</span>
          <span class="easyform-question">${escapeHtml(question)}</span>
        </div>
        <div class="easyform-answer">${escapeHtml(String(value))}</div>
      `;

      list.appendChild(item);
    });

    content.appendChild(list);

    // Footer with execute button
    const footer = document.createElement('div');
    footer.className = 'easyform-footer';
    footer.innerHTML = `
      <button class="easyform-execute" id="easyform-execute">
        Execute Actions (${actions.length})
      </button>
    `;

    // Assemble overlay
    overlay.appendChild(header);
    overlay.appendChild(content);
    overlay.appendChild(footer);

    // Event listeners
    overlay.querySelector('#easyform-close').addEventListener('click', removeOverlay);
    overlay.querySelector('#easyform-execute').addEventListener('click', async () => {
      const button = overlay.querySelector('#easyform-execute');
      button.disabled = true;
      button.textContent = 'Executing...';

      try {
        const result = await executeActions(actions, true);
        if (result.success) {
          showNotification('success', `Executed ${result.successCount} action(s)`);
          removeOverlay();
        } else {
          showNotification('error', `Failed: ${result.failCount} action(s)`);
        }
      } catch (error) {
        showNotification('error', error.message);
      } finally {
        button.disabled = false;
        button.textContent = `Execute Actions (${actions.length})`;
      }
    });

    // Make draggable
    makeDraggable(overlay, header);

    return overlay;
  }

  /**
   * Make element draggable
   */
  function makeDraggable(element, handle) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

    handle.onmousedown = dragMouseDown;

    function dragMouseDown(e) {
      e.preventDefault();
      pos3 = e.clientX;
      pos4 = e.clientY;
      document.onmouseup = closeDragElement;
      document.onmousemove = elementDrag;
    }

    function elementDrag(e) {
      e.preventDefault();
      pos1 = pos3 - e.clientX;
      pos2 = pos4 - e.clientY;
      pos3 = e.clientX;
      pos4 = e.clientY;
      element.style.top = (element.offsetTop - pos2) + 'px';
      element.style.left = (element.offsetLeft - pos1) + 'px';
    }

    function closeDragElement() {
      document.onmouseup = null;
      document.onmousemove = null;
    }
  }

  /**
   * Show notification (disabled - notifications only shown in extension popup)
   */
  function showNotification(type, message) {
    // Log to console instead of showing floating notification
    console.log(`[EasyForm ${type.toUpperCase()}]:`, message);
  }

  /**
   * Escape HTML
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Initialize
  console.log('EasyForm content script loaded');
})();
