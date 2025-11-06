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
        console.log('[EasyForm Content] 📨 Received executeActions message:', {
          actionsCount: request.actions?.length,
          autoExecute: request.autoExecute,
          timestamp: new Date().toISOString()
        });
        executeActions(request.actions, request.autoExecute)
          .then(result => {
            console.log('[EasyForm Content] ✅ executeActions completed:', result);
            sendResponse(result);
          })
          .catch(error => {
            console.error('[EasyForm Content] ❌ executeActions error:', error);
            sendResponse({ error: error.message });
          });
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
    const data = {
      url: window.location.href,
      title: document.title,
      text: document.body.innerText,
      html: document.documentElement.outerHTML,
      sessionInstructions: null,
      timestamp: new Date().toISOString()
    };
    console.log('[EasyForm Content] Page data extracted:', {
      url: data.url,
      title: data.title,
      textLength: data.text?.length,
      htmlLength: data.html?.length,
      sessionInstructionsLength: data.sessionInstructions?.length || 0
    });
    return data;
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

    // Store filtered actions
    let filteredActions = [...actions];

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

    const renderActions = () => {
      list.innerHTML = '';
      
      // Group checkbox and radio actions by label
      const groupedActions = [];
      const checkboxGroups = new Map();
      const radioGroups = new Map();
      
      filteredActions.forEach((action, index) => {
        if (action.action_type === 'selectCheckbox') {
          const label = action.label || 'Checkbox';
          if (!checkboxGroups.has(label)) {
            checkboxGroups.set(label, []);
          }
          checkboxGroups.get(label).push({ action, index });
        } else if (action.action_type === 'selectRadio') {
          const label = action.label || 'Radio';
          if (!radioGroups.has(label)) {
            radioGroups.set(label, []);
          }
          radioGroups.get(label).push({ action, index });
        } else {
          groupedActions.push({ action, index, type: 'single' });
        }
      });
      
      // Convert checkbox groups to grouped actions
      checkboxGroups.forEach((group, label) => {
        groupedActions.push({ label, group, type: 'checkbox-group' });
      });
      
      // Convert radio groups to grouped actions
      radioGroups.forEach((group, label) => {
        groupedActions.push({ label, group, type: 'radio-group' });
      });
      
      // Sort by original index
      groupedActions.sort((a, b) => {
        const indexA = a.type === 'single' ? a.index : a.group[0].index;
        const indexB = b.type === 'single' ? b.index : b.group[0].index;
        return indexA - indexB;
      });
      
      groupedActions.forEach((item, displayIndex) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'easyform-item';
        const itemNumber = displayIndex + 1;
        
        if (item.type === 'single') {
          // Regular action
          const action = item.action;
          const index = item.index;
          const question = action.label || action.question || `Field ${index + 1}`;
          const description = action.description || '';
          const value = action.value !== null && action.value !== undefined ? action.value : '-';

          itemDiv.dataset.actionIndex = index;
          itemDiv.innerHTML = `
            <div class="easyform-item-content">
              <div class="easyform-item-header">
                <div class="easyform-question-wrapper">
                  <span class="easyform-number">${itemNumber}.</span>
                  <span class="easyform-question">${escapeHtml(question)}</span>
                </div>
                <button class="easyform-remove" data-index="${index}" title="Remove this action">×</button>
              </div>
              ${description ? `
                <div class="easyform-description">
                  <span class="easyform-description-text">${escapeHtml(description)}</span>
                </div>
              ` : ''}
              <div class="easyform-answer">${escapeHtml(String(value))}</div>
            </div>
          `;
        } else if (item.type === 'checkbox-group') {
          // Checkbox group
          const label = item.label;
          const group = item.group;
          
          // Extract checkbox values from selectors
          const checkboxes = group.map(({ action, index }) => {
            const match = action.selector.match(/\[value=['"]([^'"]+)['"]\]/);
            const optionValue = match ? match[1] : 'unknown';
            const isChecked = action.value === '1' || action.value === 1 || action.value === true;
            return { optionValue, isChecked, index };
          });
          
          const selectedOptions = checkboxes.filter(cb => cb.isChecked).map(cb => cb.optionValue);
          const unselectedOptions = checkboxes.filter(cb => !cb.isChecked).map(cb => cb.optionValue);
          
          const displayValue = selectedOptions.length > 0 
            ? `✓ ${selectedOptions.join(', ')}`
            : 'None selected';
          
          itemDiv.innerHTML = `
            <div class="easyform-item-content">
              <div class="easyform-item-header">
                <div class="easyform-question-wrapper">
                  <span class="easyform-number">${itemNumber}.</span>
                  <span class="easyform-question">${escapeHtml(label)}</span>
                </div>
                <button class="easyform-remove-group" data-label="${escapeHtml(label)}" title="Remove all ${escapeHtml(label)} actions">×</button>
              </div>
              <div class="easyform-answer easyform-checkbox-answer">${escapeHtml(displayValue)}</div>
              ${unselectedOptions.length > 0 ? `
                <div class="easyform-checkbox-unselected">
                  ✗ ${escapeHtml(unselectedOptions.join(', '))}
                </div>
              ` : ''}
            </div>
          `;
        } else if (item.type === 'radio-group') {
          // Radio group
          const label = item.label;
          const group = item.group;
          
          // Extract radio values from selectors
          const radios = group.map(({ action, index }) => {
            const match = action.selector.match(/\[value=['"]([^'"]+)['"]\]/);
            const optionValue = match ? match[1] : 'unknown';
            return { optionValue, index };
          });
          
          // Only one radio should be selected (the one in the group)
          const selectedValue = radios.length > 0 ? radios[0].optionValue : 'unknown';
          
          itemDiv.innerHTML = `
            <div class="easyform-item-content">
              <div class="easyform-item-header">
                <div class="easyform-question-wrapper">
                  <span class="easyform-number">${itemNumber}.</span>
                  <span class="easyform-question">${escapeHtml(label)}</span>
                </div>
                <button class="easyform-remove-group" data-label="${escapeHtml(label)}" title="Remove ${escapeHtml(label)} action">×</button>
              </div>
              <div class="easyform-answer easyform-radio-answer">◉ ${escapeHtml(selectedValue)}</div>
            </div>
          `;
        }

        list.appendChild(itemDiv);
      });

      // Add event listeners for remove buttons (single actions)
      list.querySelectorAll('.easyform-remove').forEach(button => {
        button.addEventListener('click', (e) => {
          e.stopPropagation();
          const index = parseInt(button.dataset.index);
          filteredActions.splice(index, 1);
          renderActions();
          updateExecuteButton();
        });
      });
      
      // Add event listeners for remove group buttons (checkbox/radio groups)
      list.querySelectorAll('.easyform-remove-group').forEach(button => {
        button.addEventListener('click', (e) => {
          e.stopPropagation();
          const label = button.dataset.label;
          // Remove all actions with this label
          filteredActions = filteredActions.filter(action => action.label !== label);
          renderActions();
          updateExecuteButton();
        });
      });
    };

    renderActions();

    content.appendChild(list);

    // Footer with execute button
    const footer = document.createElement('div');
    footer.className = 'easyform-footer';
    footer.innerHTML = `
      <button class="easyform-execute" id="easyform-execute">
        Execute Actions (${filteredActions.length})
      </button>
    `;

    // Update execute button text
    const updateExecuteButton = () => {
      const button = footer.querySelector('#easyform-execute');
      if (button) {
        button.textContent = `Execute Actions (${filteredActions.length})`;
        button.disabled = filteredActions.length === 0;
      }
    };

    // Assemble overlay
    overlay.appendChild(header);
    overlay.appendChild(content);
    overlay.appendChild(footer);

    // Event listeners
    overlay.querySelector('#easyform-close').addEventListener('click', removeOverlay);
    overlay.querySelector('#easyform-execute').addEventListener('click', async () => {
      if (filteredActions.length === 0) return;

      const button = overlay.querySelector('#easyform-execute');
      button.disabled = true;
      button.textContent = 'Executing...';

      try {
        const result = await executeActions(filteredActions, true);
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
        button.textContent = `Execute Actions (${filteredActions.length})`;
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
